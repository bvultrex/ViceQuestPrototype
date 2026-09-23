#!/usr/bin/env python3
"""ViceQuest v0.6.18.30 GTA2 timecycle / map lights / police beacon pass.

Runs after v0.6.18.29 on the authoritative Quest branch.

Hardware feedback addressed:
- traffic engines finally work, but their audible radius is too broad
- sirens work, but police blue-light visuals are still too subtle/invisible
- GTA2-inspired day/night lighting was missing entirely

This pass also extracts the original Downtown GMP LGHT chunk when available.
The official GTA2 GMP format stores ARGB, fixed-point XYZ, radius, intensity,
shape and on/off timing per map light.
"""
from pathlib import Path
import json
import math
import re
import struct
import sys

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
vehicle_path = root / "scripts" / "vehicle.gd"
audio_path = root / "scripts" / "audio_manager.gd"
rig_path = root / "scripts" / "presentation_rig.gd"

main = main_path.read_text(encoding="utf-8")
vehicle = vehicle_path.read_text(encoding="utf-8")
audio = audio_path.read_text(encoding="utf-8")
rig = rig_path.read_text(encoding="utf-8")

def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    hits = text.count(old)
    if hits < count:
        raise SystemExit(f"Missing v0.6.18.30 anchor {label}: found {hits}, need {count}")
    return text.replace(old, new, count)

def func_span(text: str, name: str) -> tuple[int, int]:
    match = re.search(rf"(?m)^func {re.escape(name)}\s*\(", text)
    if match is None:
        raise SystemExit(f"Missing function {name}")
    start = match.start()
    next_match = re.search(r"(?m)^func [A-Za-z0-9_]+\s*\(", text[match.end():])
    end = len(text) if next_match is None else match.end() + next_match.start()
    return start, end

def get_func(text: str, name: str) -> str:
    start, end = func_span(text, name)
    return text[start:end]

def replace_func(text: str, name: str, replacement: str) -> str:
    start, end = func_span(text, name)
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]

def insert_before_func(text: str, name: str, addition: str) -> str:
    start, _ = func_span(text, name)
    return text[:start] + addition.rstrip() + "\n\n" + text[start:]

# ---------------------------------------------------------------------------
# 1) Shorter traffic engine range. Hardware 18.29 proved the unique-WAV path.
# ---------------------------------------------------------------------------
traffic = get_func(audio, "update_nearby_traffic")
if traffic.count("58.0") < 2:
    raise SystemExit("Unexpected v0.6.18.29 traffic radius layout")
traffic = traffic.replace("58.0", "36.0")
traffic = traffic.replace("lerpf(-13.0, 0.0, pow(nearness, 1.18))", "lerpf(-14.0, -1.0, pow(nearness, 1.22))")
audio = replace_func(audio, "update_nearby_traffic", traffic)

# ---------------------------------------------------------------------------
# 2) Extract original GTA2 map lights from the GMP LGHT chunk.
# ---------------------------------------------------------------------------
out_dir = root / "assets" / "gta2" / "downtown"
out_dir.mkdir(parents=True, exist_ok=True)
lights_out = out_dir / "downtown_lights.json"

def fixed_1_8_7(raw: int) -> float:
    # Signed 16-bit 1.8.7 fixed point used by GTA2 map objects/lights.
    if raw >= 0x8000:
        raw -= 0x10000
    return float(raw) / 128.0

def parse_lght(blob: bytes) -> list[dict]:
    found = []
    cursor = 0
    while True:
        pos = blob.find(b"LGHT", cursor)
        if pos < 0 or pos + 8 > len(blob):
            break
        size = struct.unpack_from("<I", blob, pos + 4)[0]
        start = pos + 8
        end = start + size
        if 0 < size <= len(blob) - start and size % 16 == 0:
            for offset in range(start, end, 16):
                argb = struct.unpack_from("<I", blob, offset)[0]
                x_raw, y_raw, z_raw, radius_raw = struct.unpack_from("<4H", blob, offset + 4)
                intensity, shape, on_time, off_time = struct.unpack_from("<4B", blob, offset + 12)
                a = (argb >> 24) & 0xFF
                r = (argb >> 16) & 0xFF
                g = (argb >> 8) & 0xFF
                b = argb & 0xFF
                found.append({
                    "x": fixed_1_8_7(x_raw),
                    "y": fixed_1_8_7(y_raw),
                    "z": fixed_1_8_7(z_raw),
                    "radius": max(0.10, abs(fixed_1_8_7(radius_raw))),
                    "intensity": int(intensity),
                    "shape": int(shape),
                    "on_time": int(on_time),
                    "off_time": int(off_time),
                    "r": int(r), "g": int(g), "b": int(b), "a": int(a),
                })
            return found
        cursor = pos + 4
    return found

gmp_candidates = sorted(root.rglob("*.gmp"), key=lambda p: (0 if p.name.lower() == "wil.gmp" else 1, len(str(p))))
map_lights: list[dict] = []
source_name = ""
for candidate in gmp_candidates:
    try:
        parsed = parse_lght(candidate.read_bytes())
    except OSError:
        parsed = []
    if parsed:
        map_lights = parsed
        source_name = str(candidate.relative_to(root))
        break

# Some source packs keep parsed map metadata but omit the original GMP.
# Accept an existing light list if one has already been preserved there.
if not map_lights:
    exact_map = out_dir / "downtown_exact_map.json"
    if exact_map.is_file():
        try:
            exact = json.loads(exact_map.read_text(encoding="utf-8"))
        except Exception:
            exact = {}
        for key in ("lights", "map_lights", "point_lights"):
            value = exact.get(key) if isinstance(exact, dict) else None
            if isinstance(value, list) and value:
                for entry in value:
                    if not isinstance(entry, dict):
                        continue
                    if all(k in entry for k in ("x", "y")):
                        map_lights.append({
                            "x": float(entry.get("x", 0.0)),
                            "y": float(entry.get("y", 0.0)),
                            "z": float(entry.get("z", 0.0)),
                            "radius": float(entry.get("radius", 1.0)),
                            "intensity": int(entry.get("intensity", 180)),
                            "shape": int(entry.get("shape", 0)),
                            "on_time": int(entry.get("on_time", 0)),
                            "off_time": int(entry.get("off_time", 0)),
                            "r": int(entry.get("r", 255)),
                            "g": int(entry.get("g", 220)),
                            "b": int(entry.get("b", 160)),
                            "a": int(entry.get("a", 0)),
                        })
                if map_lights:
                    source_name = f"downtown_exact_map.json:{key}"
                    break

lights_out.write_text(json.dumps({"source": source_name, "lights": map_lights}, separators=(",", ":")), encoding="utf-8")
print(f"v0.6.18.30: extracted {len(map_lights)} GTA2 map lights from {source_name or 'no preserved LGHT source'}")

# ---------------------------------------------------------------------------
# 3) Quest timecycle tint. Base game viewport darkens independently from UI.
#    Pop-out buildings/pawns/vehicles receive the same night tint.
# ---------------------------------------------------------------------------
rig = must_replace(
    rig,
    "var popout_enabled: bool = false\n",
    "var popout_enabled: bool = false\nvar night_overlay: ColorRect\nvar gta2_night_factor: float = 0.0\nvar gta2_world_tint: Color = Color.WHITE\n",
    "rig night fields",
)

viewport_func = get_func(rig, "_build_quest_game_viewport")
viewport_func = must_replace(
    viewport_func,
    "    game_viewport.add_child(camera)\n",
    """    game_viewport.add_child(camera)

    var night_layer: CanvasLayer = CanvasLayer.new()
    night_layer.name = "GTA2NightTintLayer"
    night_layer.layer = 90
    game_viewport.add_child(night_layer)
    night_overlay = ColorRect.new()
    night_overlay.name = "GTA2NightTint"
    night_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    night_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
    night_overlay.color = Color(0.005, 0.012, 0.030, 0.0)
    night_layer.add_child(night_overlay)
""",
    "Quest night overlay",
)
rig = replace_func(rig, "_build_quest_game_viewport", viewport_func)

popout_func = get_func(rig, "_ensure_popout_material")
popout_func = must_replace(
    popout_func,
    "uniform float min_world_y = 0.08;\n",
    "uniform float min_world_y = 0.08;\nuniform float night_strength = 0.0;\n",
    "popout night uniform",
)
popout_func = must_replace(
    popout_func,
    "    ALBEDO = texel.rgb;\n",
    "    vec3 night_tint = mix(vec3(1.0), vec3(0.42, 0.50, 0.68), night_strength);\n    ALBEDO = texel.rgb * night_tint;\n",
    "popout night tint",
)
popout_func = must_replace(
    popout_func,
    '    popout_material.set_shader_parameter("min_world_y", QUEST_POP_OUT_MIN_Y)\n',
    '    popout_material.set_shader_parameter("min_world_y", QUEST_POP_OUT_MIN_Y)\n    popout_material.set_shader_parameter("night_strength", gta2_night_factor)\n',
    "popout night init",
)
rig = replace_func(rig, "_ensure_popout_material", popout_func)

rig_helpers = r'''func set_gta2_time_of_day(_hour: float, night_factor: float) -> void:
    gta2_night_factor = clampf(night_factor, 0.0, 1.0)
    gta2_world_tint = Color(
        lerpf(1.0, 0.42, gta2_night_factor),
        lerpf(1.0, 0.50, gta2_night_factor),
        lerpf(1.0, 0.68, gta2_night_factor),
        1.0
    )
    if night_overlay != null:
        night_overlay.color = Color(0.005, 0.012, 0.030, gta2_night_factor * 0.58)
    if popout_material != null:
        popout_material.set_shader_parameter("night_strength", gta2_night_factor)

func _night_modulate(source: Color) -> Color:
    return Color(
        source.r * gta2_world_tint.r,
        source.g * gta2_world_tint.g,
        source.b * gta2_world_tint.b,
        source.a
    )
'''
rig = insert_before_func(rig, "_build_quest_display", rig_helpers)

pawn_copy = get_func(rig, "_copy_elevated_pawn")
pawn_copy = must_replace(pawn_copy, "    clone.modulate = src.modulate\n", "    clone.modulate = _night_modulate(src.modulate)\n", "pawn night tint")
rig = replace_func(rig, "_copy_elevated_pawn", pawn_copy)

flat_copy = get_func(rig, "_copy_flat_sprite")
flat_copy = must_replace(
    flat_copy,
    "    clone.modulate = flat.modulate\n",
    '    clone.modulate = flat.modulate if clone.name == "PoliceLight" else _night_modulate(flat.modulate)\n',
    "vehicle night tint",
)
rig = replace_func(rig, "_copy_flat_sprite", flat_copy)

# ---------------------------------------------------------------------------
# 4) Main GTA2 clock plus pooled original map-light coronas.
# ---------------------------------------------------------------------------
main = must_replace(
    main,
    "var gta2_vehicle_name_tween: Tween\n",
    """var gta2_vehicle_name_tween: Tween
const GTA2_DAY_CYCLE_SECONDS: float = 720.0
const GTA2_MAP_LIGHT_POOL: int = 36
const GTA2_MAP_LIGHT_RANGE: float = 44.0
var gta2_clock_hours: float = 17.5
var gta2_night_factor: float = 0.0
var gta2_map_light_defs: Array = []
var gta2_map_light_pool: Array[Sprite3D] = []
var gta2_map_light_texture: Texture2D
var gta2_map_light_root: Node3D
var gta2_map_light_accumulator: float = 0.0
""",
    "main timecycle fields",
)

lighting_helpers = r'''func _smooth_time(a: float, b: float, value: float) -> float:
    var t: float = clampf((value - a) / maxf(0.001, b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

func _night_for_hour(hour: float) -> float:
    if hour >= 20.0 or hour < 5.0:
        return 1.0
    if hour >= 18.0:
        return _smooth_time(18.0, 20.0, hour)
    if hour < 7.0:
        return 1.0 - _smooth_time(5.0, 7.0, hour)
    return 0.0

func _build_gta2_light_texture() -> Texture2D:
    var size: int = 64
    var image: Image = Image.create(size, size, false, Image.FORMAT_RGBA8)
    var center: Vector2 = Vector2(float(size - 1) * 0.5, float(size - 1) * 0.5)
    var radius: float = float(size) * 0.5
    for y in range(size):
        for x in range(size):
            var distance: float = Vector2(float(x), float(y)).distance_to(center) / radius
            var alpha: float = pow(maxf(0.0, 1.0 - distance), 2.25)
            image.set_pixel(x, y, Color(1.0, 1.0, 1.0, alpha))
    return ImageTexture.create_from_image(image)

func _build_gta2_lighting_system() -> void:
    gta2_map_light_texture = _build_gta2_light_texture()
    gta2_map_light_root = Node3D.new()
    gta2_map_light_root.name = "GTA2OriginalMapLights"
    add_child(gta2_map_light_root)

    var path: String = "res://assets/gta2/downtown/downtown_lights.json"
    if FileAccess.file_exists(path):
        var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
        if parsed is Dictionary:
            var raw_lights: Variant = (parsed as Dictionary).get("lights", [])
            if raw_lights is Array:
                gta2_map_light_defs = raw_lights

    for index in range(GTA2_MAP_LIGHT_POOL):
        var glow: Sprite3D = Sprite3D.new()
        glow.name = "GTA2MapLight_%02d" % index
        glow.texture = gta2_map_light_texture
        glow.shaded = false
        glow.centered = true
        glow.double_sided = true
        glow.no_depth_test = true
        glow.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
        glow.render_priority = 11
        glow.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
        glow.rotation_degrees.x = -90.0
        glow.visible = false
        gta2_map_light_root.add_child(glow)
        gta2_map_light_pool.append(glow)

func _map_light_active(definition: Dictionary, light_index: int) -> bool:
    var on_time: int = int(definition.get("on_time", 0))
    var off_time: int = int(definition.get("off_time", 0))
    if on_time <= 0 or off_time <= 0:
        return true
    var cycle: int = maxi(1, on_time + off_time)
    var tick: int = int(Time.get_ticks_msec() / 45) + light_index * 17
    return posmod(tick, cycle) < on_time

func _update_gta2_map_lights() -> void:
    if gta2_map_light_pool.is_empty():
        return
    if gta2_night_factor <= 0.03 or gta2_map_light_defs.is_empty():
        for glow in gta2_map_light_pool:
            glow.visible = false
        return

    var local_id: int = multiplayer.get_unique_id()
    var center: Vector3 = Vector3.ZERO
    if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
        center = vehicles[player_vehicle[local_id]].position
    elif players.has(local_id):
        center = players[local_id].position

    var chosen: Array = []
    for light_index in range(gta2_map_light_defs.size()):
        var definition: Dictionary = gta2_map_light_defs[light_index]
        if not _map_light_active(definition, light_index):
            continue
        # GTA2 map coordinates are blocks. ViceQuest uses 2.8 world units per
        # map block horizontally and 0.6 per vertical level.
        var world_position: Vector3 = Vector3(
            float(definition.get("x", 0.0)) * 2.8,
            maxf(0.055, float(definition.get("z", 0.0)) * 0.6 + 0.055),
            float(definition.get("y", 0.0)) * 2.8
        )
        var distance: float = Vector2(world_position.x - center.x, world_position.z - center.z).length()
        if distance > GTA2_MAP_LIGHT_RANGE:
            continue
        var entry: Dictionary = {"index": light_index, "distance": distance, "position": world_position}
        var inserted: bool = false
        for slot in range(chosen.size()):
            if distance < float((chosen[slot] as Dictionary)["distance"]):
                chosen.insert(slot, entry)
                inserted = true
                break
        if not inserted:
            chosen.append(entry)
        while chosen.size() > GTA2_MAP_LIGHT_POOL:
            chosen.pop_back()

    for pool_index in range(gta2_map_light_pool.size()):
        var glow: Sprite3D = gta2_map_light_pool[pool_index]
        if pool_index >= chosen.size():
            glow.visible = false
            continue
        var selected: Dictionary = chosen[pool_index]
        var definition: Dictionary = gta2_map_light_defs[int(selected["index"])]
        glow.position = selected["position"]
        var radius_blocks: float = clampf(float(definition.get("radius", 1.0)), 0.25, 8.0)
        var world_radius: float = radius_blocks * 2.8
        glow.pixel_size = maxf(0.008, (world_radius * 2.0) / 64.0)
        var intensity: float = clampf(float(definition.get("intensity", 180)) / 255.0, 0.15, 1.0)
        var color: Color = Color(
            float(definition.get("r", 255)) / 255.0,
            float(definition.get("g", 220)) / 255.0,
            float(definition.get("b", 160)) / 255.0,
            clampf(gta2_night_factor * intensity * 0.86, 0.0, 0.92)
        )
        glow.modulate = color
        glow.visible = true

func _update_gta2_timecycle(delta: float) -> void:
    gta2_clock_hours = fmod(gta2_clock_hours + delta * (24.0 / GTA2_DAY_CYCLE_SECONDS), 24.0)
    gta2_night_factor = _night_for_hour(gta2_clock_hours)
    if presentation_rig != null and presentation_rig.has_method("set_gta2_time_of_day"):
        presentation_rig.call("set_gta2_time_of_day", gta2_clock_hours, gta2_night_factor)
    gta2_map_light_accumulator += delta
    if gta2_map_light_accumulator >= 0.18:
        gta2_map_light_accumulator = 0.0
        _update_gta2_map_lights()
'''
main = insert_before_func(main, "_build_wasted_overlay", lighting_helpers)

main = must_replace(
    main,
    "func _process(delta: float) -> void:\n",
    "func _process(delta: float) -> void:\n    _update_gta2_timecycle(delta)\n",
    "timecycle process",
)

# Build the light pool once after the camera/presentation rig exists.
if main.count("    _build_camera()\n") != 1:
    raise SystemExit(f"Expected one _build_camera() call, found {main.count('    _build_camera()\n')}")
main = main.replace("    _build_camera()\n", "    _build_camera()\n    _build_gta2_lighting_system()\n", 1)

# ---------------------------------------------------------------------------
# 5) Make police beacon unmistakably blue. The old thin 24x7 bar could be
#    swallowed by top-down scale. Use a larger soft blue roof corona.
# ---------------------------------------------------------------------------
beacon = r'''func _build_police_lightbar() -> Sprite3D:
    var size: int = 48
    var image: Image = Image.create(size, size, false, Image.FORMAT_RGBA8)
    var center: Vector2 = Vector2(float(size - 1) * 0.5, float(size - 1) * 0.5)
    var radius: float = float(size) * 0.5
    for y in range(size):
        for x in range(size):
            var distance: float = Vector2(float(x), float(y)).distance_to(center) / radius
            var halo: float = pow(maxf(0.0, 1.0 - distance), 2.15)
            var core: float = 1.0 if absf(float(x) - center.x) < 8.0 and absf(float(y) - center.y) < 3.0 else 0.0
            var alpha: float = clampf(halo * 0.82 + core * 0.45, 0.0, 1.0)
            image.set_pixel(x, y, Color(0.08 + core * 0.55, 0.32 + core * 0.42, 1.0, alpha))
    var texture: ImageTexture = ImageTexture.create_from_image(image)
    var light: Sprite3D = Sprite3D.new()
    light.name = "PoliceLightbar"
    light.texture = texture
    light.shaded = false
    light.centered = true
    light.double_sided = true
    light.no_depth_test = true
    light.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
    light.render_priority = 18
    light.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    if _sprite != null:
        light.transform = _sprite.transform
        light.position.y += 0.22
        light.pixel_size = maxf(_sprite.pixel_size * 1.25, 0.024)
        light.layers = _sprite.layers
    else:
        light.rotation_degrees.x = -90.0
        light.position.y = 0.24
        light.pixel_size = 0.030
    add_child(light)
    var flash: Tween = create_tween()
    flash.set_loops()
    flash.tween_property(light, "modulate", Color(0.45, 0.72, 1.0, 1.0), 0.105)
    flash.tween_property(light, "modulate", Color(0.04, 0.18, 1.0, 0.26), 0.105)
    return light
'''
vehicle = replace_func(vehicle, "_build_police_lightbar", beacon)

checks = [
    ("distance > 36.0", audio),
    ("chosen_dist[index] / 36.0", audio),
    ("func set_gta2_time_of_day", rig),
    ("GTA2NightTint", rig),
    ("night_strength", rig),
    ("const GTA2_DAY_CYCLE_SECONDS", main),
    ("func _update_gta2_map_lights", main),
    ("downtown_lights.json", main),
    ("func _build_police_lightbar", vehicle),
    ("var size: int = 48", vehicle),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"v0.6.18.30 verification failed: {needle}")

if "AudioStreamPlayer3D" in audio:
    raise SystemExit("v0.6.18.30 must stay on the proven manual Ear mixer")

main_path.write_text(main, encoding="utf-8")
vehicle_path.write_text(vehicle, encoding="utf-8")
audio_path.write_text(audio, encoding="utf-8")
rig_path.write_text(rig, encoding="utf-8")
print("Applied v0.6.18.30: tighter traffic audio, original GTA2 map-light extraction, timecycle/night tint and stronger blue beacon.")
