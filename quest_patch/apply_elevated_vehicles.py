#!/usr/bin/env python3
"""v0.6.18.15 — draw elevated vehicles on the Quest popout, and fund a test wallet.

Hardware 18.14: Fruitbat (northwest, z=3) hides the car under the stereo roof.
Only on-foot pawns were cloned. This patch clones vehicle body + tank turret
the same way, and grants $50000 so one pass can buy every Downtown stall.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()


def read(rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (root / rel).write_text(text, encoding="utf-8")


def replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing elevated-vehicle patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"Elevated-vehicle patch anchor is not unique: {label}")
    return text.replace(old, new, 1)


vehicle = read("scripts/vehicle.gd")
getter = '''
func get_sprite() -> Sprite3D:
    return _sprite

func get_turret_sprite() -> Sprite3D:
    return _turret_sprite

func wants_board_sprite() -> bool:
    return stream_active or not ambient_pool_member

func wants_turret_sprite() -> bool:
    return variant_id == "tank" and stream_active and not is_destroyed and _turret_sprite != null
'''
if "func get_sprite() -> Sprite3D:" not in vehicle:
    if not vehicle.endswith("\n"):
        vehicle += "\n"
    vehicle += getter
write("scripts/vehicle.gd", vehicle)

main = read("scripts/main.gd")
main = replace(
    main,
    "const STARTING_CASH: int = 0\n",
    "const STARTING_CASH: int = 50000\n",
    "test wallet",
)
main = replace(
    main,
    "                presentation_rig.sync_elevated_pawns(players)\n",
    "                presentation_rig.sync_elevated_pawns(players)\n"
    "                presentation_rig.sync_elevated_vehicles(vehicles)\n",
    "vehicle popout sync",
)
write("scripts/main.gd", main)

for rel, needle in (
    ("scripts/vehicle.gd", "func get_sprite() -> Sprite3D:"),
    ("scripts/vehicle.gd", "func wants_board_sprite() -> bool:"),
    ("scripts/vehicle.gd", "func wants_turret_sprite() -> bool:"),
    ("scripts/main.gd", "const STARTING_CASH: int = 50000"),
    ("scripts/main.gd", "presentation_rig.sync_elevated_vehicles(vehicles)"),
):
    if needle not in read(rel):
        raise SystemExit(f"Elevated-vehicle patch did not land: {rel} / {needle}")

print("Elevated vehicle Quest overlay patch applied.")
