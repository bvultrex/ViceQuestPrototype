#!/usr/bin/env python3
"""ViceQuest v0.6.18.34 Downtown train core.

Build-time:
- extract original GTA2 TRAIN / TRAINCAB / TRAINFB / boxcar sprites from wil.sty
- reconstruct railway lines from FIELD blocks carrying GTA2 green arrows
- infer station stop points from Downtown platform tiles next to the rail graph
- synthesize bounded train rumble/clack/door audio for the Quest manual mix

Runtime:
- up to two Downtown trains, matching original wil.mis initial station setup
- one TRAINCAB + three passenger TRAIN cars per consist
- cyclic station service with braking, dwell and departure
- server-authoritative train progress with lightweight RPC state sync
- vehicle impact/crush interaction
- manual distance-attenuated train audio
- elevated Quest pop-out clones for train cars

Also removes the wrongly identified skull/coin skid_blob from braking.
"""
from pathlib import Path
import json
import math
import re
import struct
import sys
import wave

from PIL import Image

root = Path(sys.argv[1]).resolve()
assets = root / "assets"
train_out = assets / "gta2" / "train"
vehicle_out = assets / "vehicles"
audio_out = assets / "audio" / "gta2" / "sfx"
train_out.mkdir(parents=True, exist_ok=True)
vehicle_out.mkdir(parents=True, exist_ok=True)
audio_out.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# GTA2 STY sprite extraction. Same CARI/SPRX/PPAL scheme already used by the
# enforcement extractor on this branch.
# ---------------------------------------------------------------------------
def chunks(data: bytes):
    result = {}
    pos = 6
    while pos + 8 <= len(data):
        kind = data[pos:pos+4].decode("latin1")
        size = struct.unpack_from("<I", data, pos + 4)[0]
        result[kind] = (pos + 8, size)
        pos += 8 + size
    return result

def car_sprite_lookup(data: bytes, cari_offset: int, cari_size: int):
    lookup = {}
    cursor = 0
    relative_sprite = 0
    while cursor < cari_size:
        record = cari_offset + cursor
        model = data[record]
        sprite_count = data[record + 1]
        remap_count = data[record + 4]
        lookup[model] = (relative_sprite, sprite_count)
        door_count_offset = record + 14 + remap_count
        door_count = data[door_count_offset]
        cursor = door_count_offset - cari_offset + 1 + door_count * 2
        relative_sprite += sprite_count
    return lookup

def sprite_tools(sty: Path):
    data = sty.read_bytes()
    t = chunks(data)
    spg, _ = t["SPRG"]
    sprx, sprx_size = t["SPRX"]
    palx, _ = t["PALX"]
    ppal, _ = t["PPAL"]
    sprb, _ = t["SPRB"]
    palb, _ = t["PALB"]
    sprite_counts = struct.unpack_from("<6H", data, sprb)
    palette_counts = struct.unpack_from("<8H", data, palb)
    sprite_bases = []
    run = 0
    for n in sprite_counts:
        sprite_bases.append(run)
        run += n
    palette_bases = []
    run = 0
    for n in palette_counts:
        palette_bases.append(run)
        run += n

    def rgba(physical, c):
        idx = (physical // 64) * 64 * 256 + (physical % 64) + c * 64
        v = struct.unpack_from("<I", data, ppal + idx * 4)[0]
        return ((v >> 16) & 255, (v >> 8) & 255, v & 255, 0 if c == 0 else 255)

    def sprite(true_index: int):
        pointer, w, h, _ = struct.unpack_from("<IBBH", data, sprx + true_index * 8)
        vp = palette_bases[1] + true_index
        physical = struct.unpack_from("<H", data, palx + vp * 2)[0]
        image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = image.load()
        for y in range(h):
            row = spg + pointer + y * 256
            for x in range(w):
                px[x, y] = rgba(physical, data[row + x])
        return image
    return data, t, sprite, sprx_size // 8

wil = root / "source_gta2" / "wil.sty"
if not wil.is_file():
    raise SystemExit(f"Missing Downtown style: {wil}")
sty_data, sty_chunks, get_sprite, _ = sprite_tools(wil)
cari, cari_size = sty_chunks["CARI"]
lookup = car_sprite_lookup(sty_data, cari, cari_size)

TRAIN_MODELS = {
    "train_passenger": 59,  # TRAIN
    "train_cab": 60,        # TRAINCAB
    "train_freight": 61,    # TRAINFB
    "train_boxcar": 6,      # boxcar
}
manifest = {}
for name, model in TRAIN_MODELS.items():
    if model not in lookup:
        raise SystemExit(f"Train model {model} missing from CARI")
    first, count = lookup[model]
    manifest[name] = {"model": model, "first_sprite": first, "sprite_count": count}
    frame_count = min(max(1, count), 8)
    for frame in range(frame_count):
        image = get_sprite(first + frame).transpose(Image.Transpose.ROTATE_270)
        path = train_out / f"{name}_{frame}.png"
        image.save(path, optimize=True)
    # stable frame-0 convenience path
    get_sprite(first).transpose(Image.Transpose.ROTATE_270).save(train_out / f"{name}.png", optimize=True)

# ---------------------------------------------------------------------------
# Railway reconstruction from exact Downtown block data.
# GTA2 railway detection is FIELD block + any green arrow in low nibble.
# Green directions: left bit0, right bit1, up bit2, down bit3.
# ---------------------------------------------------------------------------
map_path = assets / "gta2" / "downtown" / "downtown_exact_map.json"
if not map_path.is_file():
    raise SystemExit(f"Missing exact Downtown map: {map_path}")
data = json.loads(map_path.read_text(encoding="utf-8"))
block_defs = data["block_defs"]
columns = data["columns"]

def arrow_value(block: dict) -> int:
    for key in ("arrows", "arrow", "arrow_data", "traffic_arrows"):
        if key in block:
            try:
                return int(block[key])
            except Exception:
                pass
    for key, value in block.items():
        if "arrow" in str(key).lower() and isinstance(value, (int, float)):
            return int(value)
    return 0

def lid_tile(block: dict) -> int:
    lid = block.get("lid", {})
    if isinstance(lid, dict):
        return int(lid.get("tile", 0) or 0)
    return 0

rail = {}
platform_cells = []
for column in columns:
    x = int(column["x"])
    y = int(column["y"])
    off = int(column["offset"])
    for local_z, raw_bid in enumerate(column["blocks"]):
        bid = int(raw_bid)
        if bid == 0:
            continue
        z = off + local_z
        block = block_defs[bid]
        ground = int(block.get("ground_type", -1))
        arrows = arrow_value(block) & 0x0F
        if ground == 3 and arrows:
            rail[(x, y, z)] = arrows
        if ground == 2 and z >= 1 and lid_tile(block) in (346, 350):
            platform_cells.append((x, y, z))

if len(rail) < 40:
    sample_keys = sorted(str(k) for k in block_defs[1].keys()) if len(block_defs) > 1 else []
    raise SystemExit(f"Rail reconstruction found only {len(rail)} arrow FIELD cells; block keys={sample_keys}")

DIRS = {
    0x1: (-1, 0),  # green left
    0x2: (1, 0),   # green right
    0x4: (0, -1),  # green up
    0x8: (0, 1),   # green down
}
OPPOSITE = {0x1: 0x2, 0x2: 0x1, 0x4: 0x8, 0x8: 0x4}

def neighbor_for(cell, bit):
    x, y, z = cell
    dx, dy = DIRS[bit]
    for dz in (0, 1, -1):
        candidate = (x + dx, y + dy, z + dz)
        if candidate not in rail:
            continue
        # Connect when either side explicitly describes this rail edge.
        other = rail[candidate]
        if (rail[cell] & bit) or (other & OPPOSITE[bit]):
            return candidate
    return None

adj = {cell: set() for cell in rail}
for cell in rail:
    for bit in DIRS:
        if not (rail[cell] & bit):
            continue
        other = neighbor_for(cell, bit)
        if other is not None:
            adj[cell].add(other)
            adj[other].add(cell)

# Remove isolated arrow markers.
adj = {k: v for k, v in adj.items() if v}
rail_nodes = set(adj)

components = []
remaining = set(rail_nodes)
while remaining:
    start = next(iter(remaining))
    todo = [start]
    comp = set()
    while todo:
        node = todo.pop()
        if node in comp:
            continue
        comp.add(node)
        remaining.discard(node)
        for nb in adj.get(node, ()):
            if nb not in comp:
                todo.append(nb)
    if len(comp) >= 12:
        components.append(comp)
components.sort(key=len, reverse=True)

def direction_vec(a, b):
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])

def walk_component(comp):
    # Prefer an endpoint for an open route. Otherwise start deterministically.
    endpoints = sorted([n for n in comp if len([q for q in adj[n] if q in comp]) == 1])
    start = endpoints[0] if endpoints else min(comp)
    path = [start]
    prev = None
    current = start
    used_edges = set()
    max_steps = max(32, len(comp) * 3)

    for _ in range(max_steps):
        candidates = []
        for nb in adj[current]:
            if nb not in comp or nb == prev:
                continue
            edge = tuple(sorted((current, nb)))
            if edge in used_edges:
                continue
            candidates.append(nb)
        if not candidates:
            # For a loop, closing to start is valid.
            if start in adj[current] and start != prev:
                edge = tuple(sorted((current, start)))
                if edge not in used_edges:
                    used_edges.add(edge)
                    return path, True
            break

        if prev is not None and len(candidates) > 1:
            incoming = direction_vec(prev, current)
            def straight_score(nb):
                out = direction_vec(current, nb)
                return incoming[0] * out[0] + incoming[1] * out[1] + incoming[2] * out[2]
            candidates.sort(key=straight_score, reverse=True)
        else:
            candidates.sort()

        nxt = candidates[0]
        edge = tuple(sorted((current, nxt)))
        used_edges.add(edge)
        if nxt == start:
            return path, True
        path.append(nxt)
        prev, current = current, nxt

    return path, False

raw_lines = []
for comp in components[:6]:
    path, closed = walk_component(comp)
    if len(path) < 16:
        continue
    # If graph is open, turn it into a safe ping-pong cycle. This avoids an
    # instant teleport at endpoints while retaining the exact rail geometry.
    if not closed and len(path) >= 3:
        path = path + list(reversed(path[1:-1]))
        closed = True
    raw_lines.append((path, closed, comp))

if not raw_lines:
    raise SystemExit(f"No usable railway line from {len(rail)} railway cells / {len(components)} components")

# Cluster platform tiles and attach cluster center to nearest route point.
platform_set = set(platform_cells)
platform_clusters = []
pending = set(platform_set)
while pending:
    seed = pending.pop()
    cluster = {seed}
    stack = [seed]
    while stack:
        x, y, z = stack.pop()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            n = (x+dx, y+dy, z)
            if n in pending:
                pending.remove(n)
                cluster.add(n)
                stack.append(n)
    if len(cluster) >= 2:
        platform_clusters.append(cluster)

lines_out = []
for line_index, (path, closed, comp) in enumerate(raw_lines[:2]):
    stops = []
    for cluster in platform_clusters:
        cx = sum(p[0] + 0.5 for p in cluster) / len(cluster)
        cy = sum(p[1] + 0.5 for p in cluster) / len(cluster)
        cz = sum(p[2] for p in cluster) / len(cluster)
        best_index = -1
        best_dist = 9999.0
        for idx, p in enumerate(path):
            d = math.hypot((p[0] + 0.5) - cx, (p[1] + 0.5) - cy) + abs(p[2] - cz) * 1.6
            if d < best_dist:
                best_dist = d
                best_index = idx
        if best_index >= 0 and best_dist <= 4.5:
            if all(abs(best_index - old["point_index"]) > 5 for old in stops):
                stops.append({
                    "point_index": best_index,
                    "platform_x": cx,
                    "platform_y": cy,
                    "platform_z": cz,
                })
    stops.sort(key=lambda s: s["point_index"])

    # If platform tiles were not preserved in this reconstruction, provide
    # conservative evenly spaced operational stops so the train still has a
    # stop/dwell/depart cycle for hardware testing.
    if len(stops) < 2 and len(path) >= 40:
        stops = [
            {"point_index": 0, "platform_x": path[0][0]+0.5, "platform_y": path[0][1]+0.5, "platform_z": path[0][2]},
            {"point_index": len(path)//2, "platform_x": path[len(path)//2][0]+0.5, "platform_y": path[len(path)//2][1]+0.5, "platform_z": path[len(path)//2][2]},
        ]

    lines_out.append({
        "name": f"trak{line_index}",
        "closed": bool(closed),
        "points": [[p[0] + 0.5, p[1] + 0.5, p[2]] for p in path],
        "stops": stops,
    })

route_payload = {
    "source": "downtown_exact_map:FIELD+green_arrows",
    "rail_cells": len(rail),
    "components": [len(c) for c in components],
    "platform_clusters": len(platform_clusters),
    "lines": lines_out,
}
(train_out / "downtown_train_routes.json").write_text(json.dumps(route_payload, indent=2) + "\n", encoding="utf-8")
(train_out / "train_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# Lightweight train audio. GTA2 RE confirms a train engine loop, rolling
# friction loop and station/door event. This build uses clean synthesized loops
# until the exact sample-bank extraction is folded into the project.
# ---------------------------------------------------------------------------
def write_wav(path: Path, samples, rate=22050):
    peak = max((abs(s) for s in samples), default=1.0) or 1.0
    gain = min(0.88 / peak, 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for s in samples:
            v = max(-32767, min(32767, int(s * gain * 32767)))
            frames += struct.pack("<h", v)
        w.writeframes(frames)

rate = 22050
duration = 2.4
rumble = []
for i in range(int(rate * duration)):
    t = i / rate
    # low traction hum + harmonic + wheel/rail texture
    s = 0.36 * math.sin(2*math.pi*46*t)
    s += 0.22 * math.sin(2*math.pi*92*t + 0.4)
    s += 0.08 * math.sin(2*math.pi*138*t + 1.1)
    s += 0.035 * math.sin(2*math.pi*310*t)
    rumble.append(s)
write_wav(audio_out / "train_rumble.wav", rumble)
write_wav(audio_out / "train_rumble_0.wav", rumble)
write_wav(audio_out / "train_rumble_1.wav", [v * 0.985 for v in rumble])

clack = []
duration = 1.6
for i in range(int(rate * duration)):
    t = i / rate
    phase = t % 0.40
    hit = math.exp(-phase * 36.0) if phase < 0.12 else 0.0
    s = hit * (0.35 * math.sin(2*math.pi*180*t) + 0.18 * math.sin(2*math.pi*360*t))
    clack.append(s)
write_wav(audio_out / "train_clack.wav", clack)

door = []
duration = 0.65
for i in range(int(rate * duration)):
    t = i / rate
    env = math.exp(-t * 4.5)
    s = env * (0.40 * math.sin(2*math.pi*620*t) + 0.18 * math.sin(2*math.pi*930*t))
    door.append(s)
write_wav(audio_out / "train_door.wav", door)

# ---------------------------------------------------------------------------
# Runtime train system.
# ---------------------------------------------------------------------------
train_gd = r'''class_name ViceQuestTrainSystem
extends Node3D

const MAX_TRAINS: int = 2
const PASSENGER_WAGONS: int = 3
const CAR_SPACING: float = 1.46
const MAX_SPEED: float = 5.8
const ACCEL: float = 1.65
const BRAKE: float = 2.35
const DWELL_SECONDS: float = 4.6
const SYNC_INTERVAL: float = 0.22
const IMPACT_RADIUS: float = 0.78
const IMPACT_COOLDOWN_MS: int = 600

var host: Node
var presentation_rig: Node
var tile_size: float = 2.5
var height_unit: float = 0.6
var lines: Array = []
var trains: Array[Dictionary] = []
var train_visuals: Dictionary = {}
var _sync_accum: float = 0.0
var _impact_until: Dictionary = {}

func configure(host_node: Node, tile_size_value: float, height_unit_value: float, rig_node: Node) -> void:
    host = host_node
    tile_size = tile_size_value
    height_unit = height_unit_value
    presentation_rig = rig_node
    _load_routes()
    _build_trains()

func _load_routes() -> void:
    var path: String = "res://assets/gta2/train/downtown_train_routes.json"
    if not FileAccess.file_exists(path):
        push_warning("ViceQuest train routes missing")
        return
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
    if not (parsed is Dictionary):
        return
    var raw_lines: Variant = (parsed as Dictionary).get("lines", [])
    if not (raw_lines is Array):
        return

    for raw_line: Variant in raw_lines:
        if not (raw_line is Dictionary):
            continue
        var source: Dictionary = raw_line
        var raw_points: Variant = source.get("points", [])
        if not (raw_points is Array) or (raw_points as Array).size() < 4:
            continue
        var points: Array[Vector3] = []
        for raw_point: Variant in raw_points:
            if not (raw_point is Array) or (raw_point as Array).size() < 3:
                continue
            var p: Array = raw_point
            points.append(Vector3(float(p[0]) * tile_size, float(p[2]) * height_unit + 0.082, float(p[1]) * tile_size))
        if points.size() < 4:
            continue

        var cumulative: Array[float] = [0.0]
        var total: float = 0.0
        for index in range(1, points.size()):
            total += points[index - 1].distance_to(points[index])
            cumulative.append(total)
        var closing: float = points[-1].distance_to(points[0])
        if closing <= tile_size * 1.8:
            total += closing

        var stop_distances: Array[float] = []
        var raw_stops: Variant = source.get("stops", [])
        if raw_stops is Array:
            for stop_variant: Variant in raw_stops:
                if stop_variant is Dictionary:
                    var idx: int = clampi(int((stop_variant as Dictionary).get("point_index", 0)), 0, cumulative.size() - 1)
                    stop_distances.append(cumulative[idx])
        stop_distances.sort()

        lines.append({
            "name": String(source.get("name", "trak")),
            "points": points,
            "cumulative": cumulative,
            "length": maxf(total, 0.1),
            "stops": stop_distances,
        })

func _make_train_sprite(texture_path: String, car_name: String) -> Sprite3D:
    var sprite: Sprite3D = Sprite3D.new()
    sprite.name = car_name
    sprite.texture = load(texture_path) as Texture2D
    sprite.pixel_size = 0.025
    sprite.rotation_degrees.x = -90.0
    sprite.shaded = false
    sprite.centered = true
    sprite.double_sided = true
    sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    sprite.layers = 1
    sprite.render_priority = 9
    return sprite

func _build_trains() -> void:
    var count: int = mini(MAX_TRAINS, lines.size())
    for index in range(count):
        var line: Dictionary = lines[index]
        var root_node: Node3D = Node3D.new()
        root_node.name = "DowntownTrain_%d" % index
        add_child(root_node)

        var cars: Array[Node3D] = []
        for car_index in range(PASSENGER_WAGONS + 1):
            var holder: Node3D = Node3D.new()
            holder.name = "Train%dCar%d" % [index, car_index]
            var texture_path: String = "res://assets/gta2/train/train_cab.png" if car_index == 0 else "res://assets/gta2/train/train_passenger.png"
            holder.add_child(_make_train_sprite(texture_path, "Body"))
            root_node.add_child(holder)
            cars.append(holder)
            train_visuals[index * 16 + car_index] = holder

        var rumble: AudioStreamPlayer = AudioStreamPlayer.new()
        rumble.name = "TrainRumble_%d" % index
        rumble.stream = load("res://assets/audio/gta2/sfx/train_rumble_%d.wav" % index) as AudioStream
        rumble.volume_db = -40.0
        add_child(rumble)
        if rumble.stream != null:
            var length: float = rumble.stream.get_length()
            rumble.play(fposmod(float(index) * 0.61, maxf(0.05, length - 0.05)))

        var clack: AudioStreamPlayer = AudioStreamPlayer.new()
        clack.name = "TrainClack_%d" % index
        clack.stream = load("res://assets/audio/gta2/sfx/train_clack.wav") as AudioStream
        clack.volume_db = -42.0
        add_child(clack)
        if clack.stream != null:
            clack.play(float(index) * 0.18)

        var start_distance: float = 0.0
        var stops: Array = line["stops"]
        if not stops.is_empty():
            start_distance = float(stops[0])
        elif index > 0:
            start_distance = float(line["length"]) * 0.5

        trains.append({
            "line": index,
            "distance": start_distance,
            "target_distance": start_distance,
            "speed": 0.0,
            "dwell": 1.5 + float(index),
            "next_stop": 1 if stops.size() > 1 else 0,
            "cars": cars,
            "rumble": rumble,
            "clack": clack,
            "door_open": true,
            "last_door_state": true,
        })

    _refresh_all_visuals()

func _wrap_distance(value: float, total: float) -> float:
    if total <= 0.01:
        return 0.0
    return fposmod(value, total)

func _forward_distance(current: float, target: float, total: float) -> float:
    return _wrap_distance(target - current, total)

func _sample_line(line: Dictionary, distance: float) -> Dictionary:
    var points: Array = line["points"]
    var cumulative: Array = line["cumulative"]
    var total: float = float(line["length"])
    var d: float = _wrap_distance(distance, total)

    for index in range(points.size() - 1):
        var a_dist: float = float(cumulative[index])
        var b_dist: float = float(cumulative[index + 1])
        if d <= b_dist:
            var span: float = maxf(0.001, b_dist - a_dist)
            var t: float = clampf((d - a_dist) / span, 0.0, 1.0)
            var a: Vector3 = points[index]
            var b: Vector3 = points[index + 1]
            var direction: Vector3 = b - a
            direction.y = 0.0
            if direction.length_squared() <= 0.001:
                direction = Vector3(0.0, 0.0, -1.0)
            else:
                direction = direction.normalized()
            return {"position": a.lerp(b, t), "direction": direction}

    var last: Vector3 = points[-1]
    var first: Vector3 = points[0]
    var closing_start: float = float(cumulative[-1])
    var closing_span: float = maxf(0.001, total - closing_start)
    var closing_t: float = clampf((d - closing_start) / closing_span, 0.0, 1.0)
    var closing_dir: Vector3 = first - last
    closing_dir.y = 0.0
    if closing_dir.length_squared() <= 0.001:
        closing_dir = Vector3(0.0, 0.0, -1.0)
    else:
        closing_dir = closing_dir.normalized()
    return {"position": last.lerp(first, closing_t), "direction": closing_dir}

func _set_car_pose(holder: Node3D, pose: Dictionary) -> void:
    var pos: Vector3 = pose["position"]
    var dir: Vector3 = pose["direction"]
    holder.position = pos
    holder.rotation.y = atan2(dir.x, dir.z)

func _refresh_train_visual(train_index: int) -> void:
    if train_index < 0 or train_index >= trains.size():
        return
    var train: Dictionary = trains[train_index]
    var line: Dictionary = lines[int(train["line"])]
    var head_distance: float = float(train["distance"])
    var cars: Array = train["cars"]
    for car_index in range(cars.size()):
        var holder: Node3D = cars[car_index]
        var pose: Dictionary = _sample_line(line, head_distance - float(car_index) * CAR_SPACING)
        _set_car_pose(holder, pose)

func _refresh_all_visuals() -> void:
    for index in range(trains.size()):
        _refresh_train_visual(index)
    if presentation_rig != null and presentation_rig.has_method("sync_elevated_trains"):
        presentation_rig.call("sync_elevated_trains", train_visuals)

func _update_train_server(index: int, delta: float) -> void:
    var train: Dictionary = trains[index]
    var line: Dictionary = lines[int(train["line"])]
    var total: float = float(line["length"])
    var stops: Array = line["stops"]
    var dwell: float = float(train["dwell"])
    var speed: float = float(train["speed"])
    var distance: float = float(train["distance"])

    if dwell > 0.0:
        dwell = maxf(0.0, dwell - delta)
        speed = move_toward(speed, 0.0, BRAKE * delta)
        train["door_open"] = true
        if dwell <= 0.0:
            train["door_open"] = false
    else:
        var target_speed: float = MAX_SPEED
        if not stops.is_empty():
            var stop_idx: int = clampi(int(train["next_stop"]), 0, stops.size() - 1)
            var stop_distance: float = float(stops[stop_idx])
            var remaining: float = _forward_distance(distance, stop_distance, total)
            if remaining < 10.0:
                target_speed = minf(MAX_SPEED, maxf(0.25, remaining * 0.72))
            if remaining < 0.16 and speed < 0.58:
                distance = stop_distance
                speed = 0.0
                dwell = DWELL_SECONDS
                train["door_open"] = true
                train["next_stop"] = (stop_idx + 1) % stops.size()
        if dwell <= 0.0:
            if speed < target_speed:
                speed = move_toward(speed, target_speed, ACCEL * delta)
            else:
                speed = move_toward(speed, target_speed, BRAKE * delta)
            distance = _wrap_distance(distance + speed * delta, total)

    train["distance"] = distance
    train["target_distance"] = distance
    train["speed"] = speed
    train["dwell"] = dwell
    trains[index] = train

func _update_train_client(index: int, delta: float) -> void:
    var train: Dictionary = trains[index]
    var line: Dictionary = lines[int(train["line"])]
    var total: float = float(line["length"])
    var current: float = float(train["distance"])
    var target: float = float(train["target_distance"])
    var forward_gap: float = _forward_distance(current, target, total)
    if forward_gap > total * 0.5:
        current = target
    else:
        current = _wrap_distance(current + minf(forward_gap, maxf(0.15, float(train["speed"]) * delta + 0.35)), total)
    train["distance"] = current
    trains[index] = train

@rpc("authority", "call_remote", "unreliable")
func _sync_train_state(index: int, distance: float, speed: float, dwell: float, next_stop: int, door_open: bool) -> void:
    if index < 0 or index >= trains.size():
        return
    var train: Dictionary = trains[index]
    train["target_distance"] = distance
    train["speed"] = speed
    train["dwell"] = dwell
    train["next_stop"] = next_stop
    train["door_open"] = door_open
    trains[index] = train

func _local_ear() -> Vector3:
    if host == null:
        return Vector3.ZERO
    var local_id: int = multiplayer.get_unique_id()
    var player_vehicle_variant: Variant = host.get("player_vehicle")
    var vehicles_variant: Variant = host.get("vehicles")
    var players_variant: Variant = host.get("players")
    if player_vehicle_variant is Dictionary and vehicles_variant is Dictionary:
        var player_vehicle: Dictionary = player_vehicle_variant
        var vehicles: Dictionary = vehicles_variant
        if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
            return (vehicles[player_vehicle[local_id]] as Node3D).position
    if players_variant is Dictionary:
        var players: Dictionary = players_variant
        if players.has(local_id):
            return (players[local_id] as Node3D).position
    return Vector3.ZERO

func _update_audio() -> void:
    var ear: Vector3 = _local_ear()
    for index in range(trains.size()):
        var train: Dictionary = trains[index]
        var line: Dictionary = lines[int(train["line"])]
        var pose: Dictionary = _sample_line(line, float(train["distance"]))
        var pos: Vector3 = pose["position"]
        var distance: float = Vector2(pos.x - ear.x, pos.z - ear.z).length()
        var nearness: float = 1.0 - clampf(distance / 68.0, 0.0, 1.0)
        var speed_ratio: float = clampf(float(train["speed"]) / MAX_SPEED, 0.0, 1.0)
        var rumble: AudioStreamPlayer = train["rumble"]
        var clack: AudioStreamPlayer = train["clack"]
        var audible: bool = distance < 68.0 and speed_ratio > 0.03
        if audible:
            rumble.volume_db = lerpf(-30.0, -3.0, nearness * nearness)
            rumble.pitch_scale = 0.76 + speed_ratio * 0.48
            clack.volume_db = lerpf(-34.0, -8.0, nearness * nearness) + speed_ratio * 3.0
            clack.pitch_scale = 0.72 + speed_ratio * 0.62
            if not rumble.playing:
                rumble.play(float(index) * 0.37)
            if not clack.playing:
                clack.play(float(index) * 0.19)
        else:
            rumble.volume_db = -50.0
            clack.volume_db = -50.0

        var door_open: bool = bool(train["door_open"])
        var last_door: bool = bool(train["last_door_state"])
        if door_open != last_door and distance < 42.0:
            var door_player: AudioStreamPlayer = AudioStreamPlayer.new()
            door_player.stream = load("res://assets/audio/gta2/sfx/train_door.wav") as AudioStream
            door_player.volume_db = lerpf(-20.0, -5.0, 1.0 - clampf(distance / 42.0, 0.0, 1.0))
            add_child(door_player)
            door_player.finished.connect(door_player.queue_free)
            door_player.play()
        train["last_door_state"] = door_open
        trains[index] = train

func _server_train_impacts() -> void:
    if host == null or not multiplayer.is_server():
        return
    var vehicles_variant: Variant = host.get("vehicles")
    if not (vehicles_variant is Dictionary):
        return
    var vehicles: Dictionary = vehicles_variant
    var now_ms: int = Time.get_ticks_msec()

    for train_index in range(trains.size()):
        var train: Dictionary = trains[train_index]
        if float(train["speed"]) < 1.1:
            continue
        var cars: Array = train["cars"]
        for holder_variant: Variant in cars:
            var holder: Node3D = holder_variant
            for raw_id: Variant in vehicles.keys():
                var vehicle: Node = vehicles[raw_id]
                if vehicle == null or not is_instance_valid(vehicle) or bool(vehicle.get("is_destroyed")):
                    continue
                var vehicle_id: int = int(raw_id)
                var key: String = "%d:%d" % [train_index, vehicle_id]
                if int(_impact_until.get(key, 0)) > now_ms:
                    continue
                var delta: Vector3 = (vehicle as Node3D).position - holder.position
                delta.y = 0.0
                if delta.length() > IMPACT_RADIUS:
                    continue
                _impact_until[key] = now_ms + IMPACT_COOLDOWN_MS
                if vehicle.has_method("apply_external_impulse"):
                    var away: Vector3 = delta.normalized() if delta.length_squared() > 0.001 else Vector3.RIGHT
                    vehicle.call("apply_external_impulse", away * (2.8 + float(train["speed"]) * 0.55))
                if host.has_method("_damage_vehicle"):
                    host.call("_damage_vehicle", vehicle_id, clampi(28 + roundi(float(train["speed"]) * 7.0), 32, 78), 0)

func _physics_process(delta: float) -> void:
    if trains.is_empty():
        return
    if multiplayer.is_server():
        for index in range(trains.size()):
            _update_train_server(index, delta)
        _sync_accum += delta
        if _sync_accum >= SYNC_INTERVAL:
            _sync_accum = 0.0
            for index in range(trains.size()):
                var train: Dictionary = trains[index]
                _sync_train_state.rpc(index, float(train["distance"]), float(train["speed"]), float(train["dwell"]), int(train["next_stop"]), bool(train["door_open"]))
        _server_train_impacts()
    else:
        for index in range(trains.size()):
            _update_train_client(index, delta)
    _refresh_all_visuals()
    _update_audio()

func get_train_visuals() -> Dictionary:
    return train_visuals
'''
(root / "scripts" / "train_system.gd").write_text(train_gd, encoding="utf-8")

# ---------------------------------------------------------------------------
# Main wiring.
# ---------------------------------------------------------------------------
main_path = root / "scripts" / "main.gd"
main = main_path.read_text(encoding="utf-8")

def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    hits = text.count(old)
    if hits < count:
        raise SystemExit(f"Missing v0.6.18.34 anchor {label}: found {hits}, need {count}")
    return text.replace(old, new, count)

def func_span(text: str, name: str):
    match = re.search(rf"(?m)^func {re.escape(name)}\s*\(", text)
    if match is None:
        raise SystemExit(f"Missing function {name}")
    start = match.start()
    nxt = re.search(r"(?m)^func [A-Za-z0-9_]+\s*\(", text[match.end():])
    end = len(text) if nxt is None else match.end() + nxt.start()
    return start, end

def insert_before_func(text: str, name: str, addition: str):
    start, _ = func_span(text, name)
    return text[:start] + addition.rstrip() + "\n\n" + text[start:]

main = must_replace(
    main,
    "var train_system:",
    "var train_system:",
    "existing train field",
) if "var train_system:" in main else main.replace(
    "var gta2_vehicle_light_root: Node3D\n",
    "var gta2_vehicle_light_root: Node3D\nvar train_system: Node\n",
    1,
)

build_train = r'''func _build_train_system() -> void:
    if train_system != null and is_instance_valid(train_system):
        return
    var script: Script = load("res://scripts/train_system.gd") as Script
    if script == null:
        push_warning("Train system script missing")
        return
    train_system = script.new()
    train_system.name = "ViceQuestTrainSystem"
    add_child(train_system)
    train_system.call("configure", self, DOWNTOWN_DATA.TILE_SIZE, DOWNTOWN_DATA.HEIGHT_UNIT, presentation_rig)
'''
main = insert_before_func(main, "_build_gta2_lighting_system", build_train)

if "    _build_gta2_lighting_system()\n" not in main:
    raise SystemExit("Missing lighting build call for train init")
main = main.replace(
    "    _build_gta2_lighting_system()\n",
    "    _build_gta2_lighting_system()\n    _build_train_system()\n",
    1,
)

# ---------------------------------------------------------------------------
# Quest pop-out train clones.
# ---------------------------------------------------------------------------
rig_path = root / "scripts" / "presentation_rig.gd"
rig = rig_path.read_text(encoding="utf-8")
if "var popout_trains:" not in rig:
    rig = rig.replace(
        "var popout_vehicles: Dictionary = {}\n",
        "var popout_vehicles: Dictionary = {}\nvar popout_trains: Dictionary = {}\n",
        1,
    )

def rig_func_span(text: str, name: str):
    m = re.search(rf"(?m)^func {re.escape(name)}\s*\(", text)
    if m is None:
        raise SystemExit(f"Missing rig function {name}")
    start = m.start()
    nxt = re.search(r"(?m)^func [A-Za-z0-9_]+\s*\(", text[m.end():])
    end = len(text) if nxt is None else m.end() + nxt.start()
    return start, end

def rig_insert(text: str, name: str, addition: str):
    start, _ = rig_func_span(text, name)
    return text[:start] + addition.rstrip() + "\n\n" + text[start:]

rig_train = r'''func sync_elevated_trains(train_nodes: Dictionary) -> void:
    if not xr_active or popout_root == null or not popout_enabled:
        _clear_elevated_trains()
        return
    var desired: Dictionary = {}
    for raw_id: Variant in train_nodes.keys():
        var id: int = int(raw_id)
        var holder_src: Node = train_nodes[raw_id]
        if holder_src == null or not is_instance_valid(holder_src):
            continue
        var src: Sprite3D = holder_src.get_node_or_null("Body") as Sprite3D
        if src == null or src.texture == null:
            continue
        # Railway/station decks at elevated Y should physically rise out of the
        # Quest tabletop. Ground-level trains remain in the flat viewport.
        if holder_src.global_position.y < ELEVATED_PAWN_MIN_Y:
            src.visible = true
            continue
        desired[id] = true
        var clone: Sprite3D = popout_trains.get(id) as Sprite3D
        if clone == null or not is_instance_valid(clone):
            clone = _make_flat_sprite("ElevatedTrain_%d" % id)
            popout_root.add_child(clone)
            popout_trains[id] = clone
        _copy_flat_sprite(clone, src)
        src.visible = false

    for raw_id: Variant in popout_trains.keys():
        if desired.has(raw_id):
            continue
        _free_elevated_train(raw_id)

func _free_elevated_train(raw_id: Variant) -> void:
    if not popout_trains.has(raw_id):
        return
    var clone: Node = popout_trains[raw_id]
    if is_instance_valid(clone):
        if clone.has_meta("source_sprite"):
            var src: Variant = clone.get_meta("source_sprite")
            if src is SpriteBase3D and is_instance_valid(src):
                (src as SpriteBase3D).visible = true
        clone.queue_free()
    popout_trains.erase(raw_id)

func _clear_elevated_trains() -> void:
    var ids: Array = popout_trains.keys()
    for raw_id: Variant in ids:
        _free_elevated_train(raw_id)
'''
rig = rig_insert(rig, "sync_elevated_vehicles", rig_train)
rig_path.write_text(rig, encoding="utf-8")

# ---------------------------------------------------------------------------
# Skull-coin cleanup: braking now uses the actual dual streak texture.
# ---------------------------------------------------------------------------
combat_path = root / "scripts" / "combat_fx.gd"
combat = combat_path.read_text(encoding="utf-8")
old = '''    if braking and not sliding:
        var blob: Texture2D = _gta_tex("skid_blob")
        if blob != null:
            _spawn_gta_decal(blob, world_position, yaw + randf_range(-8.0, 8.0), 0.040, 4.2, 0.62, "skid")
        return

    var streak: Texture2D = _gta_tex("skid")
'''
new = '''    var streak: Texture2D = _gta_tex("skid")
    if braking and not sliding:
        if streak == null:
            return
        var brake_side: Vector3 = Vector3(-flat.z, 0.0, flat.x)
        for offset in [-0.34, 0.34]:
            _spawn_gta_decal(streak, world_position + brake_side * offset, yaw, 0.040, 5.0, 0.70, "skid")
        return

    var streak: Texture2D = _gta_tex("skid")
'''
if old not in combat:
    raise SystemExit("18.34 skull-coin skid anchor missing")
combat = combat.replace(old, new, 1)
# Collapse accidental duplicate declaration introduced by branch replacement.
combat = combat.replace(
    '    var streak: Texture2D = _gta_tex("skid")\n    if streak == null:\n        return\n    var streak: Texture2D = _gta_tex("skid")\n',
    '    var streak: Texture2D = _gta_tex("skid")\n',
)
combat_path.write_text(combat, encoding="utf-8")

# Verify expected generated artifacts and source wiring.
checks = [
    (train_out / "train_cab.png").is_file(),
    (train_out / "train_passenger.png").is_file(),
    (train_out / "downtown_train_routes.json").is_file(),
    (audio_out / "train_rumble.wav").is_file(),
    "func _build_train_system" in main,
    "res://scripts/train_system.gd" in main,
    "func sync_elevated_trains" in rig,
    "class_name ViceQuestTrainSystem" in train_gd,
    "PASSENGER_WAGONS: int = 3" in train_gd,
    "skid_blob" not in combat[combat.find("func play_skid_mark"):combat.find("func play_crash_sparks")],
]
if not all(checks):
    raise SystemExit("v0.6.18.34 verification failed")

main_path.write_text(main, encoding="utf-8")
print(
    "Applied v0.6.18.34 train core:",
    len(rail), "rail cells;",
    [len(line["points"]) for line in lines_out], "route points;",
    [len(line["stops"]) for line in lines_out], "stops;",
    "train sprites", {k: v["sprite_count"] for k,v in manifest.items()},
)
