#!/usr/bin/env python3
"""v0.6.18.20 — keep elevated roads on the flat board.

The stereo lid was a second copy of the road, so the street floated over its
own texture and covered NPCs. Roads and pavement stay flat, ramps included.
Only a real building roof (ground type 3) still pops out, and cops and
civilians on that roof are copied with the player.
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
        raise SystemExit(f"Missing flat-street patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"Flat-street patch anchor is not unique: {label}")
    return text.replace(old, new, 1)


GETTER = """
func get_ped_sprite() -> SpriteBase3D:
    if _visual != null and _visual.has_method("get_sprite"):
        return _visual.get_sprite()
    return null
"""

for rel in ("scripts/cop.gd", "scripts/civilian.gd"):
    body = read(rel)
    if "func get_ped_sprite()" not in body:
        if not body.endswith("\n"):
            body += "\n"
        body += GETTER
        write(rel, body)

main = read("scripts/main.gd")
main = replace(
    main,
    "    return Vector2i(best_slope, best_ground)\n",
    "    return Vector2i(best_slope, best_ground)\n"
    "\n"
    "func surface_is_building_roof(world_position: Vector3) -> bool:\n"
    "    var info: Vector2i = _surface_block_info(world_position, world_position.y - 0.12)\n"
    "    return info.y == 3\n",
    "roof query",
)
main = replace(
    main,
    "                presentation_rig.sync_elevated_pawns(players)\n",
    "                var elevated_peds: Dictionary = {}\n"
    "                for raw_pawn_id in players.keys():\n"
    "                    elevated_peds[\"p%s\" % str(raw_pawn_id)] = players[raw_pawn_id]\n"
    "                for raw_pawn_id in cops.keys():\n"
    "                    elevated_peds[\"c%s\" % str(raw_pawn_id)] = cops[raw_pawn_id]\n"
    "                for raw_pawn_id in civilians.keys():\n"
    "                    elevated_peds[\"n%s\" % str(raw_pawn_id)] = civilians[raw_pawn_id]\n"
    "                presentation_rig.sync_elevated_pawns(elevated_peds)\n",
    "npc popout roster",
)
write("scripts/main.gd", main)

for rel, needle in (
    ("scripts/main.gd", "func surface_is_building_roof"),
    ("scripts/main.gd", "presentation_rig.sync_elevated_pawns(elevated_peds)"),
    ("scripts/cop.gd", "func get_ped_sprite()"),
    ("scripts/civilian.gd", "func get_ped_sprite()"),
):
    if needle not in read(rel):
        raise SystemExit(f"Flat-street patch did not land: {rel} / {needle}")

print("Flat street Quest overlay patch applied.")
