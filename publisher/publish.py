#!/usr/bin/env python3
"""Publish the next due post from posts/ to Instagram.

Run by GitHub Actions every 30 minutes. Publishes at most ONE post per run,
the oldest one whose publish_at time has passed.

Usage:
  python publisher/publish.py --check     # validate every post folder (no network)
  python publisher/publish.py --dry-run   # show what would be published now
  python publisher/publish.py             # publish the next due post
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ig_api import InstagramClient, InstagramError  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "posts"
MAX_ATTEMPTS = 3

POST_TYPES = {"reel", "carousel", "image"}
VIDEO_EXT = {".mp4", ".mov"}
IMAGE_EXT = {".jpg", ".jpeg"}  # the Instagram API accepts JPEG only for images
MAX_FILE_BYTES = 95 * 1024 * 1024  # GitHub rejects files over 100 MB
FOLDER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def media_base_url() -> str:
    """Public base URL where GitHub Pages serves this repository."""
    explicit = os.environ.get("MEDIA_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    repo = os.environ.get("GITHUB_REPOSITORY", "sehtek-ahamm/sehtek-publisher")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}"


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def parse_time(value: str) -> dt.datetime:
    when = dt.datetime.fromisoformat(value)
    if when.tzinfo is None:
        raise ValueError(f"publish_at '{value}' has no timezone, e.g. 2026-11-22T13:00:00+03:00")
    return when


# --- validation -------------------------------------------------------------

def validate_post(folder: Path) -> list:
    """Return a list of problems with this post folder (empty list = OK)."""
    problems = []
    if not FOLDER_RE.match(folder.name):
        problems.append("folder name must use only English letters, numbers, '-', '_' or '.'")
    post_file = folder / "post.json"
    if not post_file.exists():
        return problems + ["missing post.json"]
    try:
        post = load_json(post_file)
    except ValueError as exc:
        return problems + [f"post.json is not valid JSON: {exc}"]

    ptype = post.get("type")
    if ptype not in POST_TYPES:
        problems.append(f"type must be one of {sorted(POST_TYPES)}")
    try:
        parse_time(post.get("publish_at", ""))
    except (TypeError, ValueError) as exc:
        problems.append(f"publish_at: {exc}")

    caption = post.get("caption", "")
    if not caption.strip():
        problems.append("caption is empty")
    if len(caption) > 2200:
        problems.append(f"caption is {len(caption)} characters (max 2200)")
    if caption.count("#") > 30:
        problems.append("caption has more than 30 hashtags")

    media = post.get("media") or []
    if not media:
        problems.append("media list is empty")
    for name in media + ([post["cover"]] if post.get("cover") else []):
        path = folder / name
        if not FOLDER_RE.match(name):
            problems.append(f"file name '{name}' must use only English letters, numbers, '-', '_' or '.'")
        if not path.exists():
            problems.append(f"file not found: {name}")
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            problems.append(f"{name} is larger than 95 MB")

    exts = [Path(m).suffix.lower() for m in media]
    if ptype == "reel" and (len(media) != 1 or exts[0] not in VIDEO_EXT):
        problems.append("a reel needs exactly one .mp4 or .mov file in media")
    if ptype == "image" and (len(media) != 1 or exts[0] not in IMAGE_EXT):
        problems.append("an image post needs exactly one .jpg file in media")
    if ptype == "carousel":
        if not 2 <= len(media) <= 10:
            problems.append("a carousel needs 2 to 10 files")
        if any(e not in IMAGE_EXT | VIDEO_EXT for e in exts):
            problems.append("carousel files must be .jpg, .mp4 or .mov")
    if post.get("cover") and Path(post["cover"]).suffix.lower() not in IMAGE_EXT:
        problems.append("cover must be a .jpg file")
    return problems


def all_post_folders():
    if not POSTS_DIR.exists():
        return []
    return sorted(p for p in POSTS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_"))


def run_check() -> int:
    bad = 0
    folders = all_post_folders()
    for folder in folders:
        problems = validate_post(folder)
        if problems:
            bad += 1
            print(f"✗ {folder.name}")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"✓ {folder.name}")
    print(f"\n{len(folders) - bad} OK, {bad} with problems.")
    return 1 if bad else 0


# --- publishing ---------------------------------------------------------------

def due_posts():
    """Posts whose time has come, not yet published, not drafts, oldest first."""
    due = []
    for folder in all_post_folders():
        if (folder / "published.json").exists():
            continue
        failed = folder / "failed.json"
        if failed.exists() and load_json(failed).get("attempts", 0) >= MAX_ATTEMPTS:
            continue
        if validate_post(folder):
            print(f"Skipping {folder.name}: it has problems (run --check).")
            continue
        post = load_json(folder / "post.json")
        if post.get("draft"):
            continue
        when = parse_time(post["publish_at"])
        if when <= now_utc():
            due.append((when, folder, post))
    due.sort(key=lambda item: item[0])
    return due


def seconds_until_next() -> int:
    """Seconds until the next post that still has to be published (0 if one is overdue, -1 if none)."""
    soonest = None
    for folder in all_post_folders():
        if (folder / "published.json").exists():
            continue
        failed = folder / "failed.json"
        if failed.exists() and load_json(failed).get("attempts", 0) >= MAX_ATTEMPTS:
            continue
        if validate_post(folder):
            continue
        post = load_json(folder / "post.json")
        if post.get("draft"):
            continue
        when = parse_time(post["publish_at"])
        if soonest is None or when < soonest:
            soonest = when
    if soonest is None:
        return -1
    return max(0, int((soonest - now_utc()).total_seconds()))


def public_url(folder: Path, name: str) -> str:
    return f"{media_base_url()}/posts/{quote(folder.name)}/{quote(name)}"


def media_reachable(urls) -> bool:
    for url in urls:
        try:
            resp = requests.head(url, timeout=30, allow_redirects=True)
        except requests.RequestException as exc:
            print(f"Media not reachable yet: {url} ({exc})")
            return False
        if resp.status_code != 200:
            print(f"Media not reachable yet ({resp.status_code}): {url}")
            return False
    return True


def publish_one(folder: Path, post: dict, dry_run: bool) -> int:
    urls = [public_url(folder, m) for m in post["media"]]
    cover_url = public_url(folder, post["cover"]) if post.get("cover") else None
    print(f"Next due post: {folder.name} ({post['type']}, scheduled {post['publish_at']})")
    for url in urls:
        print(f"  media: {url}")

    if not media_reachable(urls + ([cover_url] if cover_url else [])):
        print("GitHub Pages has not served the files yet. Will retry on the next run.")
        return 0
    if dry_run:
        print("Dry run: nothing was published.")
        return 0

    client = InstagramClient(os.environ.get("IG_USER_ID", ""), os.environ.get("IG_ACCESS_TOKEN", ""))
    try:
        if post["type"] == "reel":
            result = client.publish_reel(urls[0], post["caption"], cover_url,
                                         post.get("share_to_feed", True))
        elif post["type"] == "image":
            result = client.publish_image(urls[0], post["caption"])
        else:
            result = client.publish_carousel(urls, post["caption"])
    except (InstagramError, requests.RequestException) as exc:
        failed_path = folder / "failed.json"
        previous = load_json(failed_path) if failed_path.exists() else {}
        attempts = previous.get("attempts", 0) + 1
        write_json(failed_path, {
            "attempts": attempts,
            "last_error": str(exc),
            "last_attempt_at": now_utc().isoformat(),
            "gave_up": attempts >= MAX_ATTEMPTS,
        })
        print(f"FAILED (attempt {attempts}/{MAX_ATTEMPTS}): {exc}")
        return 1

    write_json(folder / "published.json", {
        **result,
        "published_at": now_utc().isoformat(),
        "bank_id": post.get("bank_id"),
    })
    failed_path = folder / "failed.json"
    if failed_path.exists():
        failed_path.unlink()
    print(f"Published: {result.get('permalink')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate all posts, no network")
    parser.add_argument("--dry-run", action="store_true", help="show the next due post without publishing")
    parser.add_argument("--next-due", action="store_true", help="print seconds until the next post (-1 if none)")
    args = parser.parse_args()

    if args.check:
        return run_check()
    if args.next_due:
        print(seconds_until_next())
        return 0

    due = due_posts()
    if not due:
        print("No post is due right now.")
        return 0
    if len(due) > 1:
        print(f"{len(due)} posts are due; publishing the oldest one this run.")
    _, folder, post = due[0]
    return publish_one(folder, post, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
