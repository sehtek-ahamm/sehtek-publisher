#!/usr/bin/env python3
"""Word timings for a recorded voice-over (ElevenLabs forced alignment) -> JSON file."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import services  # noqa: E402

services.load_keys()
audio, text_file, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
words = services.align_words(audio, text_file.read_text(encoding="utf-8"))
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
print(f"{len(words)} words aligned")
