"""Paid services: ElevenLabs (voice) and OpenAI (images). Keys come from a .env file."""

import base64
import io
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

import brand
import pronunciation

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
    text = pronunciation.prepare(text)
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


def generate_image(prompt: str, out_path: Path, size: str = "1024x1536", style: str = None):
    """Generate one image in the brand style (or the given style) and save it as JPEG."""
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {_key('OPENAI_API_KEY')}"},
        json={
            "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
            "prompt": f"{prompt}. {style or brand.IMAGE_STYLE}",
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


def generate_image_with_refs(prompt: str, out_path: Path, refs: list, size: str = "1024x1536", style: str = None):
    """Generate one image that matches reference images (same character, kitchen, props).

    Uses OpenAI image edits with the references as input images.
    """
    files = [("image[]", (Path(r).name, open(r, "rb"), "image/jpeg")) for r in refs]
    try:
        resp = requests.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {_key('OPENAI_API_KEY')}"},
            data={
                "model": os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2"),
                "prompt": (f"{prompt}. Keep exactly the same woman (neck down, same apron, top, bracelet and hands), "
                           f"the same kitchen, materials and props as in the reference images. "
                           f"{style or brand.IMAGE_STYLE}"),
                "size": size,
                "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"),
                "n": "1",
            },
            files=files,
            timeout=400,
        )
    finally:
        for _, (_, fh, _) in files:
            fh.close()
    if resp.status_code >= 400:
        raise ServiceError(f"OpenAI image error {resp.status_code}: {resp.text[:500]}")
    raw = base64.b64decode(resp.json()["data"][0]["b64_json"])
    Image.open(io.BytesIO(raw)).convert("RGB").save(out_path, "JPEG", quality=92)


# --- recorded voice (the user's own recording instead of text-to-speech) -------------------

def align_words(audio: Path, text: str) -> list:
    """Word timings for a recorded voice-over, matched to its script (ElevenLabs forced alignment)."""
    with open(audio, "rb") as fh:
        resp = requests.post(
            "https://api.elevenlabs.io/v1/forced-alignment",
            headers={"xi-api-key": _key("ELEVENLABS_API_KEY")},
            files={"file": (audio.name, fh, "audio/mpeg")},
            data={"text": text},
            timeout=300,
        )
    if resp.status_code >= 400:
        raise ServiceError(f"ElevenLabs alignment error {resp.status_code}: {resp.text[:500]}")
    return [(w["text"].strip(), w["start"], w["end"]) for w in resp.json()["words"] if w["text"].strip()]


def transcribe(audio: Path) -> str:
    """Plain transcript of a recording (ElevenLabs speech-to-text)."""
    with open(audio, "rb") as fh:
        resp = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": _key("ELEVENLABS_API_KEY")},
            files={"file": (audio.name, fh, "audio/mpeg")},
            data={"model_id": "scribe_v1", "language_code": "ara"},
            timeout=300,
        )
    if resp.status_code >= 400:
        raise ServiceError(f"ElevenLabs speech-to-text error {resp.status_code}: {resp.text[:500]}")
    return resp.json().get("text", "")
