#!/usr/bin/env python3
"""ViceQuest v0.6.18.36 isolated skid-sprite fix.

Keep the confirmed flipping-skull/coin sprite out of brake marks while the
18.34/18.35 train runtime is completely excluded from the recovery build.
"""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
path = root / "scripts" / "combat_fx.gd"
text = path.read_text(encoding="utf-8")

old = '''    if braking and not sliding:
        var blob: Texture2D = _gta_tex("skid_blob")
        if blob != null:
            _spawn_gta_decal(blob, world_position, yaw + randf_range(-8.0, 8.0), 0.040, 4.2, 0.62, "skid")
        return

    var streak: Texture2D = _gta_tex("skid")
'''
new = '''    var streak: Texture2D = _gta_tex("skid")
    if braking and not sliding:
        if streak == null:
            return
        var brake_side: Vector3 = Vector3(-flat.z, 0.0, flat.x)
        for offset in [-0.34, 0.34]:
            _spawn_gta_decal(streak, world_position + brake_side * offset, yaw, 0.040, 5.0, 0.70, "skid")
        return

'''
if old not in text:
    raise SystemExit("v0.6.18.36 skid sprite anchor missing")
text = text.replace(old, new, 1)
# Ensure there is one normal declaration for the sliding path after the brake block.
needle = '''    if streak == null:
        return
    var side: Vector3 = Vector3(-flat.z, 0.0, flat.x)
'''
if needle not in text:
    raise SystemExit("v0.6.18.36 sliding skid path missing")
segment = text[text.find("func play_skid_mark"):text.find("func play_crash_sparks")]
if "skid_blob" in segment:
    raise SystemExit("skid_blob still present in play_skid_mark")
path.write_text(text, encoding="utf-8")
print("Applied v0.6.18.36 isolated real-skid texture fix.")
