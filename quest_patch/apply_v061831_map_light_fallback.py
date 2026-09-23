#!/usr/bin/env python3
"""ViceQuest v0.6.18.31 fallback map lights.

18.30 can consume original GTA2 GMP LGHT data, but the current reconstructed
source pack does not preserve that chunk. Generate a conservative street-light
layout from the exact Downtown road/pavement topology instead.

If original LGHT data is ever present, this patch leaves it untouched.
"""
from pathlib import Path
import json
import sys

root = Path(sys.argv[1]).resolve()
downtown = root / "assets" / "gta2" / "downtown"
lights_path = downtown / "downtown_lights.json"
map_path = downtown / "downtown_exact_map.json"

payload = {"source": "", "lights": []}
if lights_path.is_file():
    try:
        payload = json.loads(lights_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {"source": "", "lights": []}

existing = payload.get("lights", []) if isinstance(payload, dict) else []
if isinstance(existing, list) and existing:
    print(f"v0.6.18.31: keeping {len(existing)} original/preserved map lights from {payload.get('source','')}")
    raise SystemExit(0)

if not map_path.is_file():
    raise SystemExit(f"Missing exact Downtown map: {map_path}")
data = json.loads(map_path.read_text(encoding="utf-8"))
block_defs = data["block_defs"]

# Top walkable surface classification by 256x256 map cell.
surface = {}
for column in data["columns"]:
    x = int(column["x"])
    y = int(column["y"])
    offset = int(column["offset"])
    best = None
    for local_z, raw_block in enumerate(column["blocks"]):
        block_id = int(raw_block)
        if block_id == 0:
            continue
        block = block_defs[block_id]
        z = offset + local_z
        ground = int(block.get("ground_type", 0))
        lid_tile = int(block.get("lid", {}).get("tile", 0) or 0)
        if lid_tile <= 0:
            continue
        best = (ground, z)
    if best is not None:
        surface[(x, y)] = best

# GTA2 ground types in this runtime: 1 road, 2 pavement. Put lamps on pavement
# cells bordering roads. A deterministic spacing hash avoids a lamp every block
# while retaining both sides of long streets and intersections.
candidates = []
directions = ((1,0),(-1,0),(0,1),(0,-1))
for (x, y), (ground, z) in surface.items():
    if ground != 2:
        continue
    road_steps = []
    for dx, dy in directions:
        neighbor = surface.get((x + dx, y + dy))
        if neighbor is not None and int(neighbor[0]) == 1 and abs(int(neighbor[1]) - z) <= 1:
            road_steps.append((dx, dy))
    if not road_steps:
        continue
    # ~1 lamp every 5 curb cells, with intersection bonus.
    spacing = (x * 11 + y * 7) % 5
    if spacing != 0 and len(road_steps) < 2:
        continue

    # Shift slightly toward the road edge while staying on the pavement cell.
    dx = sum(step[0] for step in road_steps)
    dy = sum(step[1] for step in road_steps)
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    edge_x = x + 0.5 + (dx / length) * 0.28
    edge_y = y + 0.5 + (dy / length) * 0.28
    candidates.append({
        "x": edge_x,
        "y": edge_y,
        "z": float(z) + 0.18,
        "radius": 2.15 if len(road_steps) == 1 else 2.55,
        "intensity": 168 if len(road_steps) == 1 else 188,
        "shape": 0,
        "on_time": 0,
        "off_time": 0,
        "r": 255,
        "g": 214,
        "b": 145,
        "a": 0,
    })

# Keep the authored city broad, but avoid pathological density at plazas.
# The runtime still displays only the 36 nearest lights inside 44 world units.
lights = candidates[:420]
if len(lights) < 40:
    raise SystemExit(f"Generated suspiciously few Downtown curb lights: {len(lights)}")

lights_path.write_text(
    json.dumps({"source": "generated:exact_downtown_road_edges", "lights": lights}, separators=(",", ":")),
    encoding="utf-8",
)
print(f"v0.6.18.31: generated {len(lights)} Downtown curb lights from exact road/pavement topology")
