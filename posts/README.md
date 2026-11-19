# Posts queue

Each post is one folder inside `posts/`. Folders starting with `_` (like `_example`) are ignored.

## Folder name

English letters, numbers and `-` only. Start with the date and slot so folders sort in order:

```
posts/2026-11-22-1300-avocado-banana/
posts/2026-11-22-2130-honey-myth/
```

## What goes in a folder

| File | Needed for | Notes |
| --- | --- | --- |
| `post.json` | every post | see below |
| `video.mp4` | reels | vertical 9:16, H.264 + AAC, 3–90 seconds, under 95 MB |
| `cover.jpg` | reels (optional) | 1080×1920 JPEG |
| `01.jpg`, `02.jpg`, … | carousels (2–10) / image posts (1) | JPEG only, 1080×1350 recommended |

## post.json

```json
{
  "bank_id": 4,
  "type": "reel",
  "publish_at": "2026-11-22T13:00:00+03:00",
  "media": ["video.mp4"],
  "cover": "cover.jpg",
  "share_to_feed": true,
  "draft": false,
  "caption": "Caption text with #hashtags"
}
```

- `type`: `reel`, `carousel` or `image`.
- `publish_at`: Riyadh time with `+03:00` at the end.
- `media`: file names in display order.
- `draft: true` keeps the post from being published.
- `bank_id`: the idea number in the ideas bank sheet.

## After publishing

The workflow adds `published.json` (with the Instagram link) to the folder.
If publishing fails it writes `failed.json` and retries on the next runs, up to 3 times.
To retry after 3 failures, delete `failed.json`.
