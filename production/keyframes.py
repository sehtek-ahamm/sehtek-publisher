#!/usr/bin/env python3
"""Generate a set of style keyframes (still images) with OpenAI, from a JSON spec.

Spec: {"style": "...", "character": "...", "frames": [{"name": "...", "prompt": "..."}]}
Each image is saved (and committed by the workflow) even if a later one fails;
if OpenAI reports no credits, the run stops at once.
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
failed = 0
for f in spec["frames"]:
    target = out / f"{f['name']}.jpg"
    if target.exists():
        continue
    print(f"  {f['name']}: generating")
    try:
        refs = [Path(__file__).resolve().parent / "brand-kit" / f"{r}.jpg" for r in f.get("refs", [])]
        if refs:
            services.generate_image_with_refs(f["prompt"], target, refs, style=style)
        else:
            services.generate_image(f["prompt"], target, style=style)
        print(f"  {f['name']}: saved")
    except services.ServiceError as e:
        failed += 1
        print(f"  {f['name']}: FAILED {str(e)[:200]}")
        if "credits" in str(e) or "quota" in str(e) or " 429" in str(e):
            print("  Stopping: OpenAI has no credits left.")
            break
sys.exit(1 if failed else 0)
