#!/usr/bin/env python3
"""ViceQuest v0.6.18.33 audio/light cleanup and reverse-skid fix.

Runs after v0.6.18.32.

Hardware feedback:
- lighting works, but should read a bit stronger
- some vehicle lights remain after pooled traffic despawns
- spawn-area traffic engines briefly sound doubled/chorused
- reverse driving leaves fading skull/blob decals

Fixes:
- stronger curb, headlight, beam and taillight presentation
- strict ambient-pool light eligibility + explicit holder reset
- clustered engine de-duplication, staggered loop phase and fade-in
- signed-speed skid logic so reverse throttle is not treated as braking
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
audio_path = root / "scripts" / "audio_manager.gd"
combat_path = root / "scripts" / "combat_fx.gd"

main = main_path.read_text(encoding="utf-8")
audio = audio_path.read_text(encoding="utf-8")
combat = combat_path.read_text(encoding="utf-8")

def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    hits = text.count(old)
    if hits < count:
        raise SystemExit(f"Missing v0.6.18.33 anchor {label}: found {hits}, need {count}")
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
# 1) Traffic audio: remove the synchronized three-engine chorus at spawn.
# ---------------------------------------------------------------------------
traffic_func = r'''func update_nearby_traffic(vehicles: Dictionary) -> void:
    if traffic_players.is_empty():
        return

    var ranked: Array[Dictionary] = []
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
        # Pooled traffic must actually be streamed. ai_controlled can remain
        # true for a frame after recycling and must not resurrect its sound.
        if ambient_member and not streamed and not occupied:
            continue
        if not ambient_member and not streamed and not occupied and not ai_active:
            continue

        var pos3: Vector3 = (candidate as Node3D).position
        var pos2: Vector2 = Vector2(pos3.x, pos3.z)
        var distance: float = pos2.distance_to(Vector2(_ear.x, _ear.z))
        if distance > 36.0:
            continue

        var variant: String = str(candidate.get("variant_id"))
        var key: String = String(ENGINE_BY_VARIANT.get(variant, "engine_standard"))
        var entry: Dictionary = {
            "node": candidate,
            "id": vehicle_id,
            "distance": distance,
            "pos": pos2,
            "variant": variant,
            "key": key,
        }

        var inserted: bool = false
        for slot in range(ranked.size()):
            if distance < float((ranked[slot] as Dictionary)["distance"]):
                ranked.insert(slot, entry)
                inserted = true
                break
        if not inserted:
            ranked.append(entry)
        while ranked.size() > 10:
            ranked.pop_back()

    # Manual-Ear audio has no true spatial separation. Do not mix two copies of
    # the same engine family when their cars are nearly on top of each other.
    var chosen: Array[Dictionary] = []
    for entry_variant: Variant in ranked:
        var entry: Dictionary = entry_variant
        var clustered: bool = false
        for selected_variant: Variant in chosen:
            var selected: Dictionary = selected_variant
            if String(entry["key"]) == String(selected["key"]):
                var pos_a: Vector2 = entry["pos"]
                var pos_b: Vector2 = selected["pos"]
                if pos_a.distance_to(pos_b) < 4.8:
                    clustered = true
                    break
        if clustered:
            continue
        chosen.append(entry)
        if chosen.size() >= traffic_players.size():
            break

    for index in range(traffic_players.size()):
        var player: AudioStreamPlayer = traffic_players[index]
        if index >= chosen.size():
            _traffic_wanted[index] = false
            _traffic_ids[index] = -1
            _traffic_keys[index] = ""
            if player.playing:
                player.stop()
            player.stream = null
            continue

        var entry: Dictionary = chosen[index]
        var near_vehicle: Node = entry["node"]
        var vehicle_id: int = int(entry["id"])
        var distance: float = float(entry["distance"])
        var variant: String = String(entry["variant"])
        var key: String = String(entry["key"])

        if key != _traffic_keys[index] or player.stream == null or _traffic_ids[index] != vehicle_id:
            _traffic_keys[index] = key
            _traffic_ids[index] = vehicle_id
            player.stop()
            player.stream = _traffic_voice_stream(key, index)
            player.set_meta("loop_pos", -1.0)
            player.set_meta("loop_stall", 0.0)
            player.volume_db = -32.0
            if player.stream != null:
                var length: float = player.stream.get_length()
                var phase: float = 0.0
                if length > 0.20:
                    phase = fposmod(float(posmod(vehicle_id, 19)) * 0.173 + float(index) * 0.431, maxf(0.05, length - 0.05))
                player.set_meta("loop_restart_offset", phase)
                player.play(phase)

        if player.stream == null:
            _traffic_wanted[index] = false
            continue

        var raw_speed: float = absf(float(near_vehicle.get("current_speed")))
        var max_speed: float = maxf(float(near_vehicle.get("max_forward_speed")), 0.1)
        var speed_ratio: float = maxf(clampf(raw_speed / max_speed, 0.0, 1.0), 0.18)
        var nearness: float = 1.0 - clampf(distance / 36.0, 0.0, 1.0)
        player.pitch_scale = (0.76 + speed_ratio * (0.34 if variant == "tank" else 0.60)) * (0.955 + float(index) * 0.047)
        var target_db: float = lerpf(-14.0, -1.0, pow(nearness, 1.22)) - (4.0 if _driving else 0.0)
        var fade: float = clampf(get_process_delta_time() * 8.0, 0.0, 1.0)
        player.volume_db = lerpf(player.volume_db, target_db, fade)
        _traffic_wanted[index] = true
        _service_loop(player)
'''
audio = replace_func(audio, "update_nearby_traffic", traffic_func)

service_func = r'''func _service_loop(player: AudioStreamPlayer) -> void:
    if player == null or player.stream == null:
        return
    var restart_offset: float = float(player.get_meta("loop_restart_offset", 0.0))
    if not player.playing:
        player.set_meta("loop_stall", 0.0)
        player.play(restart_offset)
        return
    var length: float = player.stream.get_length()
    var pos: float = player.get_playback_position()
    var last: float = float(player.get_meta("loop_pos", -1.0))
    var stall: float = float(player.get_meta("loop_stall", 0.0))
    if last >= 0.0 and absf(pos - last) < 0.002:
        stall += get_process_delta_time()
    else:
        stall = 0.0
    player.set_meta("loop_pos", pos)
    player.set_meta("loop_stall", stall)
    if (length > 0.05 and pos >= length - 0.02) or stall > 0.12:
        player.set_meta("loop_stall", 0.0)
        player.play(restart_offset)
'''
audio = replace_func(audio, "_service_loop", service_func)

# ---------------------------------------------------------------------------
# 2) Reverse skid bug: keep signed speed so reverse throttle is not braking.
# ---------------------------------------------------------------------------
skid_func = r'''func play_skid_mark(world_position: Vector3, forward: Vector3, signed_speed: float = 0.0, max_speed: float = 1.0, steer_amount: float = 0.0, throttle: float = 0.0) -> void:
    var speed: float = absf(signed_speed)
    var ratio: float = clampf(speed / maxf(max_speed, 0.1), 0.0, 1.0)
    var sliding: bool = ratio > 0.45 and steer_amount > 0.48

    # Brake means input opposes actual travel direction. Holding reverse while
    # already reversing is propulsion, not braking.
    var braking_forward: bool = signed_speed > 0.18 and throttle < -0.28
    var braking_reverse: bool = signed_speed < -0.18 and throttle > 0.28
    var braking: bool = (braking_forward or braking_reverse) and ratio > 0.30

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
    var yaw: float = rad_to_deg(atan2(flat.x, flat.z)) - 90.0

    if braking and not sliding:
        var blob: Texture2D = _gta_tex("skid_blob")
        if blob != null:
            _spawn_gta_decal(blob, world_position, yaw + randf_range(-8.0, 8.0), 0.040, 4.2, 0.62, "skid")
        return

    var streak: Texture2D = _gta_tex("skid")
    if streak == null:
        return
    var side: Vector3 = Vector3(-flat.z, 0.0, flat.x)
    for offset in [-0.36, 0.36]:
        _spawn_gta_decal(streak, world_position + side * offset, yaw, 0.042, 5.2, 0.74, "skid")
'''
combat = replace_func(combat, "play_skid_mark", skid_func)

main = must_replace(
    main,
    "combat_fx.play_skid_mark(driven.position, driven.get_forward_vector(), absf(driven.current_speed), driven.max_forward_speed, steer_amount, throttle)",
    "combat_fx.play_skid_mark(driven.position, driven.get_forward_vector(), driven.current_speed, driven.max_forward_speed, steer_amount, throttle)",
    "signed skid speed",
)

# ---------------------------------------------------------------------------
# 3) Stronger lighting and hard cleanup for despawned pooled cars.
# ---------------------------------------------------------------------------
main = must_replace(main, '_make_light_sprite("HeadLeft", gta2_headlight_texture, 0.026, 22)', '_make_light_sprite("HeadLeft", gta2_headlight_texture, 0.032, 22)', "head left strength")
main = must_replace(main, '_make_light_sprite("HeadRight", gta2_headlight_texture, 0.026, 22)', '_make_light_sprite("HeadRight", gta2_headlight_texture, 0.032, 22)', "head right strength")
main = must_replace(main, '_make_light_sprite("TailLeft", gta2_taillight_texture, 0.022, 22)', '_make_light_sprite("TailLeft", gta2_taillight_texture, 0.027, 22)', "tail left strength")
main = must_replace(main, '_make_light_sprite("TailRight", gta2_taillight_texture, 0.022, 22)', '_make_light_sprite("TailRight", gta2_taillight_texture, 0.027, 22)', "tail right strength")
main = must_replace(main, '_make_light_sprite("Beam", gta2_headbeam_texture, 0.055, 20)', '_make_light_sprite("Beam", gta2_headbeam_texture, 0.070, 20)', "beam strength")

hide_helper = r'''func _hide_vehicle_light_holder(holder: Node3D) -> void:
    if holder == null:
        return
    for child: Node in holder.get_children():
        if child is Sprite3D:
            (child as Sprite3D).visible = false
    holder.visible = false
'''
main = insert_before_func(main, "_update_gta2_vehicle_lights", hide_helper)

vehicle_lights = r'''func _update_gta2_vehicle_lights() -> void:
    if gta2_vehicle_light_pool.is_empty():
        return
    if gta2_night_factor <= 0.03:
        for holder in gta2_vehicle_light_pool:
            _hide_vehicle_light_holder(holder)
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

        var streamed: bool = bool(vehicle.get("stream_active"))
        var ambient_member: bool = bool(vehicle.get("ambient_pool_member"))
        var occupied: bool = int(vehicle.get("driver_id")) != 0
        var ai_active: bool = bool(vehicle.get("ai_controlled"))
        var police_fx: bool = bool(vehicle.get_meta("police_fx_active", false))

        # Ambient pool cars can retain ai_controlled for a recycle tick. They
        # only own light while actually streamed (or actively occupied).
        var active: bool
        if ambient_member:
            active = streamed or occupied
        else:
            active = streamed or occupied or ai_active or police_fx
        if not active:
            continue

        if vehicle.has_method("wants_board_sprite") and not bool(vehicle.call("wants_board_sprite")) and not occupied and not police_fx:
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
            _hide_vehicle_light_holder(holder)
            continue

        var vehicle: Node = (chosen[pool_index] as Dictionary)["node"]
        if vehicle == null or not is_instance_valid(vehicle):
            _hide_vehicle_light_holder(holder)
            continue

        var forward: Vector3 = vehicle.call("get_forward_vector")
        forward.y = 0.0
        if forward.length_squared() <= 0.001:
            _hide_vehicle_light_holder(holder)
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
        head_left.modulate = Color(1.0, 0.95, 0.74, 1.0 * intensity)
        head_right.modulate = head_left.modulate
        tail_left.modulate = Color(1.0, 0.045, 0.018, 1.0 * intensity)
        tail_right.modulate = tail_left.modulate
        beam.modulate = Color(1.0, 0.92, 0.68, 0.84 * intensity)

        _set_ground_sprite_transform(head_left, front_center - side * width_scale, forward, side)
        _set_ground_sprite_transform(head_right, front_center + side * width_scale, forward, side)
        _set_ground_sprite_transform(tail_left, rear_center - side * width_scale, forward, side)
        _set_ground_sprite_transform(tail_right, rear_center + side * width_scale, forward, side)

        var beam_position: Vector3 = base + forward * (length_scale + 1.80)
        beam_position.y = surface_y + 0.052
        _set_ground_sprite_transform(beam, beam_position, forward, side)

        holder.visible = true
        head_left.visible = true
        head_right.visible = true
        tail_left.visible = true
        tail_right.visible = true
        beam.visible = variant != "tank"
'''
main = replace_func(main, "_update_gta2_vehicle_lights", vehicle_lights)

# Stronger curb/street corona.
main = must_replace(
    main,
    'glow.pixel_size = maxf(0.018, (world_radius * 1.55) / 64.0)',
    'glow.pixel_size = maxf(0.024, (world_radius * 2.05) / 64.0)',
    "curb glow size",
)
main = must_replace(
    main,
    'clampf((0.45 + gta2_night_factor * 0.55) * intensity, 0.0, 1.0)',
    'clampf((0.62 + gta2_night_factor * 0.72) * intensity, 0.0, 1.0)',
    "curb glow alpha",
)

checks = [
    ("loop_restart_offset", audio),
    ("ranked: Array[Dictionary]", audio),
    ("pos_a.distance_to(pos_b) < 4.8", audio),
    ("signed_speed", combat),
    ("braking_reverse", combat),
    ("driven.current_speed, driven.max_forward_speed", main),
    ("func _hide_vehicle_light_holder", main),
    ("if ambient_member:", main),
    ("world_radius * 2.05", main),
    ('_make_light_sprite("Beam", gta2_headbeam_texture, 0.070, 20)', main),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"v0.6.18.33 verification failed: {needle}")

main_path.write_text(main, encoding="utf-8")
audio_path.write_text(audio, encoding="utf-8")
combat_path.write_text(combat, encoding="utf-8")
print("Applied v0.6.18.33: stronger lights, no pooled ghost lights, de-chorused spawn engines, reverse skid fix.")
