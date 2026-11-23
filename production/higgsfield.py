#!/usr/bin/env python3
"""Higgsfield API client (pay-as-you-go): text-to-video clips.

Secrets: HF_API_KEY_ID holds "id:secret" (or HF_API_KEY_ID + HF_API_KEY_SECRET separately).
Failed generations are not billed by Higgsfield. MAX_CLIPS caps how many clips one run may order.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://platform.higgsfield.ai"
MAX_CLIPS = int(os.environ.get("HF_MAX_CLIPS", "12"))
MAX_USD = float(os.environ.get("HF_MAX_USD", "5"))   # spending cap per run (list price estimate)
_ordered = 0
_spent = 0.0


def _auth() -> dict:
    kid = os.environ.get("HF_API_KEY_ID", "").strip()
    sec = os.environ.get("HF_API_KEY_SECRET", "").strip()
    cred = kid if ":" in kid else f"{kid}:{sec}"
    return {"Authorization": f"Key {cred}", "Content-Type": "application/json"}


def submit(model: str, body: dict, usd_per_sec: float = 0.0) -> dict:
    """POST a generation; on a 422 drop the optional fields the API names and retry once."""
    global _ordered, _spent
    cost = usd_per_sec * float(body.get("duration", 5))
    if _ordered >= MAX_CLIPS:
        raise RuntimeError(f"Safety cap reached ({MAX_CLIPS} clips in one run).")
    if _spent + cost > MAX_USD:
        raise RuntimeError(f"Spending cap reached: ${_spent:.2f} used, next clip ~${cost:.2f}, cap ${MAX_USD:.2f}.")
    url = f"{BASE}/{model}"
    r = requests.post(url, headers=_auth(), json=body, timeout=60)
    if r.status_code == 422:
        print(f"  422 from {model}: {r.text[:400]}")
        bad = {str(e.get("loc", [None])[-1]) for e in r.json().get("detail", []) if isinstance(e, dict)}
        body = {k: v for k, v in body.items() if k not in bad or k == "prompt"}
        print(f"  retrying without {sorted(bad)}")
        r = requests.post(url, headers=_auth(), json=body, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{model} error {r.status_code}: {r.text[:400]}")
    _ordered += 1
    _spent += cost
    print(f"  estimated spend so far: ${_spent:.2f} (cap ${MAX_USD:.2f})")
    return r.json()


def wait(job: dict, timeout: int = 900) -> dict:
    url = job.get("status_url") or f"{BASE}/requests/{job['request_id']}/status"
    start = time.time()
    while time.time() - start < timeout:
        s = requests.get(url, headers=_auth(), timeout=60).json()
        if s.get("status") in ("completed", "failed", "nsfw", "canceled"):
            return s
        time.sleep(10)
    raise TimeoutError(f"Timed out waiting for {job.get('request_id')}")


def text_to_video(model: str, prompt: str, out: Path, extra: dict, usd_per_sec: float = 0.0,
                  image_url: str = None) -> Path:
    body = {"prompt": prompt, **extra}
    if image_url:
        body["image_url"] = image_url
    job = submit(model, body, usd_per_sec)
    print(f"  {model}: queued {job.get('request_id')}")
    res = wait(job)
    if res.get("status") != "completed":
        raise RuntimeError(f"{model}: {res.get('status')} {res.get('error')}")
    data = requests.get(res["video"]["url"], timeout=300).content
    out.write_bytes(data)
    print(f"  saved {out} ({len(data) // 1024} KB)")
    return out


# model key: (endpoint, request fields, list price USD per second for those settings)
MODELS = {
    "seedance": ("bytedance/seedance-2.5/text-to-video",
                 {"duration": 5, "aspect_ratio": "9:16", "resolution": "1080p", "generate_audio": False}, 0.6518),
    "kling": ("kling-video/v3.0/std/text-to-video",
              {"duration": 5, "aspect_ratio": "9:16", "sound": "off"}, 0.0714),
    "kling-pro": ("kling-video/v3.0/pro/text-to-video",
                  {"duration": 5, "aspect_ratio": "9:16", "sound": "off"}, 0.0962),
    "kling-pro-i2v": ("kling-video/v3.0/pro/image-to-video",
                      {"duration": 5, "sound": "off"}, 0.0962),
}

if __name__ == "__main__":
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    errors = 0
    for clip in spec["clips"]:
        model, extra, price = MODELS[clip["model"]]
        try:
            text_to_video(model, clip["prompt"] + " " + spec.get("style", ""), out_dir / f"{clip['name']}.mp4", extra, price,
                          clip.get("image_url"))
        except Exception as e:  # noqa: BLE001
            errors += 1
            print(f"  FAILED {clip['name']}: {e}")
    sys.exit(1 if errors == len(spec["clips"]) else 0)
