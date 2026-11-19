# Production

Turns an approved script (a **job file** in `production/jobs/`) into a finished post in `posts/`,
in the «صحتك أهم» visual style.

| Post type | What it uses | Cost |
| --- | --- | --- |
| Reel | ElevenLabs voice + OpenAI images + ffmpeg | about $0.40–0.60 |
| Carousel | brand slide templates drawn in code | free |

## Cloud production (recommended)

Production can run entirely on GitHub, so no computer is needed:

1. Add repository secrets `ELEVENLABS_API_KEY` and `OPENAI_API_KEY`
   (Settings → Secrets and variables → Actions → New repository secret).
2. Start it from chat (Claude) or by hand: Actions → **Produce a post** → Run workflow,
   with the job file path, e.g. `production/jobs/004-avocado-banana.json`.
3. The finished post is saved in `posts/` with `draft: true` (never published as a draft),
   and the voice and AI images are saved in `production/cache/<slug>/`, so re-renders are free.
4. After review: `python production/make_post.py --approve posts/<folder> --at 2026-11-22T13:00:00+03:00`,
   commit and push. GitHub publishes it at that time.

## One-time setup on Windows (local production, optional)

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

Voice and images are cached in `production/cache/<slug>/` (committed to the repository), so running
again after a text fix doesn't pay for them twice. Delete that folder to regenerate them.

## Review and approve

1. Watch `video.mp4` (or look at the slides).
2. Approve with a publish time:
   `python production/make_post.py --approve posts/<folder> --at 2026-11-22T13:00:00+03:00`
3. The folder is renamed to its date and time automatically.
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
