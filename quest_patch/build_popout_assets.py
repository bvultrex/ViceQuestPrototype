from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
builder = root / "tools" / "rebuild_gta2_runtime_assets.py"
source = builder.read_text(encoding="utf-8")

out = []
saw_chunk_init = False
vis_append_count = 0

for line in source.splitlines():
    stripped = line.strip()

    if stripped == "vis=[]; col=[]":
        indent = line[: len(line) - len(line.lstrip())]
        out.append(indent + "vis=[]; pop_vis=[]; flat_vis=[]; col=[]")
        saw_chunk_init = True
        continue

    if stripped.startswith("vis.append("):
        indent = line[: len(line) - len(line.lstrip())]
        out.append(line)
        expression = stripped[len("vis.append("):-1]

        # Pop-out: everything elevated except GTA2 slope families 1..44.
        out.append(indent + f"if not (1 <= slope <= 44): pop_vis.append({expression})")

        # Flat Quest viewport: roads/pavement, ground-level field lids, and all
        # slope/ramp/stair geometry. Elevated field/building geometry is omitted.
        out.append(
            indent
            + f"if (1 <= slope <= 44) or (name == 'lid' and (z <= 1 or int(bd['ground_type']) in (1,2))): flat_vis.append({expression})"
        )
        vis_append_count += 1
        continue

    out.append(line)

if not saw_chunk_init:
    raise SystemExit("Could not find visual chunk initialization")
if vis_append_count != 3:
    raise SystemExit(f"Expected 3 vis.append sites, found {vis_append_count}")

text = "\n".join(out) + "\n"

needle = """    with open(OUT/f'downtown_collision_{cx}_{cy}.colbin','wb') as f:
        f.write(struct.pack('<I',len(col)))
        for row in col:f.write(struct.pack('<3f',*row))
"""
insert = """    with open(OUT/f'downtown_popout_{cx}_{cy}.meshbin','wb') as f:
        f.write(struct.pack('<I',len(pop_vis)))
        for row in pop_vis:f.write(struct.pack('<5f',*row))
    with open(OUT/f'downtown_flat_{cx}_{cy}.meshbin','wb') as f:
        f.write(struct.pack('<I',len(flat_vis)))
        for row in flat_vis:f.write(struct.pack('<5f',*row))
    with open(OUT/f'downtown_collision_{cx}_{cy}.colbin','wb') as f:
        f.write(struct.pack('<I',len(col)))
        for row in col:f.write(struct.pack('<3f',*row))
"""
if needle not in text:
    raise SystemExit("Could not find mesh output block")
text = text.replace(needle, insert, 1)

builder.write_text(text, encoding="utf-8")
subprocess.run([sys.executable, str(builder)], cwd=root, check=True)

popout = sorted((root / "assets" / "gta2" / "downtown").glob("downtown_popout_*.meshbin"))
flat = sorted((root / "assets" / "gta2" / "downtown").glob("downtown_flat_*.meshbin"))
if len(popout) != 16:
    raise SystemExit(f"Expected 16 popout meshes, found {len(popout)}")
if len(flat) != 16:
    raise SystemExit(f"Expected 16 flat meshes, found {len(flat)}")

print("Built 16 filtered Quest pop-out meshes and 16 flat ground meshes.")
