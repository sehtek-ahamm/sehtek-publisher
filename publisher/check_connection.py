#!/usr/bin/env python3
"""Confirm the Instagram token works and show which account it publishes to."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ig_api import InstagramClient, InstagramError, is_unified_token  # noqa: E402


def main() -> int:
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    if not token:
        print("IG_ACCESS_TOKEN secret is not set.")
        return 1
    kind = "Unified login (EAA, never expires)" if is_unified_token(token) else "Instagram login (IGAA, renewed weekly)"
    print(f"Token type: {kind}")
    configured = os.environ.get("IG_USER_ID", "").strip()
    try:
        client = InstagramClient(configured, token)
        account = client.account()
    except InstagramError as exc:
        print(f"Connection failed: {exc}")
        return 1
    print(f"Connected to Instagram account: @{account.get('username')}")
    print(f"Instagram account ID: {client.user_id}")
    if configured:
        print("Using the IG_USER_ID secret.")
    else:
        print("IG_USER_ID secret is not set; the account ID was found automatically. "
              "Optionally save the ID above as the IG_USER_ID secret.")
    print("Everything is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
