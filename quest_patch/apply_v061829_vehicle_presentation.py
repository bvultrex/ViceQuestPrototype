#!/usr/bin/env python3
"""ViceQuest v0.6.18.29 presentation/impact pass.

Runs after v0.6.18.28 on the authoritative Quest branch.

Hardware feedback addressed:
- nearby engines still silent: give each traffic voice a physically separate WAV
  resource path instead of relying on runtime PCM/resource duplication
- sirens/lightbar missing: update sirens in and out of cars, make response FX RPC
  reliable, and make the lightbar larger/overlay-safe
- Cop pull-out worked but Cop stayed invisible: add a reliable explicit Cop exit
  sync and separate the Cop exit position from the pulled-out player
- make collision momentum moderately heavier without restoring bounce
- rotate confirmed backwards SWAT van artwork by 180 degrees
- show GTA-style vehicle name at the HUD edge when entering a vehicle
"""
from pathlib import Path
import re
import shutil
import sys

from PIL import Image

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
vehicle_path = root / "scripts" / "vehicle.gd"
audio_path = root / "scripts" / "audio_manager.gd"

main = main_path.read_text(encoding="utf-8")
vehicle = vehicle_path.read_text(encoding="utf-8")
audio = audio_path.read_text(encoding="utf-8")

def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    hits = text.count(old)
    if hits < count:
        raise SystemExit(f"Missing v0.6.18.29 anchor {label}: found {hits}, need {count}")
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
# 1) Give every traffic/siren voice a separate physical WAV path. This avoids
#    Quest resource/PCM sharing entirely while leaving the proven own-car 18.26
#    LocalVehicleEngine path untouched.
# ---------------------------------------------------------------------------
sfx_dir = root / "assets" / "audio" / "gta2" / "sfx"
sfx_dir.mkdir(parents=True, exist_ok=True)
engine_keys = ("engine_standard", "engine_tank", "engine_sport", "engine_van", "engine_compact")
standard = sfx_dir / "engine_standard.wav"
if not standard.is_file():
    raise SystemExit(f"Missing working local engine WAV: {standard}")

for key in engine_keys:
    src = sfx_dir / f"{key}.wav"
    if not src.is_file():
        src = standard
    for index in range(3):
        shutil.copy2(src, sfx_dir / f"{key}_traffic_{index}.wav")

siren = sfx_dir / "horn_siren.wav"
if not siren.is_file():
    raise SystemExit(f"Missing GTA2 siren WAV: {siren}")
for index in range(2):
    shutil.copy2(siren, sfx_dir / f"horn_siren_{index}.wav")

unique_helpers = r'''func _traffic_voice_stream(sample_key: String, index: int) -> AudioStream:
    var path: String = SFX_ROOT + sample_key + "_traffic_%d.wav" % index
    if ResourceLoader.exists(path):
        return load(path) as AudioStream
    # Last-resort fallback. Own-car audio remains completely separate.
    return _stream(sample_key)

func _siren_voice_stream(index: int) -> AudioStream:
    var path: String = SFX_ROOT + "horn_siren_%d.wav" % index
    if ResourceLoader.exists(path):
        return load(path) as AudioStream
    return _stream("horn_siren")
'''
audio = insert_before_func(audio, "update_nearby_traffic", unique_helpers)

traffic = r'''func update_nearby_traffic(vehicles: Dictionary) -> void:
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
        if ambient_member and not streamed and not occupied and not ai_active:
            continue

        var pos: Vector3 = (candidate as Node3D).position
        var distance: float = Vector2(pos.x - _ear.x, pos.z - _ear.z).length()
        if distance > 58.0:
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
        while chosen_dist.size() > traffic_players.size():
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
            player.stream = null
            continue

        var near_vehicle: Node = chosen_nodes[index]
        var variant: String = str(near_vehicle.get("variant_id"))
        var key: String = String(ENGINE_BY_VARIANT.get(variant, "engine_standard"))
        if key != _traffic_keys[index] or player.stream == null:
            _traffic_keys[index] = key
            player.stream = _traffic_voice_stream(key, index)
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
        var speed_ratio: float = maxf(clampf(raw_speed / max_speed, 0.0, 1.0), 0.18)
        var nearness: float = 1.0 - clampf(chosen_dist[index] / 58.0, 0.0, 1.0)
        player.pitch_scale = (0.76 + speed_ratio * (0.34 if variant == "tank" else 0.60)) * (0.97 + float(index) * 0.03)
        player.volume_db = lerpf(-13.0, 0.0, pow(nearness, 1.18)) - (4.0 if _driving else 0.0)
        _traffic_wanted[index] = true
        _service_loop(player)
'''
audio = replace_func(audio, "update_nearby_traffic", traffic)

siren_update = r'''func update_police_sirens(vehicles: Dictionary) -> void:
    if siren_players.is_empty():
        return
    var chosen_nodes: Array = []
    var chosen_dist: Array[float] = []
    var chosen_ids: Array[int] = []
    for raw_id: Variant in vehicles.keys():
        var vehicle_id: int = int(raw_id)
        var candidate: Node = vehicles[raw_id]
        if candidate == null or not is_instance_valid(candidate) or bool(candidate.get("is_destroyed")):
            continue
        if not bool(candidate.get_meta("police_fx_active", false)):
            continue
        var pos: Vector3 = (candidate as Node3D).position
        var distance: float = Vector2(pos.x - _ear.x, pos.z - _ear.z).length()
        if distance > 82.0:
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
            player.stream = _siren_voice_stream(index)
            player.set_meta("loop_pos", -1.0)
            player.set_meta("loop_stall", 0.0)
            if player.stream != null:
                player.play()
        _siren_ids[index] = chosen_ids[index]
        if player.stream == null:
            _siren_wanted[index] = false
            continue
        var nearness: float = 1.0 - clampf(chosen_dist[index] / 82.0, 0.0, 1.0)
        player.volume_db = lerpf(-18.0, 1.5, pow(nearness, 1.15))
        player.pitch_scale = 0.99 + float(index) * 0.025
        _siren_wanted[index] = true
        _service_loop(player)
'''
audio = replace_func(audio, "update_police_sirens", siren_update)

# Make traffic and siren updates run both on foot and while driving.
old_audio_block = '''            if audio_manager != null:
                audio_manager.set_ear(target)
                if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
                    var driven: ViceQuestVehicle = vehicles[player_vehicle[local_id]]
                    audio_manager.update_local_vehicle(driven)
                    var steer_amount: float = 0.0
                    if inputs.has(local_id):
                        steer_amount = absf((inputs[local_id] as Vector2).x)
                    audio_manager.note_skid(absf(driven.current_speed), steer_amount, driven.max_forward_speed)
                else:
                    audio_manager.update_nearby_traffic(vehicles)
                    audio_manager.update_police_sirens(vehicles)
                    audio_manager.note_footstep(p._is_moving)
                if input_bridge != null and input_bridge.consume_radio_next():
                    _show_combat_message(audio_manager.cycle_radio())
'''
new_audio_block = '''            if audio_manager != null:
                audio_manager.set_ear(target)
                if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
                    var driven: ViceQuestVehicle = vehicles[player_vehicle[local_id]]
                    audio_manager.update_local_vehicle(driven)
                    var steer_amount: float = 0.0
                    if inputs.has(local_id):
                        steer_amount = absf((inputs[local_id] as Vector2).x)
                    audio_manager.note_skid(absf(driven.current_speed), steer_amount, driven.max_forward_speed)
                else:
                    audio_manager.stop_engine()
                    audio_manager.note_footstep(p._is_moving)
                audio_manager.update_nearby_traffic(vehicles)
                audio_manager.update_police_sirens(vehicles)
                if input_bridge != null and input_bridge.consume_radio_next():
                    _show_combat_message(audio_manager.cycle_radio())
'''
main = must_replace(main, old_audio_block, new_audio_block, "always-on traffic/siren audio")

# ---------------------------------------------------------------------------
# 2) Reliable response FX and genuinely visible Cop exit.
# ---------------------------------------------------------------------------
main = must_replace(
    main,
    '@rpc("authority", "call_local", "unreliable")\nfunc _sync_police_vehicle_fx(',
    '@rpc("authority", "call_local", "reliable")\nfunc _sync_police_vehicle_fx(',
    "reliable police FX",
)

cop_exit_rpc = r'''@rpc("authority", "call_local", "reliable")
func _sync_cop_exit(cop_id: int, role: String, world_position: Vector3, facing: Vector3, hp_value: int) -> void:
    if not cops.has(cop_id):
        return
    var cop: ViceQuestCop = cops[cop_id]
    if cop.enforcement_role != role:
        cop.set_enforcement_profile(role)
    cop.position = world_position
    cop.target_position = world_position
    cop.facing = facing
    if facing.length_squared() > 0.04:
        cop.rotation.y = -atan2(facing.x, -facing.z)
    cop.hp = mini(cop.hp, hp_value)
    cop.set_response_active(true)
    cop.visible = true
'''
main = insert_before_func(main, "_try_police_pin_extract", cop_exit_rpc)

pin_extract = r'''func _try_police_pin_extract(police_vehicle_id: int, player_id: int, now_ms: int) -> bool:
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
    var close_enough: bool = _planar_distance(police_vehicle.position, target_vehicle.position) <= 3.25
    var police_stopped: bool = absf(police_vehicle.current_speed) <= 1.35
    var target_stopped: bool = absf(target_vehicle.current_speed) <= 1.55
    if not close_enough or not police_stopped or not target_stopped:
        police_pin_since_ms.erase(police_vehicle_id)
        return false

    if not police_pin_since_ms.has(police_vehicle_id):
        police_pin_since_ms[police_vehicle_id] = now_ms
        return false
    if now_ms - int(police_pin_since_ms[police_vehicle_id]) < 850:
        return false

    var cop_id: int = int(police_driver_by_vehicle.get(police_vehicle_id, police_vehicle.get_meta("npc_driver_cop_id", 0)))
    if cop_id == 0 or not cops.has(cop_id):
        police_pin_since_ms.erase(police_vehicle_id)
        return false

    police_pin_since_ms.erase(police_vehicle_id)
    police_vehicle_stop_until_ms[police_vehicle_id] = now_ms + 4500
    police_vehicle.clear_pursuit()
    police_vehicle.ai_controlled = false
    police_vehicle.current_speed = 0.0
    _sync_police_vehicle_fx.rpc(police_vehicle_id, true)

    # Pull the player out first so the subsequent Cop spawn cannot share the
    # same exit point and visually disappear inside player/car geometry.
    if player_vehicle.has(player_id):
        _server_exit_vehicle(player_id)

    var cop: ViceQuestCop = cops[cop_id]
    var toward_target: Vector3 = target_vehicle.position - police_vehicle.position
    toward_target.y = 0.0
    if toward_target.length_squared() <= 0.04:
        toward_target = police_vehicle.get_forward_vector()
    toward_target = toward_target.normalized()
    var side: Vector3 = Vector3(-toward_target.z, 0.0, toward_target.x)
    var exit_position: Vector3 = police_vehicle.position + side * 2.05 + toward_target * 0.70
    exit_position.y = sample_surface_height(exit_position, police_vehicle.position.y - 0.10) + PLAYER_Y
    var threat: Vector3 = players[player_id].position if players.has(player_id) else target_vehicle.position

    var detached_id: int = _detach_police_driver(police_vehicle_id, true, exit_position, threat)
    if detached_id != 0 and cops.has(detached_id):
        var exited: ViceQuestCop = cops[detached_id]
        exited.visible = true
        exited.set_response_active(true)
        var exit_facing: Vector3 = threat - exit_position
        exit_facing.y = 0.0
        if exit_facing.length_squared() <= 0.04:
            exit_facing = toward_target
        else:
            exit_facing = exit_facing.normalized()
        _sync_cop_exit.rpc(detached_id, exited.enforcement_role, exit_position, exit_facing, exited.hp)

    _play_vehicle_door.rpc(police_vehicle.position, _vehicle_uses_heavy_door_sound(police_vehicle), false)
    _show_combat_message.rpc("Police pulled %s from the vehicle" % _display_name(player_id))
    return true
'''
main = replace_func(main, "_try_police_pin_extract", pin_extract)

# Lightbar: no stream_active dependency, larger and depth-test free.
wants_light = r'''func wants_police_light() -> bool:
    return bool(get_meta("police_fx_active", false)) and not is_destroyed and supports_police_response_fx()
'''
vehicle = replace_func(vehicle, "wants_police_light", wants_light)

lightbar = r'''func _build_police_lightbar() -> Sprite3D:
    var image: Image = Image.create(24, 7, false, Image.FORMAT_RGBA8)
    image.fill(Color(0.0, 0.0, 0.0, 0.0))
    for y in range(7):
        for x in range(24):
            if x <= 9:
                image.set_pixel(x, y, Color(0.05, 0.30, 1.0, 1.0))
            elif x >= 14:
                image.set_pixel(x, y, Color(0.38, 0.78, 1.0, 1.0))
            else:
                image.set_pixel(x, y, Color(0.92, 0.98, 1.0, 1.0))
    var texture: ImageTexture = ImageTexture.create_from_image(image)
    var light: Sprite3D = Sprite3D.new()
    light.name = "PoliceLightbar"
    light.texture = texture
    light.shaded = false
    light.centered = true
    light.double_sided = true
    light.no_depth_test = true
    light.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
    light.render_priority = 15
    light.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    if _sprite != null:
        light.transform = _sprite.transform
        light.position.y += 0.18
        light.pixel_size = maxf(_sprite.pixel_size * 1.05, 0.018)
        light.layers = _sprite.layers
    else:
        light.rotation_degrees.x = -90.0
        light.position.y = 0.22
        light.pixel_size = 0.032
    add_child(light)
    var flash: Tween = create_tween()
    flash.set_loops()
    flash.tween_property(light, "modulate", Color(1.0, 1.0, 1.0, 1.0), 0.11)
    flash.tween_property(light, "modulate", Color(0.04, 0.25, 1.0, 0.22), 0.11)
    return light
'''
vehicle = replace_func(vehicle, "_build_police_lightbar", lightbar)

# ---------------------------------------------------------------------------
# 3) Stronger, still low-restitution collision transfer.
# ---------------------------------------------------------------------------
vehicle = must_replace(vehicle, "relative_speed * 0.30 * (self_mass / total_mass), 0.45, 4.25", "relative_speed * 0.42 * (self_mass / total_mass), 0.65, 5.60", "heavier transfer")
vehicle = must_replace(vehicle, "transfer_speed * 0.14", "transfer_speed * 0.18", "attacker contact impulse")
vehicle = must_replace(vehicle, "transfer_speed * 0.72", "transfer_speed * 0.88", "longitudinal transfer")
vehicle = must_replace(vehicle, "relative_speed * 0.016 * (self_mass / total_mass), 0.035, 0.34", "relative_speed * 0.021 * (self_mass / total_mass), 0.050, 0.48", "heavier immediate shove")

# ---------------------------------------------------------------------------
# 4) Confirmed backwards SWAT artwork. Rotate the generated PNG itself so every
#    render path (normal + Quest elevated clone) gets the same corrected front.
# ---------------------------------------------------------------------------
swat_path = root / "assets" / "vehicles" / "swat_van.png"
if not swat_path.is_file():
    raise SystemExit(f"Missing SWAT texture: {swat_path}")
with Image.open(swat_path) as swat:
    fixed = swat.transpose(Image.Transpose.ROTATE_180)
    fixed.save(swat_path, optimize=True)

# ---------------------------------------------------------------------------
# 5) GTA-style vehicle name popup at right edge.
# ---------------------------------------------------------------------------
main = must_replace(
    main,
    "var gta2_hud_root: Control",
    "var gta2_hud_root: Control\nvar gta2_vehicle_name_label: Label\nvar gta2_vehicle_name_tween: Tween",
    "vehicle name HUD vars",
)

hud_anchor = '''    if quest_label != null:
        quest_label.position = Vector2(0, 0)
        quest_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

    _update_gta2_respect_ui()
'''
hud_new = '''    if quest_label != null:
        quest_label.position = Vector2(0, 0)
        quest_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER

    if gta2_vehicle_name_label == null:
        gta2_vehicle_name_label = Label.new()
        gta2_vehicle_name_label.name = "GTA2VehicleName"
        gta2_vehicle_name_label.position = Vector2(930, 590)
        gta2_vehicle_name_label.size = Vector2(300, 44)
        gta2_vehicle_name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
        gta2_vehicle_name_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
        gta2_vehicle_name_label.add_theme_font_size_override("font_size", 25)
        gta2_vehicle_name_label.add_theme_color_override("font_color", Color(1.0, 0.86, 0.30, 1.0))
        gta2_vehicle_name_label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 1.0))
        gta2_vehicle_name_label.add_theme_constant_override("outline_size", 5)
        gta2_vehicle_name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
        gta2_vehicle_name_label.visible = false
        gta2_hud_root.add_child(gta2_vehicle_name_label)

    _update_gta2_respect_ui()
'''
main = must_replace(main, hud_anchor, hud_new, "vehicle name HUD build")

show_name = r'''@rpc("authority", "call_local", "reliable")
func _show_vehicle_name(player_id: int, vehicle_name: String) -> void:
    if multiplayer.get_unique_id() != player_id or gta2_vehicle_name_label == null:
        return
    if gta2_vehicle_name_tween != null and gta2_vehicle_name_tween.is_valid():
        gta2_vehicle_name_tween.kill()
    gta2_vehicle_name_label.text = vehicle_name.to_upper()
    gta2_vehicle_name_label.modulate = Color(1.0, 1.0, 1.0, 1.0)
    gta2_vehicle_name_label.visible = true
    gta2_vehicle_name_tween = create_tween()
    gta2_vehicle_name_tween.tween_interval(2.1)
    gta2_vehicle_name_tween.tween_property(gta2_vehicle_name_label, "modulate:a", 0.0, 0.75)
    gta2_vehicle_name_tween.tween_callback(gta2_vehicle_name_label.hide)
'''
main = insert_before_func(main, "_server_enter_vehicle", show_name)
main = must_replace(
    main,
    "    _sync_vehicle_driver.rpc(vehicle_id, player_id)\n",
    "    _sync_vehicle_driver.rpc(vehicle_id, player_id)\n    _show_vehicle_name.rpc(player_id, vehicle.display_name)\n",
    "show vehicle name on enter",
)

checks = [
    ("func _traffic_voice_stream", audio),
    ("engine_standard_traffic_", str(list(sfx_dir.glob("engine_standard_traffic_*.wav")))),
    ("func update_police_sirens", audio),
    ("_siren_voice_stream", audio),
    ('@rpc("authority", "call_local", "reliable")\nfunc _sync_police_vehicle_fx', main),
    ("func _sync_cop_exit", main),
    ("gta2_vehicle_name_label", main),
    ("_show_vehicle_name.rpc", main),
    ("relative_speed * 0.42", vehicle),
    ("light.no_depth_test = true", vehicle),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"v0.6.18.29 verification failed: {needle}")

if "AudioStreamPlayer3D" in audio:
    raise SystemExit("v0.6.18.29 must stay on 18.26 manual Ear audio")

main_path.write_text(main, encoding="utf-8")
vehicle_path.write_text(vehicle, encoding="utf-8")
audio_path.write_text(audio, encoding="utf-8")
print("Applied v0.6.18.29: independent traffic/siren files, visible Cop exit, stronger impacts, SWAT rotation, vehicle-name HUD.")
