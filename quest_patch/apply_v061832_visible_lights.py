#!/usr/bin/env python3
"""ViceQuest v0.6.18.32 visible street and vehicle lights.

Runs after v0.6.18.31.

Hardware feedback:
- day/night transition works
- police blue beacon works
- generated curb/street lights are not visible
- vehicles have no headlights/tail lights

Fixes:
- convert map-block lights with the exact DOWNTOWN_DATA.TILE_SIZE instead of
  the incorrect hard-coded 2.8 scale
- snap each glow to the actual sampled world surface
- make curb-light corona stronger and explicitly layer-1/no-depth-test
- add a bounded nearest-vehicle light pool with shared textures:
  twin warm headlights, forward road glow and red tail lights
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
main = main_path.read_text(encoding="utf-8")

def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    hits = text.count(old)
    if hits < count:
        raise SystemExit(f"Missing v0.6.18.32 anchor {label}: found {hits}, need {count}")
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
# Fields for bounded vehicle lighting. Shared textures mean the number of
# vehicle nodes does not multiply texture memory.
# ---------------------------------------------------------------------------
main = must_replace(
    main,
    "var gta2_map_light_accumulator: float = 0.0\n",
    """var gta2_map_light_accumulator: float = 0.0
const GTA2_VEHICLE_LIGHT_POOL: int = 18
const GTA2_VEHICLE_LIGHT_RANGE: float = 31.0
var gta2_vehicle_light_root: Node3D
var gta2_vehicle_light_pool: Array[Node3D] = []
var gta2_headlight_texture: Texture2D
var gta2_taillight_texture: Texture2D
var gta2_headbeam_texture: Texture2D
""",
    "vehicle light fields",
)

# ---------------------------------------------------------------------------
# Stronger shared light textures and pool construction.
# ---------------------------------------------------------------------------
texture_and_pool = r'''func _build_gta2_vehicle_head_texture() -> Texture2D:
    var size: int = 32
    var image: Image = Image.create(size, size, false, Image.FORMAT_RGBA8)
    var center: Vector2 = Vector2(float(size - 1) * 0.5, float(size - 1) * 0.5)
    var radius: float = float(size) * 0.5
    for y in range(size):
        for x in range(size):
            var d: float = Vector2(float(x), float(y)).distance_to(center) / radius
            var alpha: float = pow(maxf(0.0, 1.0 - d), 1.65)
            image.set_pixel(x, y, Color(1.0, 0.92, 0.67, alpha))
    return ImageTexture.create_from_image(image)

func _build_gta2_vehicle_tail_texture() -> Texture2D:
    var size: int = 24
    var image: Image = Image.create(size, size, false, Image.FORMAT_RGBA8)
    var center: Vector2 = Vector2(float(size - 1) * 0.5, float(size - 1) * 0.5)
    var radius: float = float(size) * 0.5
    for y in range(size):
        for x in range(size):
            var d: float = Vector2(float(x), float(y)).distance_to(center) / radius
            var alpha: float = pow(maxf(0.0, 1.0 - d), 1.45)
            image.set_pixel(x, y, Color(1.0, 0.055, 0.025, alpha))
    return ImageTexture.create_from_image(image)

func _build_gta2_headbeam_texture() -> Texture2D:
    var width: int = 64
    var height: int = 96
    var image: Image = Image.create(width, height, false, Image.FORMAT_RGBA8)
    for y in range(height):
        var fy: float = float(y) / float(height - 1)
        var longitudinal: float = pow(1.0 - absf(fy - 0.44) / 0.62, 1.7)
        longitudinal = maxf(0.0, longitudinal)
        var half_width: float = lerpf(0.16, 0.48, 1.0 - fy)
        for x in range(width):
            var fx: float = absf((float(x) / float(width - 1)) - 0.5)
            var lateral: float = maxf(0.0, 1.0 - fx / maxf(0.03, half_width))
            var alpha: float = longitudinal * lateral * lateral * 0.46
            image.set_pixel(x, y, Color(1.0, 0.90, 0.62, alpha))
    return ImageTexture.create_from_image(image)

func _make_light_sprite(name_value: String, texture: Texture2D, pixel_size: float, priority: int) -> Sprite3D:
    var sprite: Sprite3D = Sprite3D.new()
    sprite.name = name_value
    sprite.texture = texture
    sprite.pixel_size = pixel_size
    sprite.shaded = false
    sprite.centered = true
    sprite.double_sided = true
    sprite.no_depth_test = true
    sprite.layers = 1
    sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
    sprite.render_priority = priority
    sprite.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    sprite.visible = false
    return sprite

func _build_gta2_vehicle_light_pool() -> void:
    gta2_headlight_texture = _build_gta2_vehicle_head_texture()
    gta2_taillight_texture = _build_gta2_vehicle_tail_texture()
    gta2_headbeam_texture = _build_gta2_headbeam_texture()
    gta2_vehicle_light_root = Node3D.new()
    gta2_vehicle_light_root.name = "GTA2VehicleLights"
    add_child(gta2_vehicle_light_root)

    for index in range(GTA2_VEHICLE_LIGHT_POOL):
        var holder: Node3D = Node3D.new()
        holder.name = "VehicleLight_%02d" % index
        holder.add_child(_make_light_sprite("HeadLeft", gta2_headlight_texture, 0.026, 22))
        holder.add_child(_make_light_sprite("HeadRight", gta2_headlight_texture, 0.026, 22))
        holder.add_child(_make_light_sprite("TailLeft", gta2_taillight_texture, 0.022, 22))
        holder.add_child(_make_light_sprite("TailRight", gta2_taillight_texture, 0.022, 22))
        holder.add_child(_make_light_sprite("Beam", gta2_headbeam_texture, 0.055, 20))
        holder.visible = false
        gta2_vehicle_light_root.add_child(holder)
        gta2_vehicle_light_pool.append(holder)

func _set_ground_sprite_transform(sprite: Sprite3D, world_position: Vector3, forward: Vector3, side: Vector3) -> void:
    sprite.global_transform = Transform3D(Basis(side, forward, Vector3.UP), world_position)

func _update_gta2_vehicle_lights() -> void:
    if gta2_vehicle_light_pool.is_empty():
        return
    if gta2_night_factor <= 0.03:
        for holder in gta2_vehicle_light_pool:
            holder.visible = false
        return

    var local_id: int = multiplayer.get_unique_id()
    var center: Vector3 = Vector3.ZERO
    if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
        center = vehicles[player_vehicle[local_id]].position
    elif players.has(local_id):
        center = players[local_id].position

    var chosen: Array = []
    for raw_id: Variant in vehicles.keys():
        var vehicle: Node = vehicles[raw_id]
        if vehicle == null or not is_instance_valid(vehicle):
            continue
        if bool(vehicle.get("is_destroyed")):
            continue
        var active: bool = bool(vehicle.get("stream_active")) or bool(vehicle.get("ai_controlled")) or int(vehicle.get("driver_id")) != 0
        if not active:
            continue
        var pos: Vector3 = (vehicle as Node3D).position
        var distance: float = Vector2(pos.x - center.x, pos.z - center.z).length()
        if distance > GTA2_VEHICLE_LIGHT_RANGE:
            continue
        var entry: Dictionary = {"node": vehicle, "distance": distance}
        var inserted: bool = false
        for slot in range(chosen.size()):
            if distance < float((chosen[slot] as Dictionary)["distance"]):
                chosen.insert(slot, entry)
                inserted = true
                break
        if not inserted:
            chosen.append(entry)
        while chosen.size() > GTA2_VEHICLE_LIGHT_POOL:
            chosen.pop_back()

    for pool_index in range(gta2_vehicle_light_pool.size()):
        var holder: Node3D = gta2_vehicle_light_pool[pool_index]
        if pool_index >= chosen.size():
            holder.visible = false
            continue

        var vehicle: Node = (chosen[pool_index] as Dictionary)["node"]
        var forward: Vector3 = vehicle.call("get_forward_vector")
        forward.y = 0.0
        if forward.length_squared() <= 0.001:
            holder.visible = false
            continue
        forward = forward.normalized()
        var side: Vector3 = vehicle.call("get_side_vector")
        side.y = 0.0
        if side.length_squared() <= 0.001:
            side = Vector3(-forward.z, 0.0, forward.x)
        else:
            side = side.normalized()

        var base: Vector3 = (vehicle as Node3D).position
        var surface_y: float = sample_surface_height(base, base.y - 0.20)
        var length_scale: float = 0.78
        var width_scale: float = 0.30
        var variant: String = str(vehicle.get("variant_id"))
        if variant in ["swat_van", "van", "box_truck", "benson", "truck_cab_sx", "tow_truck", "hot_dog_van", "ice_cream_van"]:
            length_scale = 0.98
            width_scale = 0.36
        elif variant == "tank":
            length_scale = 1.08
            width_scale = 0.41

        var front_center: Vector3 = base + forward * length_scale
        var rear_center: Vector3 = base - forward * length_scale
        front_center.y = surface_y + 0.075
        rear_center.y = surface_y + 0.078

        var head_left: Sprite3D = holder.get_node("HeadLeft") as Sprite3D
        var head_right: Sprite3D = holder.get_node("HeadRight") as Sprite3D
        var tail_left: Sprite3D = holder.get_node("TailLeft") as Sprite3D
        var tail_right: Sprite3D = holder.get_node("TailRight") as Sprite3D
        var beam: Sprite3D = holder.get_node("Beam") as Sprite3D

        var intensity: float = clampf(gta2_night_factor, 0.0, 1.0)
        head_left.modulate = Color(1.0, 0.94, 0.72, 0.95 * intensity)
        head_right.modulate = head_left.modulate
        tail_left.modulate = Color(1.0, 0.05, 0.025, 0.82 * intensity)
        tail_right.modulate = tail_left.modulate
        beam.modulate = Color(1.0, 0.91, 0.66, 0.62 * intensity)

        _set_ground_sprite_transform(head_left, front_center - side * width_scale, forward, side)
        _set_ground_sprite_transform(head_right, front_center + side * width_scale, forward, side)
        _set_ground_sprite_transform(tail_left, rear_center - side * width_scale, forward, side)
        _set_ground_sprite_transform(tail_right, rear_center + side * width_scale, forward, side)

        var beam_position: Vector3 = base + forward * (length_scale + 1.65)
        beam_position.y = surface_y + 0.052
        _set_ground_sprite_transform(beam, beam_position, forward, side)
        holder.visible = true
        head_left.visible = true
        head_right.visible = true
        tail_left.visible = true
        tail_right.visible = true
        beam.visible = variant != "tank"
'''
main = insert_before_func(main, "_build_gta2_lighting_system", texture_and_pool)

build_lights = get_func(main, "_build_gta2_lighting_system")
build_lights = must_replace(
    build_lights,
    "    gta2_map_light_texture = _build_gta2_light_texture()\n",
    "    gta2_map_light_texture = _build_gta2_light_texture()\n    _build_gta2_vehicle_light_pool()\n",
    "build vehicle light pool",
)
build_lights = must_replace(
    build_lights,
    "        glow.shaded = false\n",
    "        glow.shaded = false\n        glow.layers = 1\n",
    "map light layer",
)
build_lights = must_replace(build_lights, "        glow.render_priority = 11\n", "        glow.render_priority = 21\n", "map light priority")
main = replace_func(main, "_build_gta2_lighting_system", build_lights)

# Stronger warm street corona. Keep one shared texture for all pool entries.
map_tex = r'''func _build_gta2_light_texture() -> Texture2D:
    var size: int = 64
    var image: Image = Image.create(size, size, false, Image.FORMAT_RGBA8)
    var center: Vector2 = Vector2(float(size - 1) * 0.5, float(size - 1) * 0.5)
    var radius: float = float(size) * 0.5
    for y in range(size):
        for x in range(size):
            var distance: float = Vector2(float(x), float(y)).distance_to(center) / radius
            var halo: float = pow(maxf(0.0, 1.0 - distance), 1.45)
            var core: float = pow(maxf(0.0, 1.0 - distance * 2.8), 1.2)
            var alpha: float = clampf(halo * 0.78 + core * 0.38, 0.0, 1.0)
            image.set_pixel(x, y, Color(1.0, 0.92, 0.68, alpha))
    return ImageTexture.create_from_image(image)
'''
main = replace_func(main, "_build_gta2_light_texture", map_tex)

# ---------------------------------------------------------------------------
# Correct world conversion for street lights.
# ---------------------------------------------------------------------------
map_update = r'''func _update_gta2_map_lights() -> void:
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

    var tile_size: float = DOWNTOWN_DATA.TILE_SIZE
    var chosen: Array = []
    for light_index in range(gta2_map_light_defs.size()):
        var definition: Dictionary = gta2_map_light_defs[light_index]
        if not _map_light_active(definition, light_index):
            continue

        var world_x: float = float(definition.get("x", 0.0)) * tile_size
        var world_z: float = float(definition.get("y", 0.0)) * tile_size
        var probe: Vector3 = Vector3(world_x, center.y, world_z)
        var surface_y: float = sample_surface_height(probe, center.y - 0.18)
        var world_position: Vector3 = Vector3(world_x, surface_y + 0.060, world_z)

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
        var radius_blocks: float = clampf(float(definition.get("radius", 1.0)), 0.38, 3.2)
        var world_radius: float = radius_blocks * tile_size
        glow.pixel_size = maxf(0.018, (world_radius * 1.55) / 64.0)
        var intensity: float = clampf(float(definition.get("intensity", 180)) / 255.0, 0.28, 1.0)
        var source_color: Color = Color(
            float(definition.get("r", 255)) / 255.0,
            float(definition.get("g", 214)) / 255.0,
            float(definition.get("b", 145)) / 255.0
        )
        # Generated curb lights use warm amber. Preserve authored source color
        # if original LGHT data is available in a future source pack.
        glow.modulate = Color(
            source_color.r,
            source_color.g,
            source_color.b,
            clampf((0.45 + gta2_night_factor * 0.55) * intensity, 0.0, 1.0)
        )
        glow.visible = true
'''
main = replace_func(main, "_update_gta2_map_lights", map_update)

timecycle = get_func(main, "_update_gta2_timecycle")
timecycle = must_replace(
    timecycle,
    "    if presentation_rig != null and presentation_rig.has_method(\"set_gta2_time_of_day\"):\n        presentation_rig.call(\"set_gta2_time_of_day\", gta2_clock_hours, gta2_night_factor)\n",
    "    if presentation_rig != null and presentation_rig.has_method(\"set_gta2_time_of_day\"):\n        presentation_rig.call(\"set_gta2_time_of_day\", gta2_clock_hours, gta2_night_factor)\n    _update_gta2_vehicle_lights()\n",
    "vehicle light update",
)
main = replace_func(main, "_update_gta2_timecycle", timecycle)

checks = [
    ("DOWNTOWN_DATA.TILE_SIZE", main),
    ("sample_surface_height(probe", main),
    ("const GTA2_VEHICLE_LIGHT_POOL: int = 18", main),
    ("func _update_gta2_vehicle_lights", main),
    ('holder.add_child(_make_light_sprite("Beam"', main),
    ("glow.layers = 1", main),
    ("glow.render_priority = 21", main),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"v0.6.18.32 verification failed: {needle}")

main_path.write_text(main, encoding="utf-8")
print("Applied v0.6.18.32: corrected street-light coordinates plus bounded headlights, beams and tail lights.")
