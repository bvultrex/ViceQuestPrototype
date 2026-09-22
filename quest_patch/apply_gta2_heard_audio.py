#!/usr/bin/env python3
"""v0.6.18.17 — loops the Quest can actually hear.

18.16 one-shots (guns, skid, wasted, crash) reached the headset. Engine,
radio and the city bed did not: they were a duplicate() of the imported
wav, and that copy has no PCM on the Quest export. This pass owns a real
16-bit stream, restarts it if the loop dies, and keeps the beds in the
midrange the Quest speaker can play. Car explosions use WIL samples 32
and 50 instead of the tank cannon.
"""
from pathlib import Path
import math
import random
import shutil
import struct
import sys
import wave

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent


def read(rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (root / rel).write_text(text, encoding="utf-8")


def replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing heard-audio anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"Heard-audio anchor is not unique: {label}")
    return text.replace(old, new, 1)


def write_wav(path: Path, samples: list[float], rate: int = 22050) -> None:
    peak = max((abs(sample) for sample in samples), default=1.0) or 1.0
    gain = 0.86 / peak
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for sample in samples:
            value = max(-32767, min(32767, int(sample * gain * 32767)))
            frames += struct.pack("<h", value)
        handle.writeframes(frames)


def env(index: int, total: int) -> float:
    edge = min(index, total - 1 - index, 220)
    return min(1.0, edge / 220.0)


def tone(freq: float, t: float, partial: float = 0.55) -> float:
    # Quest speakers barely move air under ~150 Hz, so every note carries
    # its octave. Otherwise a bass loop is silence in the headset.
    return math.sin(2 * math.pi * freq * t) + partial * math.sin(2 * math.pi * freq * 2.0 * t)


def make_city(rate: int = 22050) -> list[float]:
    total = rate * 4
    rng = random.Random(22)
    noise = 0.0
    out = []
    for i in range(total):
        white = rng.random() * 2.0 - 1.0
        noise = noise * 0.82 + white * 0.18
        t = i / rate
        wash = math.sin(2 * math.pi * 240 * t) * 0.08 + math.sin(2 * math.pi * 480 * t) * 0.04
        pulse = 0.55 + 0.45 * math.sin(2 * math.pi * 1.7 * t)
        whoosh = 0.0
        slot = i % rate
        if slot < int(rate * 0.18):
            whoosh = noise * (slot / (rate * 0.18)) * 0.35
        out.append((noise * 0.42 * pulse + wash + whoosh) * env(i, total))
    return out


def make_night(rate: int = 22050) -> list[float]:
    total = rate * 4
    notes = (220.0, 261.6, 329.6, 440.0, 329.6, 261.6, 220.0, 196.0)
    step = rate // 2
    out = []
    for i in range(total):
        t = i / rate
        note = notes[(i // step) % len(notes)]
        beat = (i % step) / step
        level = math.exp(-beat * 2.2)
        hat = (1.0 if (i % step) < 500 else 0.0) * math.sin(2 * math.pi * 2400 * t) * 0.08
        out.append((tone(note, t, 0.45) * 0.34 * level + hat) * env(i, total))
    return out


def make_funk(rate: int = 22050) -> list[float]:
    total = rate * 2
    beat = rate // 2
    out = []
    for i in range(total):
        t = i / rate
        beat_pos = i % beat
        kick_t = beat_pos / rate
        kick = math.sin(2 * math.pi * (180 - kick_t * 90) * kick_t) * math.exp(-kick_t * 10.0)
        kick += math.sin(2 * math.pi * 360 * kick_t) * math.exp(-kick_t * 18.0) * 0.35
        if (i // beat) % 2 == 1 and beat_pos < beat // 2:
            kick *= 0.4
        note = 110.0 if (i // (beat * 2)) % 2 == 0 else 146.8
        bass = tone(note, t, 0.7) * 0.28
        hat = (1.0 if beat_pos % (beat // 2) < 400 else 0.0) * math.sin(2 * math.pi * 3200 * t) * 0.07
        out.append((kick * 0.7 + bass + hat) * env(i, total))
    return out


def make_spark(rate: int = 22050) -> list[float]:
    total = rate * 2
    notes = (440.0, 554.4, 659.3, 880.0)
    step = rate // 4
    out = []
    for i in range(total):
        t = i / rate
        note = notes[(i // step) % len(notes)]
        gate = 1.0 if (i // step) % 2 == 0 else 0.45
        pulse = 1.0 if math.sin(2 * math.pi * 8 * t) > 0 else 0.55
        out.append(tone(note, t, 0.25) * 0.22 * gate * pulse * env(i, total))
    return out


write_wav(root / "assets/audio/gta2/beds/city.wav", make_city())
write_wav(root / "assets/audio/gta2/radio/radio_night.wav", make_night())
write_wav(root / "assets/audio/gta2/radio/radio_funk.wav", make_funk())
write_wav(root / "assets/audio/gta2/radio/radio_spark.wav", make_spark())
explosion_src = here / "sfx"
for sample_name in (
    "detonation.wav",
    "molotov_break.wav",
    "fire_loop.wav",
    "grenade_bounce.wav",
    "fist_hit.wav",
    "step_0.wav",
    "step_1.wav",
    "step_2.wav",
    "step_3.wav",
):
    src = explosion_src / sample_name
    if not src.is_file():
        raise SystemExit(f"Missing quest_patch/sfx/{sample_name}")
    dst = root / "assets/audio/gta2/sfx" / sample_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
shutil.copyfile(here / "audio_manager.gd", root / "scripts/audio_manager.gd")

main = read("scripts/main.gd")
main = replace(
    main,
    """        var crash_damage: int = vehicle.consume_crash_damage()
        if crash_damage > 0:
            _damage_vehicle(vehicle_id, crash_damage, vehicle.driver_id)
""",
    """        var crash_damage: int = vehicle.consume_crash_damage()
        if crash_damage > 0:
            _damage_vehicle(vehicle_id, crash_damage, vehicle.driver_id)
            if audio_manager != null:
                audio_manager.play_vehicle_impact(vehicle.position, crash_damage >= 20)
""",
    "crash stinger",
)
main = replace(
    main,
    """            if audio_manager != null:
                if player_vehicle.has(local_id) and vehicles.has(player_vehicle[local_id]):
                    audio_manager.update_local_vehicle(vehicles[player_vehicle[local_id]])
                else:
                    audio_manager.stop_engine()
""",
    """            if audio_manager != null:
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
                if input_bridge != null and input_bridge.consume_radio_next():
                    _show_combat_message(audio_manager.cycle_radio())
""",
    "heard mix and radio",
)
main = replace(
    main,
    """            if vehicle.has_vehicle_gun:
                mods.append("GUN")
            if vehicle.has_mines:
                mods.append("MINES")
            if vehicle.has_oil_slick:
                mods.append("OIL")
            var mod_text: String = "+".join(mods) if not mods.is_empty() else "STOCK"
""",
    """            if vehicle.has_vehicle_gun:
                mods.append("GUN")
            if vehicle.has_mines:
                mods.append("MINES")
            if vehicle.has_oil_slick:
                mods.append("OIL")
            if vehicle.has_vehicle_bomb:
                mods.append("BOMB")
            var mod_text: String = "+".join(mods) if not mods.is_empty() else "STOCK"
            if audio_manager != null:
                mod_text += " // " + audio_manager.station_name()
""",
    "hud bomb and radio",
)
write("scripts/main.gd", main)

bridge = read("scripts/input_bridge.gd")
bridge = replace(
    bridge,
    "var _ui_direction_was: Vector2i = Vector2i.ZERO\n",
    "var _ui_direction_was: Vector2i = Vector2i.ZERO\n"
    "var _radio_stick_was: bool = false\n"
    "var _radio_key_was: bool = false\n",
    "radio edge state",
)
bridge = replace(
    bridge,
    "func control_hint(on_foot: bool, in_tank: bool) -> String:\n",
    '''func consume_radio_next() -> bool:
    var stick_up: bool = false
    if xr_active and right_controller != null:
        stick_up = right_controller.get_vector2(&"primary").y >= 0.72
    var joypad: int = _first_joypad()
    if joypad >= 0 and Input.get_joy_axis(joypad, JOY_AXIS_RIGHT_Y) <= -0.72:
        stick_up = true
    var key_down: bool = Input.is_key_pressed(KEY_N)
    var edge: bool = (stick_up and not _radio_stick_was) or (key_down and not _radio_key_was)
    _radio_stick_was = stick_up
    _radio_key_was = key_down
    return edge

func control_hint(on_foot: bool, in_tank: bool) -> String:
''',
    "radio edge function",
)
bridge = replace(
    bridge,
    'return "QUEST: L-STICK drive/steer • R-TRIGGER gun • X mine • Y oil • A exit/tune"\n',
    'return "QUEST: L-STICK drive • R-STICK UP radio • R-TRIGGER gun • X mine • Y oil • A exit"\n',
    "quest car hint",
)
bridge = replace(
    bridge,
    'return "ON FOOT: WASD • E interact • SPACE/LMB attack • R reload | CAR: WASD • E exit • SPACE gun | TANK: J/L turret • SPACE cannon"\n',
    'return "ON FOOT: WASD • E interact • SPACE attack • R reload | CAR: WASD • N radio • SPACE gun | TANK: J/L turret"\n',
    "keyboard hint",
)
write("scripts/input_bridge.gd", bridge)

main = read("scripts/main.gd")
main = replace(
    main,
    """    if combat_fx != null and connected:
        combat_fx.play_impact(impact_position, stun_hit)
        combat_fx.play_knockback_dust(impact_position, 4.0)
""",
    """    if combat_fx != null and connected:
        combat_fx.play_impact(impact_position, stun_hit)
        combat_fx.play_knockback_dust(impact_position, 4.0)
    if audio_manager != null and connected and not stun_hit:
        audio_manager.play_fist_hit(impact_position)
""",
    "fist hit",
)
main = replace(
    main,
    """func _play_projectile_bounce(impact_position: Vector3, strength: float) -> void:
    if combat_fx != null:
        combat_fx.play_projectile_bounce(impact_position, strength)
""",
    """func _play_projectile_bounce(impact_position: Vector3, strength: float, bottle: bool = false) -> void:
    if combat_fx != null:
        combat_fx.play_projectile_bounce(impact_position, strength)
    if audio_manager != null and not bottle:
        audio_manager.play_grenade_bounce(impact_position, strength)

""",
    "grenade bounce",
)
main = replace(
    main,
    "_play_projectile_bounce.rpc(next_position, clampf(velocity.length() / 9.0, 0.35, 1.0))",
    "_play_projectile_bounce.rpc(next_position, clampf(velocity.length() / 9.0, 0.35, 1.0), delivery == \"thrown_fire\")",
    "bounce kind",
)
main = replace(
    main,
    """func _play_molotov_burst(impact_position: Vector3) -> void:
    var burst: AnimatedSprite3D = AnimatedSprite3D.new()
""",
    """func _play_molotov_burst(impact_position: Vector3) -> void:
    if audio_manager != null:
        audio_manager.play_molotov_break(impact_position)
    var burst: AnimatedSprite3D = AnimatedSprite3D.new()
""",
    "molotov glass",
)
main = replace(
    main,
    """    node.set_meta("remaining", duration)
    fire_zone_visuals[zone_id] = node
""",
    """    node.set_meta("remaining", duration)
    fire_zone_visuals[zone_id] = node
    if audio_manager != null:
        audio_manager.note_fire_source("zone:%d" % zone_id, zone_position, true)
""",
    "fire zone on",
)
main = replace(
    main,
    """func _remove_fire_zone_visual(zone_id: int) -> void:
    if fire_zone_visuals.has(zone_id):
        fire_zone_visuals[zone_id].queue_free()
        fire_zone_visuals.erase(zone_id)
""",
    """func _remove_fire_zone_visual(zone_id: int) -> void:
    if fire_zone_visuals.has(zone_id):
        fire_zone_visuals[zone_id].queue_free()
        fire_zone_visuals.erase(zone_id)
    if audio_manager != null:
        audio_manager.note_fire_source("zone:%d" % zone_id, Vector3.ZERO, false)
""",
    "fire zone off",
)
main = replace(
    main,
    """    var target: Node3D = _burn_target_node(parts[0], int(parts[1]))
    combat_fx.set_burning(burn_key, target, active)
""",
    """    var target: Node3D = _burn_target_node(parts[0], int(parts[1]))
    combat_fx.set_burning(burn_key, target, active)
    if audio_manager != null and target != null:
        audio_manager.note_fire_source(burn_key, target.position, active)
""",
    "npc fire",
)
write("scripts/main.gd", main)

for rel, needle in (
    ("scripts/audio_manager.gd", "func note_footstep("),
    ("scripts/audio_manager.gd", "func play_fist_hit("),
    ("scripts/audio_manager.gd", "func note_fire_source("),
    ("scripts/audio_manager.gd", '"detonation"'),
    ("scripts/main.gd", "audio_manager.play_fist_hit"),
    ("scripts/main.gd", "audio_manager.play_grenade_bounce"),
    ("scripts/main.gd", "audio_manager.play_molotov_break"),
    ("scripts/main.gd", "audio_manager.note_footstep"),
    ("scripts/main.gd", "note_fire_source"),
    ("scripts/main.gd", "crash_damage >= 20"),
):
    if needle not in read(rel):
        raise SystemExit(f"Heard-audio patch did not land: {rel} / {needle}")
if '"car_explosion"' in read("scripts/audio_manager.gd"):
    raise SystemExit("explosion still uses the old boom")
if '_hold_loop(bed_player, "city"' in read("scripts/audio_manager.gd"):
    raise SystemExit("synth city bed is still playing")
for rel in (
    "assets/audio/gta2/sfx/detonation.wav",
    "assets/audio/gta2/sfx/molotov_break.wav",
    "assets/audio/gta2/sfx/fire_loop.wav",
    "assets/audio/gta2/sfx/grenade_bounce.wav",
    "assets/audio/gta2/sfx/fist_hit.wav",
    "assets/audio/gta2/sfx/step_0.wav",
):
    if not (root / rel).is_file() or (root / rel).stat().st_size < 500:
        raise SystemExit(f"Missing generated audio: {rel}")


for rel, needle in (
    ("scripts/audio_manager.gd", "func set_ear("),
    ("scripts/audio_manager.gd", "RADIO // FUNK"),
    ("scripts/audio_manager.gd", "func note_skid("),
    ("scripts/audio_manager.gd", "func _owned_loop("),
    ("scripts/audio_manager.gd", "func _service_loop("),
    ("scripts/main.gd", "audio_manager.play_vehicle_impact"),
    ("scripts/main.gd", "audio_manager.set_ear(target)"),
    ("scripts/main.gd", "consume_radio_next()"),
    ("scripts/main.gd", 'mods.append("BOMB")'),
    ("scripts/input_bridge.gd", "func consume_radio_next()"),
):
    if needle not in read(rel):
        raise SystemExit(f"Heard-audio patch did not land: {rel} / {needle}")
if ".duplicate()" in read("scripts/audio_manager.gd"):
    raise SystemExit("audio_manager still duplicates streams")
for rel in (
    "assets/audio/gta2/beds/city.wav",
    "assets/audio/gta2/radio/radio_night.wav",
    "assets/audio/gta2/radio/radio_funk.wav",
    "assets/audio/gta2/radio/radio_spark.wav",
):
    if not (root / rel).is_file() or (root / rel).stat().st_size < 1000:
        raise SystemExit(f"Missing generated audio: {rel}")

print("Quest heard-audio mix applied.")
