# sehtek-publisher

Publishes the «صحتك أهم» Instagram page's reels and carousels automatically,
twice a day, using GitHub Actions. Your computer does not need to be on.

## How it works

1. Finished posts are added to `posts/` (one folder per post, see `posts/README.md`).
2. GitHub Pages serves the videos and images at a public link so Instagram can fetch them.
3. Every 15 minutes (at :07, :22, :37, :52), the **Publish to Instagram** workflow checks for a post whose
   time has come and publishes it (one post per run).
4. The result is saved in the post folder (`published.json` with the Instagram link,
   or `failed.json` with the error).
5. Every Monday, **Refresh Instagram token** extends `IGAA…` tokens (`EAA…` tokens never expire, so it does nothing).

Posts are produced by the **Produce a post** workflow (see `production/README.md`).

## One-time setup

### 1. Turn on GitHub Pages
Settings → Pages → Source: **Deploy from a branch** → Branch: **main**, folder **/ (root)** → Save.
After a minute the site is live at `https://sehtek-ahamm.github.io/sehtek-publisher/`.

### 2. Add the secrets
Settings → Secrets and variables → Actions → **New repository secret**:

| Name | Value | Needed? |
| --- | --- | --- |
| `IG_ACCESS_TOKEN` | token from the Meta developer app | always |
| `IG_USER_ID` | Instagram account ID (the **Check Instagram connection** workflow prints it) | optional, found automatically |
| `GH_PAT` | fine-grained GitHub token, this repo only, **Secrets: Read and write** | only for `IGAA…` tokens |
| `ELEVENLABS_API_KEY` | ElevenLabs API key | for cloud production |
| `OPENAI_API_KEY` | OpenAI API key | for cloud production |

Two token types work, detected by their first letters:

- **`EAA…`** — Unified login system-user token (new Meta apps). Never expires; no refresh, no `GH_PAT`.
- **`IGAA…`** — Instagram login token (older apps). Expires after 60 days; refreshed weekly using `GH_PAT`.

Secrets are encrypted. Nobody can read them, even though the repository is public.

### 3. Test the connection
Actions → **Check Instagram connection** → **Run workflow**.
It prints the token type, the account name and the Instagram account ID.

### 4. Test a publish without posting
Actions → **Publish to Instagram** → **Run workflow** with **Dry run** ticked.

## Useful commands (on your computer)

```bash
python publisher/publish.py --check     # check every post folder for mistakes
python publisher/publish.py --dry-run   # show the next due post
```

## Notes

- GitHub can start scheduled runs a few minutes late. That's normal.
- Instagram's own music library can't be added through the API, so videos carry royalty-free music.
- Optional repository variable `IG_API_VERSION` (e.g. `v23.0`) pins the Instagram API version.
