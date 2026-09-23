#!/usr/bin/env python3
"""v0.6.18.19 — keep thrown weapons, shots and fire on the elevated deck.

Fruitbat's raised street is a stereo lid. Pawns and cars are already copied
onto that lid. Grenades, molotovs, bullet streaks, blasts and burn sprites
were still drawn only on the flat board, so the lid covered them.
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
        raise SystemExit(f"Missing elevated-throw patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"Elevated-throw patch anchor is not unique: {label}")
    return text.replace(old, new, 1)


main = read("scripts/main.gd")
main = replace(
    main,
    "                presentation_rig.sync_elevated_vehicles(vehicles)\n",
    "                presentation_rig.sync_elevated_vehicles(vehicles)\n"
    "                var burn_anchors: Dictionary = {}\n"
    "                if combat_fx != null:\n"
    "                    burn_anchors = combat_fx.burn_anchors()\n"
    "                presentation_rig.sync_elevated_throws(projectile_visuals, fire_zone_visuals, burn_anchors)\n",
    "throw popout sync",
)
main = replace(
    main,
    "    add_child(explosion)\n"
    "    explosion.animation_finished.connect(explosion.queue_free)\n",
    "    add_child(explosion)\n"
    "    if presentation_rig != null:\n"
    "        presentation_rig.track_elevated_fx(explosion)\n"
    "    explosion.animation_finished.connect(explosion.queue_free)\n",
    "explosion popout",
)
main = replace(
    main,
    "    add_child(burst)\n"
    "    burst.play()\n",
    "    add_child(burst)\n"
    "    if presentation_rig != null:\n"
    "        presentation_rig.track_elevated_fx(burst)\n"
    "    burst.play()\n",
    "molotov popout",
)
main = replace(
    main,
    "    add_child(projectile)\n"
    "\n"
    "    var projectile_end: Vector3 = end + Vector3(0.0, 0.04, 0.0)\n",
    "    add_child(projectile)\n"
    "    if presentation_rig != null:\n"
    "        presentation_rig.track_elevated_fx(projectile, end.y)\n"
    "\n"
    "    var projectile_end: Vector3 = end + Vector3(0.0, 0.04, 0.0)\n",
    "shot popout",
)
write("scripts/main.gd", main)

combat = read("scripts/combat_fx.gd")
if "func burn_anchors()" not in combat:
    if not combat.endswith("\n"):
        combat += "\n"
    combat += "\nfunc burn_anchors() -> Dictionary:\n    return _burn_effects\n"
    write("scripts/combat_fx.gd", combat)

for rel, needle in (
    ("scripts/main.gd", "presentation_rig.sync_elevated_throws(projectile_visuals, fire_zone_visuals, burn_anchors)"),
    ("scripts/main.gd", "presentation_rig.track_elevated_fx(explosion)"),
    ("scripts/main.gd", "presentation_rig.track_elevated_fx(burst)"),
    ("scripts/main.gd", "presentation_rig.track_elevated_fx(projectile, end.y)"),
    ("scripts/combat_fx.gd", "func burn_anchors() -> Dictionary:"),
):
    if needle not in read(rel):
        raise SystemExit(f"Elevated-throw patch did not land: {rel} / {needle}")

print("Elevated throw Quest overlay patch applied.")
