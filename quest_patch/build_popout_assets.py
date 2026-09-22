from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
builder = root / "tools" / "rebuild_gta2_runtime_assets.py"
source = builder.read_text(encoding="utf-8")

helper_anchor = "for cy in range(4):"
helper = '''_POPOUT_NEIGHBOR = {"left": (-1, 0), "right": (1, 0), "bottom": (0, 1), "top": (0, -1)}

def _popout_field_neighbor(gx, gy, z, name):
    step = _POPOUT_NEIGHBOR.get(name)
    if step is None:
        return False
    ngx, ngy = gx + step[0], gy + step[1]
    if ngx < 0 or ngx > 255 or ngy < 0 or ngy > 255:
        return False
    nc = C[ngy * 256 + ngx]
    for nj, nbid in enumerate(nc["blocks"]):
        if not nbid:
            continue
        if nc["offset"] + nj == z and int(B[nbid]["ground_type"]) == 3:
            return True
    return False

for cy in range(4):
'''
if helper_anchor not in source:
    raise SystemExit("Could not find chunk loop to insert popout neighbor helper")
if source.count(helper_anchor) != 1:
    raise SystemExit("Chunk loop anchor is not unique")
source = source.replace(helper_anchor, helper, 1)

roof_old = "          exposed_roof=(j==top_j and z>=2 and int(bd['ground_type'])==3 and 0<lid_tile<992)"
roof_new = """          roof_j=next((rj for rj in range(len(c['blocks'])-1,-1,-1) if c['blocks'][rj] and int(B[c['blocks'][rj]]['ground_type'])==3 and 0<int(B[c['blocks'][rj]]['lid'].get('tile',0) or 0)<992), None)
          exposed_roof=(j==roof_j and z>=2 and int(bd['ground_type'])==3 and 0<lid_tile<992)"""
if roof_old not in source:
    raise SystemExit("Could not find exposed_roof assignment")
if source.count(roof_old) != 1:
    raise SystemExit("exposed_roof assignment is not unique")
source = source.replace(roof_old, roof_new, 1)

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
        expression = stripped[len("vis.append(") : -1]

        # v0.6.18.12 roof shell:
        # - ramps/stairs (slope 1..44) stay on the flat board except the actual
        #   exposed building-roof lid, which must pop out;
        # - the roof lid is the highest field (gt3) lid in the column, even if
        #   air blocks sit above it;
        # - intermediate field lids stay out of popout (those are interior floors);
        # - field walls that face another field block at the same Z are interior
        #   and must not stick through the roof.
        out.append(indent + f"_pop_lid = (name == 'lid' and exposed_roof)")
        out.append(indent + f"_pop_ramp = (1 <= slope <= 44) and not _pop_lid")
        out.append(
            indent
            + f"_pop_hidden_lid = (name == 'lid' and int(bd['ground_type']) == 3 and not exposed_roof and z >= 2)"
        )
        out.append(
            indent
            + f"_pop_interior = (name in ('left', 'right', 'top', 'bottom') and int(bd['ground_type']) == 3 and _popout_field_neighbor(gx, gy, z, name))"
        )
        out.append(
            indent
            + f"if (not _pop_ramp) and (not _pop_hidden_lid) and (not _pop_interior): pop_vis.append({expression})"
        )

        # Flat viewport keeps traversable GTA2 slopes plus ordinary
        # ground/road/pavement lids. Elevated GroundType-0 lids stay: Downtown
        # uses them for bridges/platforms. Building roofs remain stereo-only.
        out.append(
            indent
            + f"if ((1 <= slope <= 44) and not (name == 'lid' and exposed_roof)) or (name == 'lid' and (z <= 1 or int(bd['ground_type']) in (0,1,2))): flat_vis.append({expression})"
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

if "_popout_field_neighbor" not in text:
    raise SystemExit("Roof-shell neighbor helper missing after patch")
if "roof_j=next(" not in text:
    raise SystemExit("Highest-field roof lid selection missing after patch")
if "_pop_hidden_lid" not in text:
    raise SystemExit("Interior-floor lid filter missing after patch")

builder.write_text(text, encoding="utf-8")
subprocess.run([sys.executable, str(builder)], cwd=root, check=True)

popout = sorted((root / "assets" / "gta2" / "downtown").glob("downtown_popout_*.meshbin"))
flat = sorted((root / "assets" / "gta2" / "downtown").glob("downtown_flat_*.meshbin"))
if len(popout) != 16:
    raise SystemExit(f"Expected 16 popout meshes, found {len(popout)}")
if len(flat) != 16:
    raise SystemExit(f"Expected 16 flat meshes, found {len(flat)}")

print("Built 16 Quest roof-shell pop-out meshes and 16 flat ground meshes.")
