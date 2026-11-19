# Production

Turns an approved script (a **job file** in `production/jobs/`) into a finished post in `posts/`,
in the «صحتك أهم» visual style.

| Post type | What it uses | Cost |
| --- | --- | --- |
| Reel | ElevenLabs voice + OpenAI images + ffmpeg | about $0.40–0.60 |
| Carousel | brand slide templates drawn in code | free |

## One-time setup on Windows

1. Install Python 3.12 from python.org (tick **Add python.exe to PATH**).
2. Install ffmpeg: open PowerShell and run `winget install Gyan.FFmpeg`, then open a new PowerShell window.
3. In the repository folder: `pip install -r production/requirements.txt`
4. Keys: a `.env` file in `Documents\sehtek-production\` with
   ```
   ELEVENLABS_API_KEY=...
   OPENAI_API_KEY=...
   ```
   (The program also finds `.env` in the repository folder or its parent.)
5. Optional: put the logo as `production/assets/logo.png` (transparent PNG) and royalty-free
   music as `.mp3` files in `production/assets/music/`.

## Make a post

```bash
# free layout test (no API calls) — output in production/build/offline-preview/
python production/make_post.py production/jobs/004-avocado-banana.json --offline

# real post — output in posts/<date>-<time>-<slug>/ (or posts/_review-<slug>/ if no date yet)
python production/make_post.py production/jobs/004-avocado-banana.json
```

Voice and images are cached in `production/build/<slug>/`, so running again after a text fix
doesn't pay for them twice. Delete that folder to regenerate them.

## Review and approve

1. Watch `video.mp4` (or look at the slides).
2. Set `publish_at` in the job file (e.g. `"2026-11-22T13:00:00+03:00"`) and run the job again
   (cached voice and images are reused, so it's free).
3. Approve: `python production/make_post.py --approve posts/<folder>`
4. Commit and push. GitHub publishes it at its time.

## Job file

See `production/jobs/004-avocado-banana.json` (reel) and `058-breastmilk-storage.json` (carousel).

- Reel: `hook`, `voiceover`, 4–6 `scenes` (each an `image_prompt` in English), `end_text`, `caption`.
- Carousel: `slides` of kind `cover`, `point` (number, title, body) and `final`; `source_short` shows on the last point slide.
- Image style is added automatically from `brand.py` (`IMAGE_STYLE`), so prompts describe only the subject.

## Settings (optional, in `.env`)

| Name | Default |
| --- | --- |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2` |
| `OPENAI_IMAGE_QUALITY` | `medium` (`low` is about 10× cheaper) |
| `ELEVENLABS_MODEL` | `eleven_multilingual_v2` |
