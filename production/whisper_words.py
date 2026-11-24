#!/usr/bin/env python3
"""Word timings via OpenAI whisper-1 (fallback when ElevenLabs has no credits) -> JSON [[word, start, end], ...]."""
import json, os, sys
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent))
import services  # noqa: E402

services.load_keys()
audio, out = Path(sys.argv[1]), Path(sys.argv[2])
with open(audio, "rb") as f:
    r = requests.post("https://api.openai.com/v1/audio/transcriptions",
                      headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                      data={"model": "whisper-1", "language": "ar", "response_format": "verbose_json",
                            "timestamp_granularities[]": "word"},
                      files={"file": (audio.name, f, "audio/mpeg")}, timeout=300)
r.raise_for_status()
d = r.json()
words = [[w["word"], w["start"], w["end"]] for w in d.get("words", [])]
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"text": d.get("text", ""), "words": words}, ensure_ascii=False), encoding="utf-8")
print(d.get("text", ""))
print(f"{len(words)} words")
