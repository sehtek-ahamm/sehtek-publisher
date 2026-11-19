"""Paid services: ElevenLabs (voice) and OpenAI (images). Keys come from a .env file."""

import base64
import io
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

import brand

HERE = Path(__file__).resolve().parent

# The .env file can live in any of these places (first one found wins).
ENV_LOCATIONS = [
    Path.cwd() / ".env",
    HERE / ".env",
    HERE.parent / ".env",
    HERE.parent.parent / ".env",
    Path.home() / "Documents" / "sehtek-production" / ".env",
    Path.home() / "OneDrive" / "Documents" / "sehtek-production" / ".env",
]


def load_keys():
    for path in ENV_LOCATIONS:
        if path.exists():
            load_dotenv(path)
            return path
    return None


class ServiceError(Exception):
    pass


def _key(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ServiceError(
            f"{name} not found. Put it in a .env file in Documents\\sehtek-production "
            f"(checked: {', '.join(str(p) for p in ENV_LOCATIONS)})."
        )
    return value


def text_to_speech(text: str, out_mp3: Path) -> list:
    """Generate the voice-over. Returns word timings: [(word, start, end), ...]."""
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{brand.VOICE_ID}/with-timestamps",
        headers={"xi-api-key": _key("ELEVENLABS_API_KEY"), "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": os.environ.get("ELEVENLABS_MODEL", brand.VOICE_MODEL),
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15},
        },
        timeout=180,
    )
    if resp.status_code >= 400:
        raise ServiceError(f"ElevenLabs error {resp.status_code}: {resp.text[:500]}")
    body = resp.json()
    out_mp3.write_bytes(base64.b64decode(body["audio_base64"]))
    align = body.get("alignment") or body.get("normalized_alignment")
    return words_from_alignment(
        align["characters"],
        align["character_start_times_seconds"],
        align["character_end_times_seconds"],
    )


def words_from_alignment(chars, starts, ends) -> list:
    words, current, w_start, w_end = [], "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if current:
                words.append((current, w_start, w_end))
            current, w_start = "", None
            continue
        if w_start is None:
            w_start = s
        current += ch
        w_end = e
    if current:
        words.append((current, w_start, w_end))
    return words


def generate_image(prompt: str, out_path: Path, size: str = "1024x1536"):
    """Generate one image in the brand style and save it as JPEG."""
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {_key('OPENAI_API_KEY')}"},
        json={
            "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
            "prompt": f"{prompt}. {brand.IMAGE_STYLE}",
            "size": size,
            "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
            "n": 1,
        },
        timeout=300,
    )
    if resp.status_code >= 400:
        raise ServiceError(f"OpenAI image error {resp.status_code}: {resp.text[:500]}")
    raw = base64.b64decode(resp.json()["data"][0]["b64_json"])
    Image.open(io.BytesIO(raw)).convert("RGB").save(out_path, "JPEG", quality=92)
