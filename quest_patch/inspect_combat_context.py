from pathlib import Path
import re, sys

root = Path(sys.argv[1]).resolve()
paths = [
    root / "scripts" / "main.gd",
    root / "scripts" / "player.gd",
    root / "scripts" / "input_bridge.gd",
    root / "scripts" / "weapon_data.gd",
]

needles = [
    "stun_hitscan", "shock_arc", "_weapon_stun_hit", "player_current_weapon",
    "attack", "fire", "shoot", "Input.is_action_pressed", "Input.is_action_just_pressed",
    "_server", "_rpc", "weapon_def", "delivery",
]

def functions(text: str):
    starts = list(re.finditer(r"(?m)^func\s+([A-Za-z0-9_]+)\s*\(", text))
    for i, m in enumerate(starts):
        a = m.start()
        b = starts[i+1].start() if i+1 < len(starts) else len(text)
        yield m.group(1), text[a:b]

for path in paths:
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    print(f"\n===== {path.name} =====")
    for name, body in functions(text):
        low = body.lower()
        if any(n.lower() in low for n in needles):
            print(f"\n--- FUNC {name} ---")
            print(body[:12000])
