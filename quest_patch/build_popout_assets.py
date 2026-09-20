from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
builder = root / "tools" / "rebuild_gta2_runtime_assets.py"
text = builder.read_text(encoding="utf-8")

text = text.replace(
    "    vis=[]; col=[]",
    "    vis=[]; pop_vis=[]; col=[]",
)

replacements = [
    (
        "                  vis.append((*vv[ti],*uu[ti]))",
        "                  vis.append((*vv[ti],*uu[ti]))\n"
        "                  if not (1 <= slope <= 44): pop_vis.append((*vv[ti],*uu[ti]))",
    ),
    (
        "                    vis.append((*vv[ti],*uu[ti]))",
        "                    vis.append((*vv[ti],*uu[ti]))\n"
        "                    if not (1 <= slope <= 44): pop_vis.append((*vv[ti],*uu[ti]))",
    ),
    (
        "                vis.append((*vv[ti],*uu[ti]))",
        "                vis.append((*vv[ti],*uu[ti]))\n"
        "                if not (1 <= slope <= 44): pop_vis.append((*vv[ti],*uu[ti]))",
    ),
]
for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Expected builder line missing: {old}")
    text = text.replace(old, new, 1)

needle = """    with open(OUT/f'downtown_collision_{cx}_{cy}.colbin','wb') as f:
        f.write(struct.pack('<I',len(col)))
        for row in col:f.write(struct.pack('<3f',*row))
"""
insert = """    with open(OUT/f'downtown_popout_{cx}_{cy}.meshbin','wb') as f:
        f.write(struct.pack('<I',len(pop_vis)))
        for row in pop_vis:f.write(struct.pack('<5f',*row))
    with open(OUT/f'downtown_collision_{cx}_{cy}.colbin','wb') as f:
        f.write(struct.pack('<I',len(col)))
        for row in col:f.write(struct.pack('<3f',*row))
"""
if needle not in text:
    raise SystemExit("Could not find mesh output block")
text = text.replace(needle, insert, 1)

builder.write_text(text, encoding="utf-8")
subprocess.run([sys.executable, str(builder)], cwd=root, check=True)

outputs = sorted((root / "assets" / "gta2" / "downtown").glob("downtown_popout_*.meshbin"))
if len(outputs) != 16:
    raise SystemExit(f"Expected 16 popout meshes, found {len(outputs)}")

print("Built 16 Quest pop-out meshes with GTA2 slope families 1..44 removed.")
