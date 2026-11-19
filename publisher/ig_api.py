"""Small client for publishing to Instagram. No Facebook Page is needed.

Two kinds of token work, picked automatically by the token's first letters:

* EAA...  Unified login system-user token (new Meta apps). Never expires.
          Host: graph.facebook.com. The Instagram account ID comes from
          /me/assigned_instagram_accounts (or the IG_USER_ID secret).
* IGAA... Instagram login token (older apps). Expires after 60 days and is
          refreshed weekly. Host: graph.instagram.com.

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
"""

import os
import time

import requests

INSTAGRAM_HOST = "https://graph.instagram.com"
FACEBOOK_HOST = "https://graph.facebook.com"
# Version for graph.facebook.com (it requires one); override with IG_API_VERSION.
DEFAULT_FACEBOOK_VERSION = "v23.0"

# How long to wait for Instagram to finish processing a video.
PROCESSING_TIMEOUT_SECONDS = 15 * 60
POLL_INTERVAL_SECONDS = 15


class InstagramError(Exception):
    pass


def is_unified_token(token: str) -> bool:
    return token.startswith("EAA")


def base_url(token: str) -> str:
    version = os.environ.get("IG_API_VERSION", "").strip()
    if is_unified_token(token):
        return f"{FACEBOOK_HOST}/{version or DEFAULT_FACEBOOK_VERSION}"
    return f"{INSTAGRAM_HOST}/{version}" if version else INSTAGRAM_HOST


def graph_get(token: str, path: str, **params) -> dict:
    params["access_token"] = token
    resp = requests.get(f"{base_url(token)}/{path.lstrip('/')}", params=params, timeout=60)
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}
    if resp.status_code >= 400 or "error" in body:
        raise InstagramError(f"GET {path} failed ({resp.status_code}): {body.get('error', body)}")
    return body


def find_account_id(token: str) -> str:
    """The Instagram account ID this token publishes to."""
    if is_unified_token(token):
        data = graph_get(token, "me/assigned_instagram_accounts").get("data", [])
        if not data:
            raise InstagramError(
                "No Instagram account is assigned to this token. In the Meta app's "
                "configuration, add the Instagram account as an asset and generate the token again."
            )
        if len(data) > 1:
            raise InstagramError(
                "Several Instagram accounts are assigned to this token; set the IG_USER_ID secret "
                "to the right one: " + ", ".join(str(a.get("id")) for a in data)
            )
        return str(data[0]["id"])
    return str(graph_get(token, "me", fields="user_id")["user_id"])


class InstagramClient:
    def __init__(self, user_id: str, access_token: str):
        if not access_token:
            raise InstagramError("IG_ACCESS_TOKEN must be set (GitHub repository secret).")
        self.token = access_token
        self.user_id = user_id or find_account_id(access_token)

    # --- low-level helpers -------------------------------------------------

    def _request(self, method: str, path: str, **params):
        params["access_token"] = self.token
        url = f"{base_url(self.token)}/{path.lstrip('/')}"
        if method == "GET":
            resp = requests.get(url, params=params, timeout=60)
        else:
            resp = requests.post(url, data=params, timeout=120)
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}
        if resp.status_code >= 400 or "error" in body:
            err = body.get("error", body)
            # Never echo the token.
            raise InstagramError(f"{method} {path} failed ({resp.status_code}): {err}")
        return body

    def account(self):
        return self._request("GET", self.user_id, fields="id,username")

    def _wait_until_ready(self, container_id: str):
        deadline = time.time() + PROCESSING_TIMEOUT_SECONDS
        while True:
            info = self._request("GET", container_id, fields="status_code,status")
            code = info.get("status_code")
            if code in ("FINISHED", "PUBLISHED"):
                return
            if code in ("ERROR", "EXPIRED"):
                raise InstagramError(
                    f"Instagram could not process container {container_id}: {info.get('status')}"
                )
            if time.time() > deadline:
                raise InstagramError(
                    f"Timed out waiting for container {container_id} (last status: {code})"
                )
            time.sleep(POLL_INTERVAL_SECONDS)

    def _publish_container(self, container_id: str) -> dict:
        self._wait_until_ready(container_id)
        result = self._request(
            "POST", f"{self.user_id}/media_publish", creation_id=container_id
        )
        media_id = result["id"]
        details = self._request("GET", media_id, fields="permalink,timestamp")
        return {"media_id": media_id, "permalink": details.get("permalink")}

    # --- public publishing methods ----------------------------------------

    def publish_reel(self, video_url: str, caption: str, cover_url: str = None,
                     share_to_feed: bool = True) -> dict:
        params = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
        }
        if cover_url:
            params["cover_url"] = cover_url
        container = self._request("POST", f"{self.user_id}/media", **params)
        return self._publish_container(container["id"])

    def publish_image(self, image_url: str, caption: str) -> dict:
        container = self._request(
            "POST", f"{self.user_id}/media", image_url=image_url, caption=caption
        )
        return self._publish_container(container["id"])

    def publish_carousel(self, item_urls: list, caption: str) -> dict:
        children = []
        for url in item_urls:
            params = {"is_carousel_item": "true"}
            if url.lower().endswith((".mp4", ".mov")):
                params["media_type"] = "VIDEO"
                params["video_url"] = url
            else:
                params["image_url"] = url
            child = self._request("POST", f"{self.user_id}/media", **params)
            children.append(child["id"])
        for child_id in children:
            self._wait_until_ready(child_id)
        container = self._request(
            "POST",
            f"{self.user_id}/media",
            media_type="CAROUSEL",
            children=",".join(children),
            caption=caption,
        )
        return self._publish_container(container["id"])


def refresh_long_lived_token(access_token: str) -> dict:
    """Extend a long-lived Instagram token by 60 days. Returns the API response."""
    resp = requests.get(
        f"{INSTAGRAM_HOST}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": access_token},
        timeout=60,
    )
    body = resp.json()
    if resp.status_code >= 400 or "error" in body:
        raise InstagramError(f"Token refresh failed ({resp.status_code}): {body.get('error', body)}")
    return body
