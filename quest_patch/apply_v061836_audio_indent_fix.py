#!/usr/bin/env python3
"""Normalize generated audio_manager.gd indentation for Godot 4.5.

The historical patch chain replaces several functions with 4-space-indented
blocks inside a file that otherwise uses tabs. Godot 4.5 treats mixed block
indentation as a parse error. Older Quest artifacts could still appear to work
when an imported script cache survived, but a clean rebuild exposes it.
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
path = root / "scripts" / "audio_manager.gd"
text = path.read_text(encoding="utf-8")

out = []
changed = 0
for line in text.splitlines(keepends=True):
    m = re.match(r"^[ \t]+", line)
    if not m:
        out.append(line)
        continue
    indent = m.group(0)
    if " " not in indent:
        out.append(line)
        continue
    # Godot's project convention is tabs. Interpret an existing tab as a
    # 4-column indentation unit and convert leading space columns to tabs.
    columns = 0
    for ch in indent:
        columns += 4 if ch == "\t" else 1
    tabs, remainder = divmod(columns, 4)
    # Patch-generated block indentation is always a multiple of four. Keep a
    # tiny remainder only for expression alignment, which is not block indent.
    normalized = "\t" * tabs + (" " * remainder)
    if normalized != indent:
        changed += 1
    out.append(normalized + line[len(indent):])

new_text = "".join(out)
path.write_text(new_text, encoding="utf-8")
print(f"Normalized audio_manager.gd indentation on {changed} lines.")
