#!/usr/bin/env python3
"""Confirm the Instagram token works and print the account's user ID."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ig_api import InstagramError, _url  # noqa: E402

import requests  # noqa: E402


def main() -> int:
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    if not token:
        print("IG_ACCESS_TOKEN secret is not set.")
        return 1
    resp = requests.get(_url("me"), params={
        "fields": "user_id,username,account_type", "access_token": token}, timeout=30)
    body = resp.json()
    if resp.status_code >= 400 or "error" in body:
        print(f"Connection failed: {body.get('error', body)}")
        return 1
    print(f"Connected to Instagram account: @{body.get('username')}")
    print(f"Account type: {body.get('account_type')}")
    print(f"IG_USER_ID to save as a secret: {body.get('user_id')}")
    configured = os.environ.get("IG_USER_ID", "")
    if configured and configured != str(body.get("user_id")):
        print("WARNING: the IG_USER_ID secret does not match this account.")
        return 1
    if configured:
        print("IG_USER_ID secret matches. Everything is ready.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InstagramError as exc:
        print(exc)
        sys.exit(1)
