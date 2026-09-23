#!/usr/bin/env python3
"""v0.6.18.27 pedestrian/nearby traffic engine fix.

Runs after apply_gta2_city_voice.py on the proven v0.6.18.26 audio stack.
Keeps the 2D/manual Ear mixer and the 18.26 per-voice PCM ownership fix.
No AudioStreamPlayer3D is introduced.

The 18.26 selector discarded a traffic vehicle whenever its local current_speed
was near zero. On Quest, remote/AI presentation can be visibly moving while
that replicated property is stale or zero, which leaves pedestrians with no
traffic engine voices. Select active AI/driver vehicles too, and only use
current_speed as one signal for pitch.
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
audio_path = root / "scripts" / "audio_manager.gd"
audio = audio_path.read_text(encoding="utf-8")

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

traffic = """func update_nearby_traffic(vehicles: Dictionary) -> void:
    # Keep three bounded voices for Quest, but do not require remote current_speed
    # to be authoritative. AI/occupied vehicles may be visibly moving while the
    # local replicated speed still reads zero.
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

        var raw_speed: float = absf(float(candidate.get("current_speed")))
        var ai_active: bool = bool(candidate.get("ai_controlled"))
        var occupied: bool = int(candidate.get("driver_id")) != 0
        var stream_value: Variant = candidate.get("stream_active")
        var streamed: bool = true if stream_value == null else bool(stream_value)
        if not streamed and not occupied:
            continue
        if raw_speed < 0.12 and not ai_active and not occupied:
            continue

        var pos: Vector3 = (candidate as Node3D).position
        var distance: float = Vector2(pos.x - _ear.x, pos.z - _ear.z).length()
        if distance > 46.0:
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
        if bool(near_vehicle.get("ai_controlled")) or int(near_vehicle.get("driver_id")) != 0:
            speed_ratio = maxf(speed_ratio, 0.28)

        var nearness: float = 1.0 - clampf(chosen_dist[index] / 46.0, 0.0, 1.0)
        player.pitch_scale = (0.78 + speed_ratio * (0.34 if variant == "tank" else 0.62)) * (0.94 + float(index) * 0.05)
        var loud: float = lerpf(-14.0, -1.5, pow(nearness, 1.35))
        if _driving:
            loud -= 4.5
        player.volume_db = loud
        _traffic_wanted[index] = true
        _service_loop(player)
"""
traffic = traffic.replace("    ", "\t")
audio = replace_func(audio, "update_nearby_traffic", traffic)

for needle in (
    "distance > 46.0",
    "ai_active",
    "speed_ratio = maxf(speed_ratio, 0.28)",
    "lerpf(-14.0, -1.5",
    "func _owned_loop_instance",
    "src.data.duplicate()",
):
    if needle not in audio:
        raise SystemExit(f"v0.6.18.27 traffic-audio verification failed: {needle}")

if "AudioStreamPlayer3D" in audio:
    raise SystemExit("v0.6.18.27 must stay on the 18.26 2D Ear mixer")

audio_path.write_text(audio, encoding="utf-8")
print("Applied v0.6.18.27 pedestrian traffic engines on the v0.6.18.26 audio stack.")
