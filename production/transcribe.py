#!/usr/bin/env python3
"""Print what is said in recorded voice files (to match a recording to its script)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import services  # noqa: E402

services.load_keys()
for name in sys.argv[1:]:
    for path in sorted(Path().glob(name)):
        print(f"== {path}\n{services.transcribe(path)}\n")
