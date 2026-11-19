# Instructions for Claude working in this repository

This repository is the publishing queue for the Arabic Instagram page «صحتك أهم».

## Producing posts (on the user's Windows computer)

Follow `production/README.md`. In short:

1. Job files (approved scripts) live in `production/jobs/`. Never write medical content yourself
   that isn't in an approved job or in the ideas bank sheet.
2. First run any new job with `--offline` (free) to check the layout, then without it.
   Real runs call paid APIs (ElevenLabs, OpenAI): run each job once; re-runs reuse the cache.
3. Show the user the result and wait for their OK before setting `publish_at` and running
   `python production/make_post.py --approve posts/<folder>`.
4. Keys are in a `.env` file (usually `Documents\sehtek-production\.env`). Never print, copy,
   or commit them.

## Adding finished posts

1. Create one folder per post in `posts/`, named `YYYY-MM-DD-HHMM-short-english-slug`
   (HHMM = 1300 or 2130, Riyadh time). Follow `posts/README.md` exactly.
2. Copy the rendered media in (reel: `video.mp4` + optional `cover.jpg`; carousel: `01.jpg` … `10.jpg`, JPEG only).
3. Write `post.json` with the caption from the ideas bank sheet, `publish_at` with `+03:00`,
   and `bank_id` = the idea number.
4. Run `python publisher/publish.py --check` and fix every problem before committing.
5. Never schedule two posts from the same pillar back to back (rotation rule from the content plan).
6. Commit with a message like `Add posts for week of 2026-11-22` and push to `main`.

## Do not

- Do not edit `published.json` or `failed.json` except to delete a `failed.json` when the user asks to retry.
- Do not put tokens or keys in any file. They live in GitHub repository secrets only.
- Do not add posts on sensitive topics unless the user has approved them in the ideas bank sheet.
