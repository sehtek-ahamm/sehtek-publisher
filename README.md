# sehtek-publisher

Publishes the «صحتك أهم» Instagram page's reels and carousels automatically,
twice a day, using GitHub Actions. Your computer does not need to be on.

## How it works

1. Finished posts are added to `posts/` (one folder per post, see `posts/README.md`).
2. GitHub Pages serves the videos and images at a public link so Instagram can fetch them.
3. Every 30 minutes, the **Publish to Instagram** workflow checks for a post whose
   time has come and publishes it (one post per run).
4. The result is saved in the post folder (`published.json` with the Instagram link,
   or `failed.json` with the error).
5. Every Monday, **Refresh Instagram token** extends the Instagram token so it never expires.

## One-time setup

### 1. Turn on GitHub Pages
Settings → Pages → Source: **Deploy from a branch** → Branch: **main**, folder **/ (root)** → Save.
After a minute the site is live at `https://sehtek-ahamm.github.io/sehtek-publisher/`.

### 2. Add the secrets
Settings → Secrets and variables → Actions → **New repository secret**:

| Name | Value |
| --- | --- |
| `IG_ACCESS_TOKEN` | long-lived Instagram token from the Meta developer app |
| `IG_USER_ID` | your Instagram user ID (the **Check Instagram connection** workflow prints it) |
| `GH_PAT` | fine-grained GitHub token, repository access: this repo only, permission **Secrets: Read and write** |

Secrets are encrypted. Nobody can read them, even though the repository is public.

### 3. Test the connection
Actions → **Check Instagram connection** → **Run workflow**.
It prints the account name and user ID. Copy the user ID into the `IG_USER_ID` secret, then run it again.

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
