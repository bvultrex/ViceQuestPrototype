#!/usr/bin/env python3
"""v0.6.18.16 — make GTA2 audio audible on Quest and add a car radio.

The headset listener sits in the room, so the old 3D engine at city coordinates
was silent. This mix is 2D from the player: engines, crashes, skids, weapons,
a quiet city bed, and three original station loops (not the commercial GTA2
soundtrack). Right-stick up or N cycles the station.
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for sample in samples:
            value = max(-32767, min(32767, int(sample * 32767)))
            frames += struct.pack("<h", value)
        handle.writeframes(frames)


def env(index: int, total: int) -> float:
    # Equal-power loop: fade the seam so LOOP_FORWARD does not click.
    edge = min(index, total - 1 - index, 180)
    return min(1.0, edge / 180.0)


def make_city(rate: int = 22050) -> list[float]:
    total = rate * 3
    rng = random.Random(22)
    noise = 0.0
    out = []
    for i in range(total):
        noise = noise * 0.985 + (rng.random() * 2.0 - 1.0) * 0.015
        t = i / rate
        hum = math.sin(2 * math.pi * 46 * t) * 0.045
        wash = math.sin(2 * math.pi * 92 * t) * 0.012
        out.append((noise * 0.55 + hum + wash) * env(i, total))
    return out


def make_night(rate: int = 22050) -> list[float]:
    total = rate * 4
    out = []
    for i in range(total):
        t = i / rate
        bass = math.sin(2 * math.pi * 55 * t) * 0.22
        fifth = math.sin(2 * math.pi * 82.5 * t) * 0.06
        slow = 0.65 + 0.35 * math.sin(2 * math.pi * 0.25 * t)
        hat = (1.0 if (i % 5512) < 700 else 0.0) * math.sin(2 * math.pi * 1800 * t) * 0.015
        out.append((bass + fifth) * slow * env(i, total) + hat)
    return out


def make_funk(rate: int = 22050) -> list[float]:
    total = rate * 2
    beat = rate // 2
    out = []
    for i in range(total):
        t = i / rate
        beat_pos = i % beat
        kick_t = beat_pos / rate
        kick = math.sin(2 * math.pi * (90 - kick_t * 40) * kick_t) * math.exp(-kick_t * 14.0) * 0.55
        if (i // beat) % 2 == 1 and beat_pos < beat // 2:
            kick *= 0.35
        note = 49.0 if (i // (beat * 2)) % 2 == 0 else 65.4
        bass = math.sin(2 * math.pi * note * t) * 0.18
        hat = (1.0 if beat_pos % (beat // 2) < 500 else 0.0) * math.sin(2 * math.pi * 4200 * t) * 0.03
        out.append((kick + bass + hat) * env(i, total))
    return out


def make_spark(rate: int = 22050) -> list[float]:
    total = rate * 2
    out = []
    for i in range(total):
        t = i / rate
        gate = 1.0 if (i // 2756) % 2 == 0 else 0.35
        tone = math.sin(2 * math.pi * 220 * t) * 0.08 + math.sin(2 * math.pi * 329.6 * t) * 0.05
        pulse = 1.0 if math.sin(2 * math.pi * 8 * t) > 0 else 0.4
        out.append(tone * gate * pulse * env(i, total))
    return out


write_wav(root / "assets/audio/gta2/beds/city.wav", make_city())
write_wav(root / "assets/audio/gta2/radio/radio_night.wav", make_night())
write_wav(root / "assets/audio/gta2/radio/radio_funk.wav", make_funk())
write_wav(root / "assets/audio/gta2/radio/radio_spark.wav", make_spark())
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
                audio_manager.play_vehicle_impact(vehicle.position, crash_damage >= 12)
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

for rel, needle in (
    ("scripts/audio_manager.gd", "func set_ear("),
    ("scripts/audio_manager.gd", "RADIO // FUNK"),
    ("scripts/audio_manager.gd", "func note_skid("),
    ("scripts/main.gd", "audio_manager.play_vehicle_impact"),
    ("scripts/main.gd", "audio_manager.set_ear(target)"),
    ("scripts/main.gd", "consume_radio_next()"),
    ("scripts/main.gd", 'mods.append("BOMB")'),
    ("scripts/input_bridge.gd", "func consume_radio_next()"),
):
    if needle not in read(rel):
        raise SystemExit(f"Heard-audio patch did not land: {rel} / {needle}")
for rel in (
    "assets/audio/gta2/beds/city.wav",
    "assets/audio/gta2/radio/radio_night.wav",
    "assets/audio/gta2/radio/radio_funk.wav",
    "assets/audio/gta2/radio/radio_spark.wav",
):
    if not (root / rel).is_file():
        raise SystemExit(f"Missing generated audio: {rel}")

print("Quest heard-audio mix applied.")
