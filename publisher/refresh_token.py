#!/usr/bin/env python3
"""Extend the Instagram access token and save it back into the repo's secrets.

Instagram long-lived tokens expire after 60 days. GitHub Actions runs this
weekly so the token never expires.

Needs:
  IG_ACCESS_TOKEN  current token (repository secret)
  GH_PAT           fine-grained GitHub token with "Secrets: Read and write"
                   on this repository (repository secret)
  GITHUB_REPOSITORY  set automatically by GitHub Actions
"""

import base64
import os
import sys
from pathlib import Path

import requests
from nacl import encoding, public

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ig_api import InstagramError, refresh_long_lived_token  # noqa: E402

SECRET_NAME = "IG_ACCESS_TOKEN"


def save_secret(repo: str, gh_token: str, value: str):
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers, timeout=30,
    )
    key_resp.raise_for_status()
    key = key_resp.json()
    sealed_box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
    encrypted = base64.b64encode(sealed_box.encrypt(value.encode())).decode()
    put = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{SECRET_NAME}",
        headers=headers,
        json={"encrypted_value": encrypted, "key_id": key["key_id"]},
        timeout=30,
    )
    put.raise_for_status()


def main() -> int:
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    gh_token = os.environ.get("GH_PAT", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not gh_token or not repo:
        print("IG_ACCESS_TOKEN, GH_PAT and GITHUB_REPOSITORY must all be set.")
        return 1
    try:
        result = refresh_long_lived_token(token)
    except InstagramError as exc:
        print(exc)
        return 1
    new_token = result["access_token"]
    days = int(result.get("expires_in", 0)) // 86400
    try:
        save_secret(repo, gh_token, new_token)
    except requests.HTTPError as exc:
        print(f"Instagram token was refreshed but saving it to GitHub failed: {exc}")
        print("Check that GH_PAT has 'Secrets: Read and write' permission on this repository.")
        return 1
    print(f"Token refreshed and saved. Valid for about {days} more days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
