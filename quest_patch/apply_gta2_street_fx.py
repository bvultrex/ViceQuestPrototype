#!/usr/bin/env python3
"""v0.6.18.24 — GTA2 street FX, bleed-out and the Elvis line.

Sprites are code objects from wil.sty, checked by color so a blood spray
cannot be shipped as a spark:

  290 thin skid streak, 292 brake blob
  2 / 4-6 / 497-502 blood hit, spray and the growing pool
  106-109 yellow crash sparks
  0 puff, 1 muzzle flash, 326 casing
  368-375 car explosion
  ped remap 12 Elvis jumpsuit

No city mesh changes. Tire marks only drop while the driven car is actually
sliding or braking, spaced along the track.
"""
from pathlib import Path
import struct
import sys

from PIL import Image

root = Path(sys.argv[1]).resolve()
sty_path = root / "source_gta2" / "wil.sty"
if not sty_path.exists():
    raise SystemExit(f"Missing {sty_path}")


def read(rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (root / rel).write_text(text, encoding="utf-8")


def replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing street-fx anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"Street-fx anchor is not unique: {label}")
    return text.replace(old, new, 1)


blob = sty_path.read_bytes()
chunks = {}
pos = 6
while pos + 8 <= len(blob):
    kind = blob[pos : pos + 4].decode("latin1")
    size = struct.unpack_from("<I", blob, pos + 4)[0]
    chunks[kind] = (pos + 8, size)
    pos += 8 + size

spg, _ = chunks["SPRG"]
sprx, _ = chunks["SPRX"]
palx, _ = chunks["PALX"]
ppal, _ = chunks["PPAL"]
sprb, _ = chunks["SPRB"]
palb, _ = chunks["PALB"]
counts = struct.unpack_from("<6H", blob, sprb)
bases = []
total = 0
for count in counts:
    bases.append(total)
    total += count
pal_counts = struct.unpack_from("<8H", blob, palb)
pal_bases = []
total = 0
for count in pal_counts:
    pal_bases.append(total)
    total += count
code_base = bases[2]
ped_base = bases[1]
sprite_virt = pal_bases[1]
ped_remap = pal_bases[3]


def rgba(phys: int, color: int):
    idx = (phys // 64) * 64 * 256 + (phys % 64) + color * 64
    value = struct.unpack_from("<I", blob, ppal + idx * 4)[0]
    return ((value >> 16) & 255, (value >> 8) & 255, value & 255, 0 if color == 0 else 255)


def sprite(num: int, virt: int) -> Image.Image:
    ptr, width, height, _pad = struct.unpack_from("<IBBH", blob, sprx + num * 8)
    phys = struct.unpack_from("<H", blob, palx + virt * 2)[0]
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = image.load()
    for y in range(height):
        row = spg + ptr + y * 256
        for x in range(width):
            pixels[x, y] = rgba(phys, blob[row + x])
    return image


def mean_rgb(image: Image.Image):
    pixels = [p for p in image.getdata() if p[3] > 40]
    if not pixels:
        return (0, 0, 0)
    count = len(pixels)
    return (
        sum(p[0] for p in pixels) // count,
        sum(p[1] for p in pixels) // count,
        sum(p[2] for p in pixels) // count,
    )


fx_dir = root / "assets" / "gta2" / "fx"
fx_dir.mkdir(parents=True, exist_ok=True)
CODE_SPRITES = {
    "puff": 0,
    "muzzle": 1,
    "blood_hit": 2,
    "blood_spray_0": 4,
    "blood_spray_1": 5,
    "blood_spray_2": 6,
    "spark_0": 106,
    "spark_1": 107,
    "spark_2": 108,
    "spark_3": 109,
    "skid": 290,
    "skid_blob": 292,
    "casing": 326,
    "blood_0": 497,
    "blood_1": 498,
    "blood_2": 499,
    "blood_3": 500,
    "blood_4": 501,
    "blood_5": 502,
}
for index, rel in enumerate(range(368, 376)):
    CODE_SPRITES["boom_%d" % index] = rel
for name, rel in CODE_SPRITES.items():
    sprite(code_base + rel, sprite_virt + code_base + rel).save(fx_dir / f"{name}.png")

spark_rgb = mean_rgb(Image.open(fx_dir / "spark_0.png"))
blood_rgb = mean_rgb(Image.open(fx_dir / "blood_hit.png"))
skid_image = Image.open(fx_dir / "skid.png")
if spark_rgb[0] < 180 or spark_rgb[1] < 180 or spark_rgb[2] > 90:
    raise SystemExit(f"spark_0 is not the yellow GTA2 spark: {spark_rgb}")
if blood_rgb[0] < 120 or blood_rgb[1] > 50:
    raise SystemExit(f"blood_hit is not red: {blood_rgb}")
if skid_image.size[0] < skid_image.size[1] * 4:
    raise SystemExit(f"skid streak is not a tire line: {skid_image.size}")

ANIMS = {
    "idle": list(range(53, 57)),
    "walk": list(range(0, 8)),
    "run": list(range(8, 16)),
    "jump": list(range(16, 24)),
    "armed_walk": list(range(37, 45)),
    "armed_run": list(range(45, 53)),
    "idle_alt_a": list(range(65, 73)),
    "idle_alt_b": list(range(73, 81)),
    "death": list(range(81, 98)),
    "shoot": [139],
    "electrocute": list(range(151, 156)),
}
elvis_dir = root / "assets" / "gta2" / "peds" / "animated" / "skin_12" / "type_0"
elvis_dir.mkdir(parents=True, exist_ok=True)
elvis_virt = ped_remap + 12
for anim_name, offsets in ANIMS.items():
    frames = []
    for rel in offsets:
        frame = sprite(ped_base + rel, elvis_virt)
        canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        canvas.alpha_composite(frame, ((32 - frame.width) // 2, (32 - frame.height) // 2))
        frames.append(canvas)
    sheet = Image.new("RGBA", (32 * len(frames), 32), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * 32, 0))
    sheet.save(elvis_dir / f"{anim_name}.png")

ped = read("scripts/ped_animation.gd")
ped = replace(ped, "clampi(skin_index, 0, 11)", "clampi(skin_index, 0, 12)", "elvis skin clamp")
write("scripts/ped_animation.gd", ped)

civilian = read("scripts/civilian.gd")
civilian = replace(
    civilian,
    "var gang_id: int = 0\n",
    "var gang_id: int = 0\nvar forced_skin: int = -1\n",
    "forced skin field",
)
civilian = replace(
    civilian,
    """func _skin_index() -> int:
    if gang_id > 0:
        return int(GANG_DATA.skin_for(gang_id, civilian_id))
    return posmod(civilian_id - 1, 12)
""",
    """func _skin_index() -> int:
    if forced_skin >= 0:
        return forced_skin
    if gang_id > 0:
        return int(GANG_DATA.skin_for(gang_id, civilian_id))
    return posmod(civilian_id - 1, 12)

func set_elvis() -> void:
    forced_skin = 12
    if _visual != null:
        _visual.setup(12, 0)
""",
    "elvis skin",
)
graphic_old = "        var graphic_type: int = posmod(civilian_id - 1, 3)\n"
graphic_new = "        var graphic_type: int = 0 if forced_skin >= 0 else posmod(civilian_id - 1, 3)\n"
if civilian.count(graphic_old) != 2:
    raise SystemExit(f"Expected 2 civilian graphic-type lines, found {civilian.count(graphic_old)}")
civilian = civilian.replace(graphic_old, graphic_new)
write("scripts/civilian.gd", civilian)

combat = read("scripts/combat_fx.gd")
combat = replace(
    combat,
    "var _blood_texture: Texture2D\n",
    "var _blood_texture: Texture2D\n"
    "var _gta_textures: Dictionary = {}\n"
    "var _skid_decals: Array[Node3D] = []\n"
    "var _grow_pools: Array[Node3D] = []\n"
    "var _bleed_drops: Array[Dictionary] = []\n"
    "var _last_skid: Vector3 = Vector3(99999.0, 0.0, 99999.0)\n"
    "var _boom_frames: SpriteFrames\n",
    "gta texture cache",
)
combat = replace(
    combat,
    "    _burn_effects.clear()\n",
    "    _burn_effects.clear()\n"
    "    for skid in _skid_decals:\n"
    "        if is_instance_valid(skid):\n"
    "            skid.queue_free()\n"
    "    _skid_decals.clear()\n"
    "    for pool in _grow_pools:\n"
    "        if is_instance_valid(pool):\n"
    "            pool.queue_free()\n"
    "    _grow_pools.clear()\n"
    "    _bleed_drops.clear()\n"
    "    _last_skid = Vector3(99999.0, 0.0, 99999.0)\n",
    "clear street fx",
)
combat = replace(
    combat,
    """func play_explosion_layer(world_position: Vector3, radius: float) -> void:
    var ring_size: float = clampf(radius * 0.30, 0.65, 1.75)
""",
    """func play_explosion_layer(world_position: Vector3, radius: float) -> void:
    _play_gta_boom(world_position)
    var ring_size: float = clampf(radius * 0.30, 0.65, 1.75)
""",
    "gta boom first",
)
combat = replace(
    combat,
    """func play_blood_hit(world_position: Vector3, hit_direction: Vector3, lethal: bool = false) -> void:
    var away: Vector3 = hit_direction
""",
    """func play_blood_hit(world_position: Vector3, hit_direction: Vector3, lethal: bool = false) -> void:
    var away: Vector3 = hit_direction
    away.y = 0.0
    if away.length_squared() <= 0.001:
        away = Vector3(0.707, 0.0, 0.707)
    away = away.normalized()
    if _paint_gta_blood(world_position, away, lethal):
        return
""",
    "gta blood first",
)
combat = replace(
    combat,
    """func _process(_delta: float) -> void:
    var now: float = float(Time.get_ticks_msec()) * 0.001
""",
    """func _process(delta: float) -> void:
    _service_street_fx(delta)
    var now: float = float(Time.get_ticks_msec()) * 0.001
""",
    "service street fx",
)
combat += r'''
func play_skid_mark(world_position: Vector3, forward: Vector3, speed: float = 0.0, max_speed: float = 1.0, steer_amount: float = 0.0, throttle: float = 0.0) -> void:
    var ratio: float = clampf(speed / maxf(max_speed, 0.1), 0.0, 1.0)
    var sliding: bool = ratio > 0.45 and steer_amount > 0.48
    var braking: bool = throttle < -0.28 and ratio > 0.30
    if not sliding and not braking:
        _last_skid = world_position
        return
    if _last_skid.distance_to(world_position) < (0.58 if sliding else 0.72):
        return
    _last_skid = world_position
    var flat: Vector3 = forward
    flat.y = 0.0
    if flat.length_squared() <= 0.001:
        flat = Vector3(0.0, 0.0, -1.0)
    flat = flat.normalized()
    # The streak sprite is horizontal. -90 yaw lays that axis along +Z at rest.
    var yaw: float = rad_to_deg(atan2(flat.x, flat.z)) - 90.0
    if braking and not sliding:
        var blob: Texture2D = _gta_tex("skid_blob")
        _spawn_gta_decal(blob, world_position, yaw + randf_range(-8.0, 8.0), 0.040, 6.5, 0.70, "skid")
        return
    var streak: Texture2D = _gta_tex("skid")
    if streak == null:
        return
    var side: Vector3 = Vector3(-flat.z, 0.0, flat.x)
    for offset in [-0.36, 0.36]:
        _spawn_gta_decal(streak, world_position + side * offset, yaw, 0.042, 6.0, 0.78, "skid")

func play_crash_sparks(world_position: Vector3) -> void:
    var count: int = 3 if low_power else 5
    for index in range(count):
        var tex: Texture2D = _gta_tex("spark_%d" % (index % 4))
        if tex == null:
            continue
        var jitter: Vector3 = Vector3(randf_range(-0.42, 0.42), 0.05, randf_range(-0.42, 0.42))
        _spawn_gta_decal(tex, world_position + jitter, randf_range(0.0, 360.0), randf_range(0.040, 0.062), 0.22, 1.0, "fx")
    var puff: Texture2D = _gta_tex("puff")
    if puff != null:
        _spawn_gta_decal(puff, world_position, randf_range(0.0, 360.0), 0.055, 0.45, 0.65, "fx")

func play_gun_fx(start: Vector3, end: Vector3) -> void:
    var flat: Vector3 = end - start
    flat.y = 0.0
    var yaw: float = 0.0
    if flat.length_squared() > 0.001:
        flat = flat.normalized()
        yaw = rad_to_deg(atan2(flat.x, flat.z))
    var side: Vector3 = Vector3(-flat.z, 0.0, flat.x) if flat.length_squared() > 0.5 else Vector3(1.0, 0.0, 0.0)
    var muzzle: Texture2D = _gta_tex("muzzle")
    if muzzle != null:
        _spawn_gta_decal(muzzle, start + flat * 0.28, yaw, 0.050, 0.07, 1.0, "fx")
    if not low_power:
        var casing: Texture2D = _gta_tex("casing")
        if casing != null:
            _spawn_gta_decal(casing, start - flat * 0.05 + side * 0.22, randf_range(0.0, 360.0), 0.028, 1.1, 0.9, "fx")
    if start.distance_to(end) > 0.6:
        var puff: Texture2D = _gta_tex("puff")
        if puff != null:
            _spawn_gta_decal(puff, end, randf_range(0.0, 360.0), 0.040, 0.16, 0.75, "fx")

func _paint_gta_blood(world_position: Vector3, away: Vector3, lethal: bool) -> bool:
    var hit: Texture2D = _gta_tex("blood_hit")
    var spray: Texture2D = _gta_tex("blood_spray_1" if lethal else "blood_spray_0")
    if hit == null or _gta_tex("blood_0") == null:
        return false
    _spawn_gta_decal(hit, world_position, randf_range(0.0, 360.0), 0.048 if lethal else 0.036, 0.55, 1.0, "fx")
    if spray != null:
        _spawn_gta_decal(spray, world_position + away * 0.16, randf_range(0.0, 360.0), 0.044, 0.28, 1.0, "fx")
    if lethal:
        _spawn_grow_pool(world_position + away * 0.10)
        var extra: Texture2D = _gta_tex("blood_spray_2")
        if extra != null:
            _spawn_gta_decal(extra, world_position + away * 0.34, randf_range(0.0, 360.0), 0.040, 0.34, 0.95, "fx")
        return true
    var drops: int = 2 if low_power else 4
    for index in range(drops):
        _bleed_drops.append({
            "t": 0.18 * float(index + 1),
            "pos": world_position + away * (0.26 * float(index + 1)),
            "name": "blood_0" if index < 2 else "blood_1",
            "size": 0.030 + float(index) * 0.004,
            "life": 9.0,
        })
    return true

func _spawn_grow_pool(world_position: Vector3) -> void:
    var tex: Texture2D = _gta_tex("blood_0")
    if tex == null:
        return
    var decal: Sprite3D = _make_gta_sprite(tex, world_position, randf_range(0.0, 360.0), 0.032, 1.0)
    decal.name = "FXBleed"
    decal.set_meta("grow_t", 0.0)
    decal.set_meta("grow_step", -1)
    decal.set_meta("grew", false)
    add_child(decal)
    var cap: int = 8 if low_power else 16
    while _grow_pools.size() >= cap:
        var oldest: Node3D = _grow_pools.pop_front()
        if is_instance_valid(oldest):
            oldest.queue_free()
    _grow_pools.append(decal)

func _play_gta_boom(world_position: Vector3) -> void:
    var frames: SpriteFrames = _boom_sprite_frames()
    if frames == null:
        return
    var boom: AnimatedSprite3D = AnimatedSprite3D.new()
    boom.name = "FXBoom"
    boom.sprite_frames = frames
    boom.animation = "boom"
    boom.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    boom.billboard = BaseMaterial3D.BILLBOARD_DISABLED
    boom.shaded = false
    boom.double_sided = true
    boom.rotation_degrees = Vector3(-90.0, randf_range(0.0, 360.0), 0.0)
    boom.pixel_size = 0.022
    boom.position = world_position + Vector3(0.0, 0.07, 0.0)
    add_child(boom)
    _track(boom)
    boom.animation_finished.connect(_release.bind(boom))
    boom.play("boom")
    play_crash_sparks(world_position)

func _boom_sprite_frames() -> SpriteFrames:
    if _boom_frames != null and _boom_frames.get_frame_count("boom") > 0:
        return _boom_frames
    var frames: SpriteFrames = SpriteFrames.new()
    frames.add_animation("boom")
    frames.set_animation_loop("boom", false)
    frames.set_animation_speed("boom", 14.0)
    for index in range(8):
        var tex: Texture2D = _gta_tex("boom_%d" % index)
        if tex != null:
            frames.add_frame("boom", tex)
    if frames.get_frame_count("boom") == 0:
        return null
    _boom_frames = frames
    return frames

func _service_street_fx(delta: float) -> void:
    var index: int = _bleed_drops.size() - 1
    while index >= 0:
        var drop: Dictionary = _bleed_drops[index]
        drop["t"] = float(drop["t"]) - delta
        if float(drop["t"]) <= 0.0:
            var tex: Texture2D = _gta_tex(String(drop["name"]))
            var drop_pos: Vector3 = drop["pos"] as Vector3
            _spawn_gta_decal(tex, drop_pos, randf_range(0.0, 360.0), float(drop["size"]), float(drop["life"]), 0.92, "fx")
            _bleed_drops.remove_at(index)
        index -= 1
    var dead: Array[Node3D] = []
    for pool in _grow_pools:
        if not is_instance_valid(pool):
            dead.append(pool)
            continue
        if bool(pool.get_meta("grew", false)):
            continue
        var grown: float = float(pool.get_meta("grow_t", 0.0)) + delta
        pool.set_meta("grow_t", grown)
        var step: int = clampi(int(grown / 0.16), 0, 5)
        if step != int(pool.get_meta("grow_step", -1)):
            pool.set_meta("grow_step", step)
            var tex: Texture2D = _gta_tex("blood_%d" % step)
            if tex != null:
                pool.texture = tex
            pool.pixel_size = lerpf(0.032, 0.058, float(step) / 5.0)
        if step == 5 and grown > 0.90:
            pool.set_meta("grew", true)
            var tween: Tween = create_tween()
            tween.tween_interval(11.0 if low_power else 16.0)
            tween.tween_property(pool, "modulate", Color(1.0, 1.0, 1.0, 0.0), 2.2)
            tween.finished.connect(_release_grow_pool.bind(pool))
    for pool in dead:
        _grow_pools.erase(pool)

func _release_grow_pool(pool: Node3D) -> void:
    _grow_pools.erase(pool)
    if is_instance_valid(pool):
        pool.queue_free()

func _gta_tex(name: String) -> Texture2D:
    if _gta_textures.has(name):
        var cached: Variant = _gta_textures[name]
        return cached as Texture2D
    var path: String = "res://assets/gta2/fx/%s.png" % name
    var tex: Texture2D = load(path) as Texture2D if ResourceLoader.exists(path) else null
    _gta_textures[name] = tex
    return tex

func _make_gta_sprite(tex: Texture2D, world_position: Vector3, yaw_degrees: float, pixel_size: float, alpha: float) -> Sprite3D:
    var decal: Sprite3D = Sprite3D.new()
    decal.texture = tex
    decal.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    decal.billboard = BaseMaterial3D.BILLBOARD_DISABLED
    decal.shaded = false
    decal.double_sided = true
    decal.alpha_cut = SpriteBase3D.ALPHA_CUT_DISABLED
    decal.rotation_degrees = Vector3(-90.0, yaw_degrees, 0.0)
    decal.pixel_size = pixel_size
    decal.position = world_position + Vector3(0.0, 0.034, 0.0)
    decal.modulate = Color(1.0, 1.0, 1.0, alpha)
    return decal

func _spawn_gta_decal(tex: Texture2D, world_position: Vector3, yaw_degrees: float, pixel_size: float, lifetime: float, alpha: float, kind: String) -> void:
    if tex == null:
        return
    var decal: Sprite3D = _make_gta_sprite(tex, world_position, yaw_degrees, pixel_size, alpha)
    decal.name = "FXSkid" if kind == "skid" else "FXGtaDecal"
    add_child(decal)
    if kind == "skid":
        var cap: int = 24 if low_power else 48
        while _skid_decals.size() >= cap:
            var oldest: Node3D = _skid_decals.pop_front()
            if is_instance_valid(oldest):
                oldest.queue_free()
        _skid_decals.append(decal)
        var tween: Tween = create_tween()
        tween.tween_property(decal, "modulate", Color(1.0, 1.0, 1.0, 0.0), lifetime)
        tween.finished.connect(_release_skid.bind(decal))
        return
    _track(decal)
    var tween: Tween = create_tween()
    tween.tween_property(decal, "modulate", Color(1.0, 1.0, 1.0, 0.0), lifetime)
    tween.finished.connect(_release.bind(decal))

func _release_skid(decal: Node3D) -> void:
    _skid_decals.erase(decal)
    if is_instance_valid(decal):
        decal.queue_free()
'''
write("scripts/combat_fx.gd", combat)

main = read("scripts/main.gd")
main = replace(
    main,
    "    _build_civilians()\n",
    "    _build_civilians()\n    _spawn_elvis_line()\n",
    "elvis spawn call",
)
main = replace(
    main,
    """func _create_civilian(id: int, spawn: Vector3, route: Array[Vector3], color: Color, starts_in_vehicle: bool = false, pooled: bool = false) -> void:
""",
    """func _spawn_elvis_line() -> void:
    # Remap 12 is the white jumpsuit. They share one block and start a step
    # apart so the line reads as the downtown conga, not six lone pedestrians.
    var route: Array[Vector3] = [
        Vector3(316.0, 0.12, 330.5),
        Vector3(352.0, 0.12, 330.5),
        Vector3(352.0, 0.12, 348.0),
        Vector3(316.0, 0.12, 348.0),
    ]
    for index in range(6):
        var elvis_id: int = 9001 + index
        var start: Vector3 = route[0] + Vector3(float(index) * 2.2, 0.0, 0.0)
        _create_civilian(elvis_id, start, route, Color(0.95, 0.92, 0.98), false, false)
        if civilians.has(elvis_id):
            civilians[elvis_id].set_elvis()

func _create_civilian(id: int, spawn: Vector3, route: Array[Vector3], color: Color, starts_in_vehicle: bool = false, pooled: bool = false) -> void:
""",
    "elvis line",
)
main = replace(
    main,
    "                    audio_manager.note_skid(absf(driven.current_speed), steer_amount, driven.max_forward_speed)\n",
    "                    audio_manager.note_skid(absf(driven.current_speed), steer_amount, driven.max_forward_speed)\n"
    "                    if combat_fx != null:\n"
    "                        var throttle: float = 0.0\n"
    "                        if inputs.has(local_id):\n"
    "                            throttle = -(inputs[local_id] as Vector2).y\n"
    "                        combat_fx.play_skid_mark(driven.position, driven.get_forward_vector(), absf(driven.current_speed), driven.max_forward_speed, steer_amount, throttle)\n",
    "skid decal",
)
main = replace(
    main,
    "                audio_manager.play_vehicle_impact(vehicle.position, crash_damage >= 20)\n",
    "                audio_manager.play_vehicle_impact(vehicle.position, crash_damage >= 20)\n"
    "            if combat_fx != null and crash_damage >= 8:\n"
    "                combat_fx.play_crash_sparks(vehicle.position)\n",
    "crash sparks",
)
main = replace(
    main,
    "    _spawn_projectile_streak(start, end)\n",
    "    _spawn_projectile_streak(start, end)\n"
    "    if combat_fx != null:\n"
    "        combat_fx.play_gun_fx(start, end)\n",
    "gun sprites",
)
write("scripts/main.gd", main)

audio = read("scripts/audio_manager.gd")
audio = replace(
    audio,
    "var loud: float = lerpf(-8.0, -2.0, speed_ratio)\n",
    "var loud: float = lerpf(-5.0, 0.5, speed_ratio)\n",
    "louder driven car",
)
audio = replace(
    audio,
    "engine_player.volume_db = lerpf(-28.0, -7.0, nearness * nearness)\n",
    "engine_player.volume_db = lerpf(-20.0, -3.0, nearness * nearness)\n",
    "louder traffic",
)
write("scripts/audio_manager.gd", audio)

# The bullet-streak call also exists on the shock fan. Only the single-shot
# path should have been rewritten, and exactly once.
if main.count("combat_fx.play_gun_fx(start, end)") != 1:
    # main was rewritten; re-read the file we just wrote.
    written = read("scripts/main.gd")
    if written.count("combat_fx.play_gun_fx(start, end)") != 1:
        raise SystemExit("gun fx hook did not land once")

for rel, needle in (
    ("scripts/ped_animation.gd", "clampi(skin_index, 0, 12)"),
    ("scripts/civilian.gd", "func set_elvis()"),
    ("scripts/combat_fx.gd", "func play_skid_mark("),
    ("scripts/combat_fx.gd", "func play_crash_sparks("),
    ("scripts/combat_fx.gd", "func play_gun_fx("),
    ("scripts/combat_fx.gd", "func _play_gta_boom("),
    ("scripts/combat_fx.gd", "func _spawn_grow_pool("),
    ("scripts/main.gd", "func _spawn_elvis_line()"),
    ("scripts/main.gd", "combat_fx.play_skid_mark"),
    ("scripts/main.gd", "combat_fx.play_crash_sparks"),
    ("scripts/main.gd", "combat_fx.play_gun_fx"),
    ("scripts/audio_manager.gd", "lerpf(-5.0, 0.5, speed_ratio)"),
    ("scripts/audio_manager.gd", "lerpf(-20.0, -3.0, nearness * nearness)"),
    ("assets/gta2/fx/blood_5.png", None),
    ("assets/gta2/fx/skid.png", None),
    ("assets/gta2/fx/spark_0.png", None),
    ("assets/gta2/fx/boom_0.png", None),
    ("assets/gta2/fx/muzzle.png", None),
    ("assets/gta2/peds/animated/skin_12/type_0/walk.png", None),
    ("assets/gta2/peds/animated/skin_12/type_0/electrocute.png", None),
):
    path = root / rel
    if not path.exists() or path.stat().st_size < 32:
        raise SystemExit(f"Street FX missing: {rel}")
    if needle and needle not in path.read_text(encoding="utf-8"):
        raise SystemExit(f"Street FX needle missing: {rel} / {needle}")

print("GTA2 street FX and Elvis line applied.")
