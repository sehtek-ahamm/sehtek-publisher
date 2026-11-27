"""Pull per-post Instagram insights into a JSON file (no keys are written).

Usage: python publisher/insights.py OUT.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from ig_api import InstagramError, find_account_id, graph_get  # noqa: E402

REEL_METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
                "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
FEED_METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions"]


def metrics_for(token, media_id, names):
    out, errors = {}, {}
    try:
        body = graph_get(token, f"{media_id}/insights", metric=",".join(names))
        for m in body.get("data", []):
            out[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
        return out, errors
    except InstagramError:
        pass
    for n in names:  # one at a time so one unsupported metric does not hide the rest
        try:
            body = graph_get(token, f"{media_id}/insights", metric=n)
            for m in body.get("data", []):
                out[m["name"]] = (m.get("values") or [{}])[0].get("value")
        except InstagramError as e:
            errors[n] = str(e)[:200]
    return out, errors


def main():
    token = os.environ["IG_ACCESS_TOKEN"]
    user = os.environ.get("IG_USER_ID") or find_account_id(token)
    acct = graph_get(token, user, fields="username,followers_count,media_count")
    items, after = [], None
    while True:
        params = {"fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count", "limit": 50}
        if after:
            params["after"] = after
        body = graph_get(token, f"{user}/media", **params)
        items += body.get("data", [])
        after = body.get("paging", {}).get("cursors", {}).get("after")
        if not body.get("paging", {}).get("next"):
            break
    for it in items:
        names = REEL_METRICS if it.get("media_product_type") == "REELS" else FEED_METRICS
        it["insights"], err = metrics_for(token, it["id"], names)
        if err:
            it["insight_errors"] = err
    json.dump({"account": acct, "media": items}, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    print(f"{len(items)} posts written; followers {acct.get('followers_count')}")


if __name__ == "__main__":
    main()
