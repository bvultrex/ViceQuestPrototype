from pathlib import Path
import json
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
builder = root / "tools" / "rebuild_gta2_runtime_assets.py"
source = builder.read_text(encoding="utf-8")
map_path = root / "assets" / "gta2" / "downtown" / "downtown_exact_map.json"
map_data = json.loads(map_path.read_text(encoding="utf-8"))


def _block_at(columns, block_defs, x, y, z):
    column = columns.get((x, y))
    if column is None:
        return None
    offset = int(column["offset"])
    for local_z, block_id in enumerate(column["blocks"]):
        if block_id and offset + local_z == z:
            return block_defs[int(block_id)]
    return None


def _high_step(slope):
    if 1 <= slope <= 8:
        step = slope - 1
        count = 2
    elif 9 <= slope <= 40:
        step = slope - 9
        count = 8
    elif 41 <= slope <= 44:
        step = slope - 41
        count = 1
    else:
        return None
    if step % count != count - 1:
        return None
    return ((0, 1), (0, -1), (-1, 0), (1, 0))[step // count]


def _is_pop_stair(block):
    slope = int(block["slope_type"])
    lid_tile = int(block["lid"].get("tile", 0) or 0)
    ground_type = int(block["ground_type"])
    return 1 <= slope <= 44 and (ground_type == 3 or lid_tile == 65 or slope >= 41)


def _flat_pavement(block):
    if block is None or int(block["slope_type"]) != 0 or int(block["ground_type"]) != 2:
        return False
    lid_tile = int(block["lid"].get("tile", 0) or 0)
    return 0 < lid_tile < 992


def stair_landing_decks(data):
    """Elevated pavement a real stair steps onto, plus the deck it belongs to.

    Station platforms were the first case. The same gap exists wherever a
    stair arrives on ordinary pavement: the slope is stereo and the floor
    stays a flat texture, so the landing has no floor. Roads are not included.
    """
    block_defs = data["block_defs"]
    columns = {(int(column["x"]), int(column["y"])): column for column in data["columns"]}
    deck = set()
    for (x, y), column in columns.items():
        offset = int(column["offset"])
        for local_z, block_id in enumerate(column["blocks"]):
            if not block_id:
                continue
            block = block_defs[int(block_id)]
            z_level = offset + local_z
            if z_level < 2 or not _is_pop_stair(block):
                continue
            step = _high_step(int(block["slope_type"]))
            if step is None:
                continue
            start = (x + step[0], y + step[1], z_level)
            if start in deck or not _flat_pavement(_block_at(columns, block_defs, *start)):
                continue
            pending = [start]
            deck.add(start)
            while pending:
                cx, cy, cz = pending.pop()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nxt = (cx + dx, cy + dy, cz)
                    if nxt in deck or not _flat_pavement(_block_at(columns, block_defs, *nxt)):
                        continue
                    deck.add(nxt)
                    pending.append(nxt)
    return deck


stair_deck = stair_landing_decks(map_data)
if (114, 118, 2) not in stair_deck or (115, 119, 2) not in stair_deck:
    raise SystemExit("Spawn landing deck was not found")
if len(stair_deck) < 200:
    raise SystemExit(f"Stair landing deck is unexpectedly small: {len(stair_deck)}")
deck_literal = "_STAIR_DECK = {\n" + ",\n".join(
    f"    ({x}, {y}, {z})" for x, y, z in sorted(stair_deck)
) + ",\n}\n\n"

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
source = source.replace(helper_anchor, deck_literal + helper, 1)

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

        # A stair's landing deck joins the station platforms on the stereo
        # layer. Gentle road ramps and ordinary streets stay on the flat board.
        out.append(indent + f"_pop_lid = (name == 'lid' and exposed_roof)")
        out.append(indent + f"_pop_stair = (1 <= slope <= 44) and (int(bd['ground_type']) == 3 or lid_tile == 65 or slope >= 41)")
        out.append(indent + f"_pop_platform = ((gx, gy, z) in _STAIR_DECK) or (int(bd['ground_type']) == 2 and z >= 2 and lid_tile in (346, 350))")
        out.append(indent + f"_pop_road = int(bd['ground_type']) in (1, 2) and (not _pop_stair) and (not _pop_platform)")
        out.append(indent + f"_pop_ramp = False")
        out.append(
            indent
            + f"_pop_hidden_lid = (name == 'lid' and int(bd['ground_type']) == 3 and not exposed_roof and z >= 2 and not _pop_stair)"
        )
        out.append(
            indent
            + f"_pop_interior = (name in ('left', 'right', 'top', 'bottom') and int(bd['ground_type']) == 3 and _popout_field_neighbor(gx, gy, z, name) and not _pop_stair)"
        )
        out.append(
            indent
            + f"if (not _pop_road) and (not _pop_ramp) and (not _pop_hidden_lid) and (not _pop_interior): pop_vis.append({expression})"
        )
        out.append(
            indent
            + f"if ((int(bd['ground_type']) in (1, 2)) or ((1 <= slope <= 44) and not (name == 'lid' and exposed_roof)) or (name == 'lid' and (z <= 1 or int(bd['ground_type']) in (0,1,2)))) and (not _pop_stair) and (not _pop_platform): flat_vis.append({expression})"
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
if "_STAIR_DECK" not in text:
    raise SystemExit("Stair landing deck missing after patch")

builder.write_text(text, encoding="utf-8")
subprocess.run([sys.executable, str(builder)], cwd=root, check=True)

popout = sorted((root / "assets" / "gta2" / "downtown").glob("downtown_popout_*.meshbin"))
flat = sorted((root / "assets" / "gta2" / "downtown").glob("downtown_flat_*.meshbin"))
if len(popout) != 16:
    raise SystemExit(f"Expected 16 popout meshes, found {len(popout)}")
if len(flat) != 16:
    raise SystemExit(f"Expected 16 flat meshes, found {len(flat)}")

map_path = root / "assets" / "gta2" / "downtown" / "downtown_exact_map.json"
station_floor = bytearray(256 * 256 * 8)
block_defs = map_data["block_defs"]
marked = 0
for column in map_data["columns"]:
    cell = (int(column["y"]) * 256 + int(column["x"])) * 8
    offset = int(column["offset"])
    for local_z, block_id in enumerate(column["blocks"]):
        if not block_id:
            continue
        z_level = offset + local_z
        if not 0 <= z_level < 8:
            continue
        block = block_defs[int(block_id)]
        slope = int(block["slope_type"])
        lid_tile = int(block["lid"].get("tile", 0) or 0)
        ground_type = int(block["ground_type"])
        is_stair = 1 <= slope <= 44 and lid_tile == 65 and ground_type != 3
        is_platform = (int(column["x"]), int(column["y"]), z_level) in stair_deck or (
            ground_type == 2 and z_level >= 2 and lid_tile in (346, 350)
        )
        if is_stair or is_platform:
            station_floor[cell + z_level] = 1
            marked += 1
mask_path = map_path.with_name("downtown_station_floor.bin")
mask_path.write_bytes(station_floor)
if marked < 100:
    raise SystemExit(f"Station floor mask marked only {marked} layers")

print("Built 16 Quest roof-shell pop-out meshes and 16 flat ground meshes.")
