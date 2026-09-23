#!/usr/bin/env python3
"""ViceQuest v0.6.18.28 pursuit/audio/crash pass on the proven 18.26->18.27 line.

Runs after the v0.6.18.27 patches.

Fixes:
- make nearby vehicle engines audible on foot by accepting every imported WAV
  layout instead of silently rejecting non-16-bit-mono streams
- keep three bounded manual-Ear traffic voices, including idling/AI vehicles
- add original GTA2 police siren voices tied to authoritative pursuit FX state
- transfer meaningful collision momentum into the struck vehicle without
  restoring the old gummy-ball rebound
- add flashing police lightbar sprites, including Quest elevated-vehicle clones
- let a pursuing Cop leave a stopped/pinning response car and force the wanted
  player out of their vehicle after a short stationary box-in
"""
from pathlib import Path
import re
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
        raise SystemExit(f"Missing v0.6.18.28 anchor {label}: found {hits}, need {count}")
    return text.replace(old, new, count)

def func_span(text: str, name: str) -> tuple[int, int]:
    match = re.search(rf"(?m)^func {re.escape(name)}\s*\(", text)
    if match is None:
        raise SystemExit(f"Missing function {name}")
    start = match.start()
    next_match = re.search(r"(?m)^func [A-Za-z0-9_]+\s*\(", text[match.end():])
    end = len(text) if next_match is None else match.end() + next_match.start()
    return start, end

def replace_func(text: str, name: str, replacement: str) -> str:
    start, end = func_span(text, name)
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]

def insert_before_func(text: str, name: str, addition: str) -> str:
    start, _ = func_span(text, name)
    return text[:start] + addition.rstrip() + "\n\n" + text[start:]

# ---------------------------------------------------------------------------
# 1) Traffic engines: preserve the 18.26 PCM ownership fix, but do not reject
#    imported WAVs just because Godot changed format/stereo during import.
# ---------------------------------------------------------------------------
owned_instance = r'''func _owned_loop_instance(sample_key: String) -> AudioStream:
    var base: AudioStream = _stream(sample_key)
    if base == null:
        return null
    if base is AudioStreamWAV:
        var src: AudioStreamWAV = base as AudioStreamWAV
        if src.data.is_empty():
            return null
        var owned: AudioStreamWAV = AudioStreamWAV.new()
        owned.format = src.format
        owned.mix_rate = src.mix_rate
        owned.stereo = src.stereo
        owned.loop_mode = AudioStreamWAV.LOOP_FORWARD
        owned.loop_begin = 0
        owned.loop_end = 0
        owned.data = src.data.duplicate()
        return owned
    var copied: Resource = base.duplicate(true)
    return copied as AudioStream
'''
audio = replace_func(audio, "_owned_loop_instance", owned_instance)

traffic_func = r'''func update_nearby_traffic(vehicles: Dictionary) -> void:
    if traffic_players.is_empty():
        return
    var chosen_nodes: Array = []
    var chosen_dist: Array[float] = []
    var chosen_ids: Array[int] = []

    for raw_id: Variant in vehicles.keys():
        var vehicle_id: int = int(raw_id)
        if _driving and vehicle_id == _local_vehicle_id:
            continue
        var candidate: Node = vehicles[raw_id]
        if candidate == null or not is_instance_valid(candidate):
            continue
        if bool(candidate.get("is_destroyed")):
            continue

        var occupied: bool = int(candidate.get("driver_id")) != 0
        var ai_active: bool = bool(candidate.get("ai_controlled"))
        var streamed: bool = bool(candidate.get("stream_active"))
        var ambient_member: bool = bool(candidate.get("ambient_pool_member"))
        # A visible fixed/spawned car may not be an ambient pool member. Keep
        # its idle motor eligible. Hidden pool members remain silent.
        if ambient_member and not streamed and not occupied and not ai_active:
            continue

        var pos: Vector3 = (candidate as Node3D).position
        var distance: float = Vector2(pos.x - _ear.x, pos.z - _ear.z).length()
        if distance > 52.0:
            continue

        var placed: bool = false
        for slot in range(chosen_dist.size()):
            if distance < chosen_dist[slot]:
                chosen_dist.insert(slot, distance)
                chosen_nodes.insert(slot, candidate)
                chosen_ids.insert(slot, vehicle_id)
                placed = true
                break
        if not placed:
            chosen_dist.append(distance)
            chosen_nodes.append(candidate)
            chosen_ids.append(vehicle_id)
        while chosen_dist.size() > 3:
            chosen_dist.pop_back()
            chosen_nodes.pop_back()
            chosen_ids.pop_back()

    for index in range(traffic_players.size()):
        var player: AudioStreamPlayer = traffic_players[index]
        if index >= chosen_nodes.size():
            _traffic_wanted[index] = false
            _traffic_ids[index] = -1
            _traffic_keys[index] = ""
            if player.playing:
                player.stop()
            continue

        var near_vehicle: Node = chosen_nodes[index]
        var variant: String = str(near_vehicle.get("variant_id"))
        var key: String = String(ENGINE_BY_VARIANT.get(variant, "engine_standard"))
        if key != _traffic_keys[index] or player.stream == null:
            _traffic_keys[index] = key
            player.stream = _owned_loop_instance(key)
            player.set_meta("loop_pos", -1.0)
            player.set_meta("loop_stall", 0.0)
            if player.stream != null:
                player.play()

        _traffic_ids[index] = chosen_ids[index]
        if player.stream == null:
            _traffic_wanted[index] = false
            continue

        var raw_speed: float = absf(float(near_vehicle.get("current_speed")))
        var max_speed: float = maxf(float(near_vehicle.get("max_forward_speed")), 0.1)
        var speed_ratio: float = clampf(raw_speed / max_speed, 0.0, 1.0)
        # Idling/remote AI still has an audible engine even when replicated
        # current_speed happens to be zero for a frame.
        speed_ratio = maxf(speed_ratio, 0.16)

        var nearness: float = 1.0 - clampf(chosen_dist[index] / 52.0, 0.0, 1.0)
        player.pitch_scale = (0.76 + speed_ratio * (0.34 if variant == "tank" else 0.60)) * (0.96 + float(index) * 0.035)
        var loud: float = lerpf(-15.0, -1.0, pow(nearness, 1.25))
        if _driving:
            loud -= 5.0
        player.volume_db = loud
        _traffic_wanted[index] = true
        _service_loop(player)
'''
audio = replace_func(audio, "update_nearby_traffic", traffic_func)

audio = must_replace(
    audio,
    'var _elvis_spotted: bool = false\n',
    'var _elvis_spotted: bool = false\nvar siren_players: Array[AudioStreamPlayer] = []\nvar _siren_wanted: Array[bool] = []\nvar _siren_ids: Array[int] = []\n',
    "siren fields",
)
audio = must_replace(
    audio,
    '\t\t_traffic_wanted.append(false)\n',
    '\t\t_traffic_wanted.append(false)\n\tfor index in range(2):\n\t\tsiren_players.append(_make_voice("PoliceSiren_%d" % index, -8.0))\n\t\t_siren_wanted.append(false)\n\t\t_siren_ids.append(-1)\n',
    "siren voices",
)
audio = must_replace(
    audio,
    '\tfor index in range(traffic_players.size()):\n\t\tif _traffic_wanted[index]:\n\t\t\t_service_loop(traffic_players[index])\n',
    '\tfor index in range(traffic_players.size()):\n\t\tif _traffic_wanted[index]:\n\t\t\t_service_loop(traffic_players[index])\n\tfor index in range(siren_players.size()):\n\t\tif _siren_wanted[index]:\n\t\t\t_service_loop(siren_players[index])\n',
    "siren loop service",
)

siren_func = r'''func update_police_sirens(vehicles: Dictionary) -> void:
    if siren_players.is_empty():
        return
    var chosen_nodes: Array = []
    var chosen_dist: Array[float] = []
    var chosen_ids: Array[int] = []
    for raw_id: Variant in vehicles.keys():
        var vehicle_id: int = int(raw_id)
        var candidate: Node = vehicles[raw_id]
        if candidate == null or not is_instance_valid(candidate):
            continue
        if bool(candidate.get("is_destroyed")):
            continue
        if not bool(candidate.get_meta("police_fx_active", false)):
            continue
        var pos: Vector3 = (candidate as Node3D).position
        var distance: float = Vector2(pos.x - _ear.x, pos.z - _ear.z).length()
        if distance > 72.0:
            continue
        var placed: bool = false
        for slot in range(chosen_dist.size()):
            if distance < chosen_dist[slot]:
                chosen_dist.insert(slot, distance)
                chosen_nodes.insert(slot, candidate)
                chosen_ids.insert(slot, vehicle_id)
                placed = true
                break
        if not placed:
            chosen_dist.append(distance)
            chosen_nodes.append(candidate)
            chosen_ids.append(vehicle_id)
        while chosen_dist.size() > siren_players.size():
            chosen_dist.pop_back()
            chosen_nodes.pop_back()
            chosen_ids.pop_back()

    for index in range(siren_players.size()):
        var player: AudioStreamPlayer = siren_players[index]
        if index >= chosen_nodes.size():
            _siren_wanted[index] = false
            _siren_ids[index] = -1
            if player.playing:
                player.stop()
            player.stream = null
            continue
        if player.stream == null:
            player.stream = _owned_loop_instance("horn_siren")
            player.set_meta("loop_pos", -1.0)
            player.set_meta("loop_stall", 0.0)
            if player.stream != null:
                player.play()
        _siren_ids[index] = chosen_ids[index]
        if player.stream == null:
            _siren_wanted[index] = false
            continue
        var nearness: float = 1.0 - clampf(chosen_dist[index] / 72.0, 0.0, 1.0)
        player.volume_db = lerpf(-20.0, -1.5, pow(nearness, 1.20))
        player.pitch_scale = 0.985 + float(index) * 0.035
        _siren_wanted[index] = true
        _service_loop(player)
'''
audio = insert_before_func(audio, "_owned_loop_instance", siren_func)

main = must_replace(
    main,
    '                audio_manager.update_nearby_traffic(vehicles)\n',
    '                audio_manager.update_nearby_traffic(vehicles)\n                audio_manager.update_police_sirens(vehicles)\n',
    "siren frame update",
)

# ---------------------------------------------------------------------------
# 2) Police pursuit FX + stationary pin extraction.
# ---------------------------------------------------------------------------
main = must_replace(
    main,
    'var police_ejected_driver_until_ms: Dictionary[int, int] = {}\n',
    'var police_ejected_driver_until_ms: Dictionary[int, int] = {}\nvar police_pin_since_ms: Dictionary[int, int] = {}\nvar police_vehicle_stop_until_ms: Dictionary[int, int] = {}\n',
    "police pin state",
)

police_helpers = r'''@rpc("authority", "call_local", "unreliable")
func _sync_police_vehicle_fx(vehicle_id: int, active: bool) -> void:
    if not vehicles.has(vehicle_id):
        return
    var vehicle: ViceQuestVehicle = vehicles[vehicle_id]
    var supported: bool = active
    if vehicle.has_method("supports_police_response_fx"):
        supported = active and bool(vehicle.call("supports_police_response_fx"))
    vehicle.set_meta("police_fx_active", supported)
    if vehicle.has_method("set_police_response_fx"):
        vehicle.call("set_police_response_fx", supported)

func _try_police_pin_extract(police_vehicle_id: int, player_id: int, now_ms: int) -> bool:
    if not vehicles.has(police_vehicle_id) or not players.has(player_id):
        police_pin_since_ms.erase(police_vehicle_id)
        return false
    if not player_vehicle.has(player_id):
        police_pin_since_ms.erase(police_vehicle_id)
        return false
    var target_vehicle_id: int = int(player_vehicle[player_id])
    if target_vehicle_id == police_vehicle_id or not vehicles.has(target_vehicle_id):
        police_pin_since_ms.erase(police_vehicle_id)
        return false

    var police_vehicle: ViceQuestVehicle = vehicles[police_vehicle_id]
    var target_vehicle: ViceQuestVehicle = vehicles[target_vehicle_id]
    var close_enough: bool = _planar_distance(police_vehicle.position, target_vehicle.position) <= 3.15
    var police_stopped: bool = absf(police_vehicle.current_speed) <= 1.25
    var target_stopped: bool = absf(target_vehicle.current_speed) <= 1.45
    if not close_enough or not police_stopped or not target_stopped:
        police_pin_since_ms.erase(police_vehicle_id)
        return false

    if not police_pin_since_ms.has(police_vehicle_id):
        police_pin_since_ms[police_vehicle_id] = now_ms
        return false
    if now_ms - int(police_pin_since_ms[police_vehicle_id]) < 850:
        return false

    var cop_id: int = int(police_driver_by_vehicle.get(police_vehicle_id, police_vehicle.get_meta("npc_driver_cop_id", 0)))
    if cop_id == 0:
        police_pin_since_ms.erase(police_vehicle_id)
        return false

    police_pin_since_ms.erase(police_vehicle_id)
    police_vehicle_stop_until_ms[police_vehicle_id] = now_ms + 4500
    police_vehicle.clear_pursuit()
    police_vehicle.ai_controlled = false
    police_vehicle.current_speed = 0.0

    var side: Vector3 = police_vehicle.get_side_vector()
    var exit_position: Vector3 = police_vehicle.position + side * 1.45
    exit_position.y = sample_surface_height(exit_position, police_vehicle.position.y - 0.10) + PLAYER_Y
    _detach_police_driver(police_vehicle_id, true, exit_position, target_vehicle.position)
    _sync_police_vehicle_fx.rpc(police_vehicle_id, true)
    _play_vehicle_door.rpc(police_vehicle.position, _vehicle_uses_heavy_door_sound(police_vehicle), false)

    if player_vehicle.has(player_id):
        _server_exit_vehicle(player_id)
        _show_combat_message.rpc("Police pulled %s from the vehicle" % _display_name(player_id))
    return true
'''
main = insert_before_func(main, "_server_update_pursuit_forces", police_helpers)

main = must_replace(
    main,
    '    if wanted_target_id == 0:\n        police_ejected_driver_until_ms.clear()\n',
    '    if wanted_target_id == 0:\n        police_ejected_driver_until_ms.clear()\n        police_pin_since_ms.clear()\n        police_vehicle_stop_until_ms.clear()\n',
    "clear police pin state",
)
main = must_replace(
    main,
    '            idle_vehicle.clear_pursuit()\n',
    '            idle_vehicle.clear_pursuit()\n            _sync_police_vehicle_fx.rpc(police_vehicle_id, false)\n',
    "idle police fx off",
)
main = must_replace(
    main,
    '        if bool(police_vehicle.get_meta("response_hijacked", false)) or police_vehicle.driver_id != 0:\n            police_vehicle.clear_pursuit()\n            police_vehicle.ai_controlled = false\n',
    '        if bool(police_vehicle.get_meta("response_hijacked", false)) or police_vehicle.driver_id != 0:\n            police_vehicle.clear_pursuit()\n            police_vehicle.ai_controlled = false\n            _sync_police_vehicle_fx.rpc(police_vehicle_id, false)\n',
    "hijacked police fx off",
)
main = must_replace(
    main,
    '        if active_driver_slot >= desired_variants.size():\n            _detach_police_driver(police_vehicle_id, false)\n',
    '        if police_vehicle_stop_until_ms.has(police_vehicle_id):\n            if int(police_vehicle_stop_until_ms[police_vehicle_id]) > now_ms:\n                police_vehicle.clear_pursuit()\n                police_vehicle.ai_controlled = false\n                police_vehicle.current_speed = move_toward(police_vehicle.current_speed, 0.0, police_vehicle.brake_deceleration * POLICE_RESPONSE_INTERVAL)\n                _sync_police_vehicle_fx.rpc(police_vehicle_id, true)\n                active_driver_slot += 1\n                continue\n            police_vehicle_stop_until_ms.erase(police_vehicle_id)\n\n        if active_driver_slot >= desired_variants.size():\n            _detach_police_driver(police_vehicle_id, false)\n            _sync_police_vehicle_fx.rpc(police_vehicle_id, false)\n',
    "police stop cooldown",
)
main = must_replace(
    main,
    '        if assigned_driver == 0:\n            police_vehicle.clear_pursuit()\n            police_vehicle.current_speed = move_toward(police_vehicle.current_speed, 0.0, police_vehicle.brake_deceleration * POLICE_RESPONSE_INTERVAL)\n            active_driver_slot += 1\n            continue\n        police_vehicle.set_pursuit_target(target, "police")\n        active_driver_slot += 1\n',
    '        if assigned_driver == 0:\n            police_vehicle.clear_pursuit()\n            police_vehicle.current_speed = move_toward(police_vehicle.current_speed, 0.0, police_vehicle.brake_deceleration * POLICE_RESPONSE_INTERVAL)\n            _sync_police_vehicle_fx.rpc(police_vehicle_id, false)\n            active_driver_slot += 1\n            continue\n        police_vehicle.set_pursuit_target(target, "police")\n        _sync_police_vehicle_fx.rpc(police_vehicle_id, true)\n        if _try_police_pin_extract(police_vehicle_id, wanted_target_id, now_ms):\n            active_driver_slot += 1\n            continue\n        active_driver_slot += 1\n',
    "active police fx and pin extraction",
)
main = must_replace(
    main,
    '        vehicle.set_stream_active(false)\n        vehicle_stream_states[vehicle_id] = false\n',
    '        vehicle.set_stream_active(false)\n        vehicle_stream_states[vehicle_id] = false\n        _sync_police_vehicle_fx.rpc(vehicle_id, false)\n',
    "respawn police fx off",
)

# ---------------------------------------------------------------------------
# 3) Police lightbar. A tiny generated sprite keeps this asset-free and copies
#    cleanly into the Quest popout vehicle mirror.
# ---------------------------------------------------------------------------
police_light_methods = r'''
func supports_police_response_fx() -> bool:
    return variant_id == "cop_car" or variant_id == "swat_van"

func get_police_light_sprite() -> Sprite3D:
    return get_node_or_null("PoliceLightbar") as Sprite3D

func wants_police_light() -> bool:
    return bool(get_meta("police_fx_active", false)) and not is_destroyed and stream_active and supports_police_response_fx()

func set_police_response_fx(active: bool) -> void:
    var enabled: bool = active and supports_police_response_fx()
    set_meta("police_fx_active", enabled)
    var light: Sprite3D = get_police_light_sprite()
    if enabled and light == null:
        light = _build_police_lightbar()
    if light != null:
        light.visible = enabled

func _build_police_lightbar() -> Sprite3D:
    var image: Image = Image.create(12, 4, false, Image.FORMAT_RGBA8)
    image.fill(Color(0.0, 0.0, 0.0, 0.0))
    for y in range(4):
        for x in range(12):
            if x <= 4:
                image.set_pixel(x, y, Color(0.08, 0.35, 1.0, 1.0))
            elif x >= 7:
                image.set_pixel(x, y, Color(0.25, 0.75, 1.0, 1.0))
            else:
                image.set_pixel(x, y, Color(0.75, 0.92, 1.0, 0.95))
    var texture: ImageTexture = ImageTexture.create_from_image(image)
    var light: Sprite3D = Sprite3D.new()
    light.name = "PoliceLightbar"
    light.texture = texture
    light.shaded = false
    light.centered = true
    light.double_sided = true
    light.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    light.render_priority = 12
    light.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    if _sprite != null:
        light.transform = _sprite.transform
        light.position.y += 0.11
        light.pixel_size = maxf(_sprite.pixel_size * 0.72, 0.012)
        light.layers = _sprite.layers
    else:
        light.rotation_degrees.x = -90.0
        light.position.y = 0.18
        light.pixel_size = 0.025
    add_child(light)
    var flash: Tween = create_tween()
    flash.set_loops()
    flash.tween_property(light, "modulate", Color(0.95, 1.0, 1.0, 1.0), 0.10)
    flash.tween_property(light, "modulate", Color(0.08, 0.30, 1.0, 0.28), 0.10)
    return light
'''
if "func supports_police_response_fx()" not in vehicle:
    vehicle = vehicle.rstrip() + "\n\n" + police_light_methods.strip() + "\n"

rig = must_replace(
    rig,
    '            src.visible = show_body\n            _restore_vehicle_turret(vehicle)\n            continue\n',
    '            src.visible = show_body\n            _restore_vehicle_turret(vehicle)\n            _restore_vehicle_police_light(vehicle)\n            continue\n',
    "restore road police light",
)
rig = must_replace(
    rig,
    '        _sync_elevated_turret(holder, vehicle)\n',
    '        _sync_elevated_turret(holder, vehicle)\n        _sync_elevated_police_light(holder, vehicle)\n',
    "sync roof police light",
)
rig = must_replace(
    rig,
    '    holder.add_child(_make_flat_sprite("Body"))\n    holder.add_child(_make_flat_sprite("Turret"))\n',
    '    holder.add_child(_make_flat_sprite("Body"))\n    holder.add_child(_make_flat_sprite("Turret"))\n    holder.add_child(_make_flat_sprite("PoliceLight"))\n',
    "police light clone slot",
)
rig_helpers = r'''func _sync_elevated_police_light(holder: Node3D, vehicle: Node) -> void:
    var light_clone: Sprite3D = holder.get_node("PoliceLight") as Sprite3D
    var src: SpriteBase3D = null
    if vehicle.has_method("get_police_light_sprite"):
        src = vehicle.get_police_light_sprite()
    var show: bool = src != null and is_instance_valid(src) and vehicle.has_method("wants_police_light") and bool(vehicle.call("wants_police_light"))
    if not show:
        light_clone.visible = false
        _restore_vehicle_police_light(vehicle)
        return
    _copy_flat_sprite(light_clone, src)
    src.visible = false

func _restore_vehicle_police_light(vehicle: Node) -> void:
    if vehicle == null or not is_instance_valid(vehicle) or not vehicle.has_method("get_police_light_sprite"):
        return
    var src: SpriteBase3D = vehicle.get_police_light_sprite()
    if src != null and is_instance_valid(src):
        src.visible = vehicle.has_method("wants_police_light") and bool(vehicle.call("wants_police_light"))
'''
rig = insert_before_func(rig, "_restore_vehicle_turret", rig_helpers)
rig = must_replace(
    rig,
    '        for sprite_name: String in ["Body", "Turret"]:\n',
    '        for sprite_name: String in ["Body", "Turret", "PoliceLight"]:\n',
    "free police light clone",
)
rig = must_replace(
    rig,
    '    if src.name == "OriginalGTA2Turret" and node.has_method("wants_turret_sprite"):\n        src.visible = bool(node.call("wants_turret_sprite"))\n    else:\n        src.visible = bool(node.call("wants_board_sprite"))\n',
    '    if src.name == "OriginalGTA2Turret" and node.has_method("wants_turret_sprite"):\n        src.visible = bool(node.call("wants_turret_sprite"))\n    elif src.name == "PoliceLightbar" and node.has_method("wants_police_light"):\n        src.visible = bool(node.call("wants_police_light"))\n    else:\n        src.visible = bool(node.call("wants_board_sprite"))\n',
    "restore cloned police light",
)

# ---------------------------------------------------------------------------
# 4) Crash momentum transfer. Keep low restitution, but a struck parked vehicle
#    must visibly move instead of behaving like scenery.
# ---------------------------------------------------------------------------
collision = r'''func _resolve_vehicle_collisions(impact_speed: float) -> void:
    for collision_index in range(get_slide_collision_count()):
        var collision: KinematicCollision3D = get_slide_collision(collision_index)
        var collider: Object = collision.get_collider()
        if not collider is ViceQuestVehicle:
            continue
        var other: ViceQuestVehicle = collider as ViceQuestVehicle
        if other == self or other.is_destroyed:
            continue
        if variant_id == "tank" and other.variant_id != "tank" and multiplayer.is_server():
            var main_node: Node = get_parent()
            if main_node != null and main_node.has_method("_server_tank_crush_vehicle"):
                main_node.call("_server_tank_crush_vehicle", vehicle_id, other.vehicle_id, driver_id)
            var travel_sign: float = 1.0 if current_speed >= 0.0 else -1.0
            current_speed = travel_sign * maxf(absf(current_speed), impact_speed * 0.82)
            position += get_forward_vector() * travel_sign * clampf(impact_speed * 0.045, 0.38, 0.92)
            _snap_to_map_surface()
            target_position = position
            continue

        var normal: Vector3 = collision.get_normal()
        normal.y = 0.0
        if normal.length_squared() <= 0.001:
            normal = position - other.position
        if normal.length_squared() <= 0.001:
            normal = get_side_vector()
        normal = normal.normalized()

        var relative_velocity: Vector3 = velocity - other.velocity
        relative_velocity.y = 0.0
        var normal_speed: float = absf(relative_velocity.dot(normal))
        var relative_speed: float = maxf(impact_speed, maxf(normal_speed, relative_velocity.length() * 0.65))
        if relative_speed < 0.75:
            continue

        var self_mass: float = maxf(collision_mass, 1.0)
        var other_mass: float = maxf(other.collision_mass, 1.0)
        var total_mass: float = self_mass + other_mass

        # Attacker loses energy but does not reverse.
        var self_retention: float = clampf(0.38 + (self_mass / total_mass) * 0.30, 0.44, 0.70)
        current_speed *= self_retention

        # Transfer enough momentum that a stationary target actually rolls or
        # slides. External impulse handles side hits; longitudinal transfer lets
        # a nose-to-tail hit push the target along its own heading.
        var transfer_speed: float = clampf(relative_speed * 0.30 * (self_mass / total_mass), 0.45, 4.25)
        var target_direction: Vector3 = -normal
        other.apply_external_impulse(target_direction * transfer_speed)
        apply_external_impulse(normal * transfer_speed * 0.14)

        var along_other: float = target_direction.dot(other.get_forward_vector())
        if absf(along_other) > 0.18:
            other.current_speed += along_other * transfer_speed * 0.72
            other.current_speed = clampf(other.current_speed, -other.max_reverse_speed, other.max_forward_speed)

        # Immediate low-distance shove prevents two CharacterBodies from looking
        # welded together before the next physics tick, without pinball recoil.
        var shove: float = clampf(relative_speed * 0.016 * (self_mass / total_mass), 0.035, 0.34)
        other.position += target_direction * shove
        other._snap_to_map_surface()
        other.target_position = other.position

        if _crash_damage_cooldown <= 0.0 and relative_speed >= CRASH_DAMAGE_MIN_SPEED:
            _pending_crash_damage = maxi(_pending_crash_damage, clampi(roundi(relative_speed * 1.6), 5, 24))
            _crash_damage_cooldown = CRASH_DAMAGE_COOLDOWN
        if other._crash_damage_cooldown <= 0.0 and relative_speed >= CRASH_DAMAGE_MIN_SPEED:
            other._pending_crash_damage = maxi(other._pending_crash_damage, clampi(roundi(relative_speed * 1.35), 4, 20))
            other._crash_damage_cooldown = CRASH_DAMAGE_COOLDOWN
'''
vehicle = replace_func(vehicle, "_resolve_vehicle_collisions", collision)

checks = [
    ("owned.data = src.data.duplicate()", audio),
    ("func update_police_sirens", audio),
    ("horn_siren", audio),
    ("police_pin_since_ms", main),
    ("func _try_police_pin_extract", main),
    ("_sync_police_vehicle_fx.rpc", main),
    ("func supports_police_response_fx", vehicle),
    ("PoliceLightbar", vehicle),
    ("transfer_speed", vehicle),
    ("other.position += target_direction * shove", vehicle),
    ("func _sync_elevated_police_light", rig),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"v0.6.18.28 verification failed: {needle}")

if "AudioStreamPlayer3D" in audio:
    raise SystemExit("v0.6.18.28 must remain on the proven 18.26 manual Ear mixer")

main_path.write_text(main, encoding="utf-8")
vehicle_path.write_text(vehicle, encoding="utf-8")
audio_path.write_text(audio, encoding="utf-8")
rig_path.write_text(rig, encoding="utf-8")
print("Applied v0.6.18.28: audible traffic, crash momentum, police sirens/lights and pin extraction.")
