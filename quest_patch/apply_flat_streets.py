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
    "var downtown_ground_layers: PackedByteArray = PackedByteArray()\n",
    "var downtown_ground_layers: PackedByteArray = PackedByteArray()\n"
    "var downtown_station_floor: PackedByteArray = PackedByteArray()\n",
    "station floor buffer",
)
main = replace(
    main,
    "        downtown_ground_layers = ground_file.get_buffer(ground_file.get_length())\n",
    "        downtown_ground_layers = ground_file.get_buffer(ground_file.get_length())\n"
    "    var station_file: FileAccess = FileAccess.open(\"res://assets/gta2/downtown/downtown_station_floor.bin\", FileAccess.READ)\n"
    "    if station_file != null:\n"
    "        downtown_station_floor = station_file.get_buffer(station_file.get_length())\n",
    "station floor load",
)
main = replace(
    main,
    "    return Vector2i(best_slope, best_ground)\n",
    "    return Vector2i(best_slope, best_ground)\n"
    "\n"
    "func _on_station_floor(world_position: Vector3, current_surface_y: float) -> bool:\n"
    "    if downtown_station_floor.size() < 256 * 256 * 8:\n"
    "        return false\n"
    "    if downtown_surface_mask.size() < 256 * 256 or downtown_slope_layers.size() < 256 * 256 * 8:\n"
    "        return false\n"
    "    var tile_size: float = DOWNTOWN_DATA.TILE_SIZE\n"
    "    var height_unit: float = DOWNTOWN_DATA.HEIGHT_UNIT\n"
    "    var cell_x: int = clampi(floori(world_position.x / tile_size), 0, 255)\n"
    "    var cell_y: int = clampi(floori(world_position.z / tile_size), 0, 255)\n"
    "    var cell_index: int = cell_y * 256 + cell_x\n"
    "    var mask: int = int(downtown_surface_mask[cell_index])\n"
    "    var local_x: float = fposmod(world_position.x, tile_size) / tile_size\n"
    "    var source_local_y: float = 1.0 - fposmod(world_position.z, tile_size) / tile_size\n"
    "    var best_z: int = -1\n"
    "    var best_distance: float = INF\n"
    "    for z_level in range(8):\n"
    "        if (mask & (1 << z_level)) == 0:\n"
    "            continue\n"
    "        var slope_type: int = int(downtown_slope_layers[cell_index * 8 + z_level])\n"
    "        var local_height: float = _slope_local_height(slope_type, local_x, source_local_y)\n"
    "        var surface_y: float = (float(z_level) + local_height - 1.0) * height_unit\n"
    "        var distance: float = absf(surface_y - current_surface_y)\n"
    "        if distance < best_distance:\n"
    "            best_distance = distance\n"
    "            best_z = z_level\n"
    "    if best_z < 0:\n"
    "        return false\n"
    "    return downtown_station_floor[cell_index * 8 + best_z] != 0\n"
    "\n"
    "func surface_is_building_roof(world_position: Vector3) -> bool:\n"
    "    var info: Vector2i = _surface_block_info(world_position, world_position.y - 0.12)\n"
    "    if info.y == 3:\n"
    "        return true\n"
    "    return _on_station_floor(world_position, world_position.y - 0.12)\n",
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
    ("scripts/main.gd", "func _on_station_floor"),
    ("scripts/main.gd", "presentation_rig.sync_elevated_pawns(elevated_peds)"),
    ("scripts/cop.gd", "func get_ped_sprite()"),
    ("scripts/civilian.gd", "func get_ped_sprite()"),
):
    if needle not in read(rel):
        raise SystemExit(f"Flat-street patch did not land: {rel} / {needle}")

print("Flat street Quest overlay patch applied.")
