#!/usr/bin/env python3
"""v0.6.18.13 — copy elevated player sprites onto the Quest popout layer.

Run AFTER apply_shock_animation_upgrade.py. Walkable field roofs live only in
the stereo popout, so the SubViewport ped disappears under the plaza lid.
This patch exposes the live ped sprite and asks presentation_rig to clone it
into popout_root at world XYZ (world Y pops out of the board).
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
        raise SystemExit(f"Missing elevated-pawn patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"Elevated-pawn patch anchor is not unique: {label}")
    return text.replace(old, new, 1)


ped = read("scripts/ped_animation.gd")
ped = replace(
    ped,
    "    _sprite.shaded = false\n    _sprite.centered = true\n    add_child(_sprite)\n",
    "    _sprite.shaded = false\n    _sprite.centered = true\n"
    "    _sprite.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD\n"
    "    _sprite.render_priority = 1\n"
    "    add_child(_sprite)\n",
    "ped sprite alpha cut",
)
if "func get_sprite() -> SpriteBase3D:" not in ped:
    if not ped.endswith("\n"):
        ped += "\n"
    ped += (
        "\nfunc get_sprite() -> SpriteBase3D:\n"
        "    return _sprite\n"
    )
write("scripts/ped_animation.gd", ped)

player = read("scripts/player.gd")
player_getter = '''
func get_ped_sprite() -> SpriteBase3D:
    if _ped_visual != null and _ped_visual.has_method("get_sprite"):
        return _ped_visual.get_sprite()
    return null
'''
if "func get_ped_sprite()" not in player:
    facing = '''func _update_visual_facing() -> void:
    if _sprite_pivot == null or facing.length_squared() <= 0.0:
        return
    var raw_angle: float = atan2(facing.x, -facing.z)
    var snapped_angle: float = round(raw_angle / FACING_STEP_RADIANS) * FACING_STEP_RADIANS
    _sprite_pivot.rotation.y = -snapped_angle
'''
    player = replace(player, facing, facing + player_getter, "player visual facing")
write("scripts/player.gd", player)

main = read("scripts/main.gd")
old_follow = """            if presentation_rig != null:
                presentation_rig.follow_target(target, delta)
            if audio_manager != null:
"""
new_follow = """            if presentation_rig != null:
                presentation_rig.follow_target(target, delta)
                presentation_rig.sync_elevated_pawns(players)
            if audio_manager != null:
"""
main = replace(main, old_follow, new_follow, "main follow_target pawn sync")
write("scripts/main.gd", main)

for rel, needle in (
    ("scripts/ped_animation.gd", "func get_sprite() -> SpriteBase3D:"),
    ("scripts/ped_animation.gd", "ALPHA_CUT_DISCARD"),
    ("scripts/player.gd", "func get_ped_sprite() -> SpriteBase3D:"),
    ("scripts/main.gd", "presentation_rig.sync_elevated_pawns(players)"),
):
    text = read(rel)
    if needle not in text:
        raise SystemExit(f"Elevated-pawn patch did not land: {rel} / {needle}")

print("Elevated pawn Quest overlay patch applied.")
