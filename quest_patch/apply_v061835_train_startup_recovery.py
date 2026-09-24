#!/usr/bin/env python3
"""ViceQuest v0.6.18.35 train startup recovery.

18.34 exported successfully but hardware boot stayed black with no sound.
The train core was initialized synchronously from the main startup path and
referenced DOWNTOWN_DATA.HEIGHT_UNIT, a property not established by the
existing Downtown runtime contract.

Recovery:
- use the proven 0.60 vertical block scale explicitly
- do not construct trains synchronously during main _ready
- defer train startup for several process frames so XR board/audio can boot
- add a one-shot startup guard and readiness flag
- reduce first-pass train work until startup validation succeeds
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
main_path = root / "scripts" / "main.gd"
train_path = root / "scripts" / "train_system.gd"

main = main_path.read_text(encoding="utf-8")
train = train_path.read_text(encoding="utf-8")

def must_replace(text: str, old: str, new: str, label: str, count: int = 1) -> str:
    hits = text.count(old)
    if hits < count:
        raise SystemExit(f"Missing v0.6.18.35 anchor {label}: found {hits}, need {count}")
    return text.replace(old, new, count)

def func_span(text: str, name: str):
    m = re.search(rf"(?m)^func {re.escape(name)}\s*\(", text)
    if m is None:
        raise SystemExit(f"Missing function {name}")
    start = m.start()
    nxt = re.search(r"(?m)^func [A-Za-z0-9_]+\s*\(", text[m.end():])
    end = len(text) if nxt is None else m.end() + nxt.start()
    return start, end

def replace_func(text: str, name: str, replacement: str):
    start, end = func_span(text, name)
    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]

def insert_before_func(text: str, name: str, addition: str):
    start, _ = func_span(text, name)
    return text[:start] + addition.rstrip() + "\n\n" + text[start:]

# Never ask the runtime data script for a HEIGHT_UNIT that may not exist.
main = must_replace(
    main,
    'train_system.call("configure", self, DOWNTOWN_DATA.TILE_SIZE, DOWNTOWN_DATA.HEIGHT_UNIT, presentation_rig)',
    'train_system.call("configure", self, DOWNTOWN_DATA.TILE_SIZE, 0.60, presentation_rig)',
    "safe height scale",
)
# The generated base can contain additional Downtown height lookups after the
# complete patch chain. HEIGHT_UNIT is not part of the proven runtime contract,
# so normalize every remaining occurrence before startup.
main = main.replace("DOWNTOWN_DATA.HEIGHT_UNIT", "0.60")

# Replace synchronous startup with a deferred boot sequence. The base game,
# Quest presentation rig and audio manager get several frames to initialize.
main = must_replace(
    main,
    "    _build_gta2_lighting_system()\n    _build_train_system()\n",
    "    _build_gta2_lighting_system()\n    call_deferred(\"_start_train_system_after_boot\")\n",
    "deferred train startup",
)

startup = r'''func _start_train_system_after_boot() -> void:
    # Do not let optional public transport block the critical XR startup path.
    await get_tree().process_frame
    await get_tree().process_frame
    await get_tree().process_frame
    _build_train_system()
'''
main = insert_before_func(main, "_build_train_system", startup)

# Add explicit setup state. Train _physics_process stays inert until configure
# reaches the end successfully.
if "var _configured: bool" not in train:
    train = train.replace(
        "var _impact_until: Dictionary = {}\n",
        "var _impact_until: Dictionary = {}\nvar _configured: bool = false\n",
        1,
    )

configure = r'''func configure(host_node: Node, tile_size_value: float, height_unit_value: float, rig_node: Node) -> void:
    if _configured:
        return
    host = host_node
    tile_size = maxf(0.1, tile_size_value)
    height_unit = 0.60 if height_unit_value <= 0.0 else height_unit_value
    presentation_rig = rig_node
    _load_routes()
    if lines.is_empty():
        push_warning("ViceQuest train core: no valid Downtown rail lines; train system disabled")
        return
    _build_trains()
    if trains.is_empty():
        push_warning("ViceQuest train core: no trains constructed; train system disabled")
        return
    _configured = true
    print("ViceQuest train core ready: ", trains.size(), " trains / ", lines.size(), " lines")
'''
train = replace_func(train, "configure", configure)

physics_start, physics_end = func_span(train, "_physics_process")
physics = train[physics_start:physics_end]
physics = must_replace(
    physics,
    "func _physics_process(delta: float) -> void:\n    if trains.is_empty():\n",
    "func _physics_process(delta: float) -> void:\n    if not _configured or trains.is_empty():\n",
    "configured physics guard",
)
train = train[:physics_start] + physics.rstrip() + "\n\n" + train[physics_end:]

# Reduce impact work for the startup-validation build. This still tests train
# vs vehicles, but only every few physics ticks instead of every frame.
if "var _impact_accum:" not in train:
    train = train.replace(
        "var _configured: bool = false\n",
        "var _configured: bool = false\nvar _impact_accum: float = 0.0\n",
        1,
    )

physics_start, physics_end = func_span(train, "_physics_process")
physics = train[physics_start:physics_end]
physics = must_replace(
    physics,
    "        _server_train_impacts()\n",
    """        _impact_accum += delta
        if _impact_accum >= 0.10:
            _impact_accum = 0.0
            _server_train_impacts()
""",
    "impact throttle",
)
train = train[:physics_start] + physics.rstrip() + "\n\n" + train[physics_end:]

checks = [
    ("call_deferred(\"_start_train_system_after_boot\")", main),
    ("func _start_train_system_after_boot", main),
    ('DOWNTOWN_DATA.TILE_SIZE, 0.60, presentation_rig', main),
    ("var _configured: bool = false", train),
    ("if not _configured or trains.is_empty()", train),
    ("ViceQuest train core ready:", train),
    ("_impact_accum >= 0.10", train),
]
for needle, text in checks:
    if needle not in text:
        raise SystemExit(f"v0.6.18.35 verification failed: {needle}")

if "DOWNTOWN_DATA.HEIGHT_UNIT" in main:
    raise SystemExit("Unsafe DOWNTOWN_DATA.HEIGHT_UNIT reference remains")

main_path.write_text(main, encoding="utf-8")
train_path.write_text(train, encoding="utf-8")
print("Applied v0.6.18.35: deferred safe train startup with explicit Downtown height scale.")
