#!/usr/bin/env python3
"""Generate a set of style keyframes (still images) with OpenAI, from a JSON spec.

Spec: {"style": "...", "character": "...", "frames": [{"name": "...", "prompt": "..."}]}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import services  # noqa: E402

services.load_keys()
spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
style = f"{spec.get('character', '')} {spec['style']}"
for f in spec["frames"]:
    target = out / f"{f['name']}.jpg"
    if target.exists():
        continue
    print(f"  {f['name']}: generating")
    services.generate_image(f["prompt"], target, style=style)
