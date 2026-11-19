"""Small client for the Instagram API with Instagram Login (graph.instagram.com).

No Facebook Page is needed. Docs:
https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing
"""

import os
import time

import requests

GRAPH_HOST = "https://graph.instagram.com"
# Optional, e.g. "v23.0". Empty means Meta's default version.
API_VERSION = os.environ.get("IG_API_VERSION", "").strip()

# How long to wait for Instagram to finish processing a video.
PROCESSING_TIMEOUT_SECONDS = 15 * 60
POLL_INTERVAL_SECONDS = 15


class InstagramError(Exception):
    pass


def _url(path: str) -> str:
    path = path.lstrip("/")
    if API_VERSION:
        return f"{GRAPH_HOST}/{API_VERSION}/{path}"
    return f"{GRAPH_HOST}/{path}"


class InstagramClient:
    def __init__(self, user_id: str, access_token: str):
        if not user_id or not access_token:
            raise InstagramError(
                "IG_USER_ID and IG_ACCESS_TOKEN must be set (GitHub repository secrets)."
            )
        self.user_id = user_id
        self.token = access_token

    # --- low-level helpers -------------------------------------------------

    def _request(self, method: str, path: str, **params):
        params["access_token"] = self.token
        if method == "GET":
            resp = requests.get(_url(path), params=params, timeout=60)
        else:
            resp = requests.post(_url(path), data=params, timeout=120)
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}
        if resp.status_code >= 400 or "error" in body:
            err = body.get("error", body)
            # Never echo the token.
            raise InstagramError(f"{method} {path} failed ({resp.status_code}): {err}")
        return body

    def whoami(self):
        return self._request("GET", "me", fields="user_id,username,account_type")

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
        f"{GRAPH_HOST}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": access_token},
        timeout=60,
    )
    body = resp.json()
    if resp.status_code >= 400 or "error" in body:
        raise InstagramError(f"Token refresh failed ({resp.status_code}): {body.get('error', body)}")
    return body
