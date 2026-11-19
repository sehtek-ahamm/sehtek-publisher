#!/usr/bin/env python3
"""Turn a job file (approved script) into a finished post in posts/.

Usage:
  python production/make_post.py production/jobs/<job>.json            # real run (paid APIs)
  python production/make_post.py production/jobs/<job>.json --offline  # free layout test, no APIs
  python production/make_post.py --approve posts/<folder>              # mark a reviewed post ready to publish

Reels: ElevenLabs voice + OpenAI images + ffmpeg (slow zooms, hook box, subtitles, end card).
Carousels: slides drawn from the brand templates (no paid API).

Voice and images are cached in production/build/<slug>/, so re-running after a
fix does not pay for them again. Delete that folder to regenerate them.
"""

import argparse
import datetime as dt
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import brand  # noqa: E402
import graphics  # noqa: E402
import services  # noqa: E402

ROOT = HERE.parent
POSTS = ROOT / "posts"
BUILD = HERE / "build"
W, H = brand.REEL_SIZE
FPS = brand.FPS
HOOK_SECONDS = 3.0
END_CARD_SECONDS = 1.4


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(map(str, cmd[:6]))}...\n{result.stderr[-2000:]}")
    return result.stdout


def duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def check_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg is not installed. On Windows run:  winget install Gyan.FFmpeg  then open a new terminal.")


def folder_name(job: dict) -> str:
    slug = job["slug"]
    if job.get("publish_at"):
        when = dt.datetime.fromisoformat(job["publish_at"])
        return f"{when:%Y-%m-%d-%H%M}-{slug}"
    return f"_review-{slug}"


# --- subtitles ---------------------------------------------------------------------

def subtitle_chunks(words, max_words=4, max_chars=22):
    chunks, cur = [], []
    for w in words:
        text = " ".join(x[0] for x in cur + [w])
        if cur and (len(cur) >= max_words or len(text) > max_chars):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w[0][-1:] in ".،,؟?!:" and len(cur) >= 2:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        start = c[0][1]
        end = chunks[i + 1][0][1] if i + 1 < len(chunks) else c[-1][2] + 0.3
        out.append((" ".join(x[0] for x in c), start, end))
    return out


def fake_words(text: str):
    words = text.split()
    per = 0.42
    return [(w, i * per, i * per + per * 0.9) for i, w in enumerate(words)]


# --- reel ----------------------------------------------------------------------------

def make_reel(job: dict, out_dir: Path, offline: bool):
    work = BUILD / job["slug"]
    work.mkdir(parents=True, exist_ok=True)

    # 1. Voice
    voice = work / "voice.mp3"
    words_file = work / "words.json"
    if offline:
        words = fake_words(job["voiceover"])
        length = words[-1][2] + 0.4
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{length:.2f}",
             "-c:a", "libmp3lame", str(voice)])
    elif voice.exists() and words_file.exists():
        words = json.loads(words_file.read_text(encoding="utf-8"))
        print("  voice: reusing cached voice-over")
    else:
        print("  voice: ElevenLabs...")
        words = services.text_to_speech(job["voiceover"], voice)
        words_file.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    voice_len = duration(voice)

    # 2. Scene images
    scenes = job["scenes"]
    images = []
    for i, scene in enumerate(scenes):
        img_path = work / f"scene{i + 1}.png"
        if offline:
            graphics.placeholder_scene(i, scene["image_prompt"]).save(img_path)
        elif img_path.exists():
            print(f"  image {i + 1}: reusing cached image")
        else:
            print(f"  image {i + 1}/{len(scenes)}: OpenAI...")
            services.generate_image(scene["image_prompt"], img_path)
        images.append(img_path)

    # 3. Scene clips with slow zoom (alternating in / out)
    main_len = voice_len + 0.5
    per_scene = main_len / len(images)
    frames = max(int(per_scene * FPS), 1)
    clips = []
    for i, img in enumerate(images):
        clip = work / f"clip{i + 1}.mp4"
        zoom = ("min(zoom+0.0007,1.12)" if i % 2 == 0
                else "if(eq(on,0),1.12,max(zoom-0.0007,1.0))")
        vf = (f"crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=2160:3840,"
              f"zoompan=z='{zoom}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
              f"fade=t=in:st=0:d=0.25,format=yuv420p")
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-vf", vf, "-frames:v", str(frames),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS), str(clip)])
        clips.append(clip)

    # 4. End card clip
    end_png = work / "endcard.png"
    graphics.end_card(job.get("end_text", "احفظيها لوقت الحاجة")).save(end_png)
    end_clip = work / "endcard.mp4"
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(end_png), "-vf", f"fade=t=in:st=0:d=0.3,format=yuv420p",
         "-t", f"{END_CARD_SECONDS}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS), str(end_clip)])

    # 5. Join clips
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{c.name}'\n" for c in clips + [end_clip]), encoding="utf-8")
    base = work / "base.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(base)])
    total = main_len + END_CARD_SECONDS

    # 6. Overlays: hook, subtitles, watermark
    overlays = []  # (png, start, end)
    hook_png = work / "hook.png"
    graphics.hook_overlay(job["hook"]).save(hook_png)
    overlays.append((hook_png, 0, HOOK_SECONDS))
    hook_spoken = job["voiceover"].strip().startswith(job["hook"].strip().rstrip(".!؟?"))
    for n, (text, start, end) in enumerate(subtitle_chunks(words)):
        if hook_spoken and start < HOOK_SECONDS:
            continue  # the hook box already shows these words
        png = work / f"sub{n + 1}.png"
        graphics.subtitle_overlay(text).save(png)
        overlays.append((png, max(start, 0), min(end, main_len)))
    wm_png = work / "watermark.png"
    graphics.watermark_overlay().save(wm_png)
    overlays.append((wm_png, HOOK_SECONDS, main_len))

    inputs = ["-i", str(base), "-i", str(voice)]
    for png, _, _ in overlays:
        inputs += ["-i", str(png)]
    music = sorted(brand.MUSIC_DIR.glob("*.mp3")) if brand.MUSIC_DIR.exists() else []
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(random.choice(music))]

    chain, last = [], "[0:v]"
    for k, (_, start, end) in enumerate(overlays):
        label = f"[v{k}]"
        chain.append(f"{last}[{k + 2}:v]overlay=0:0:enable='between(t,{start:.2f},{end:.2f})'{label}")
        last = label
    audio = "[1:a]apad,atrim=0:{:.2f}[voice]".format(total)
    chain.append(audio)
    if music:
        m = len(overlays) + 2
        chain.append(f"[{m}:a]volume=0.07,atrim=0:{total:.2f},afade=t=out:st={total - 1.5:.2f}:d=1.5[music]")
        chain.append("[voice][music]amix=inputs=2:duration=first:normalize=0[aout]")
    else:
        chain.append("[voice]anull[aout]")

    video = out_dir / "video.mp4"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", last, "-map", "[aout]",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(video)])

    # 7. Cover image: first scene + hook
    first = Image.open(images[0]).convert("RGB")
    fw, fh = first.size
    cw = min(fw, int(fh * 9 / 16))
    ch = min(fh, int(fw * 16 / 9))
    first = first.crop(((fw - cw) // 2, (fh - ch) // 2, (fw + cw) // 2, (fh + ch) // 2)).resize((W, H))
    cover = first.convert("RGBA")
    cover.alpha_composite(graphics.hook_overlay(job["hook"]))
    cover.convert("RGB").save(out_dir / "cover.jpg", quality=92)

    print(f"  video: {total:.1f} s, {video.stat().st_size / 1e6:.1f} MB")
    return ["video.mp4"], "cover.jpg"


# --- carousel --------------------------------------------------------------------------

def make_carousel(job: dict, out_dir: Path):
    files = []
    source = job.get("source_short", "")
    slides = job["slides"]
    for i, s in enumerate(slides):
        kind = s["kind"]
        if kind == "cover":
            img = graphics.slide_cover(s["title"], s.get("subtitle", ""), job.get("pillar", ""))
        elif kind == "final":
            img = graphics.slide_final(s["title"])
        else:
            is_last_point = i + 1 < len(slides) and slides[i + 1]["kind"] == "final"
            img = graphics.slide_point(s.get("number"), s["title"], s.get("body", ""),
                                       source if is_last_point else "")
        name = f"{len(files) + 1:02d}.jpg"
        img.save(out_dir / name, quality=92)
        files.append(name)
    if not 2 <= len(files) <= 10:
        raise ValueError("A carousel needs 2 to 10 slides.")
    print(f"  slides: {len(files)}")
    return files, None


# --- main --------------------------------------------------------------------------------

def approve(folder: Path):
    post_file = folder / "post.json"
    post = json.loads(post_file.read_text(encoding="utf-8"))
    if not post.get("publish_at"):
        sys.exit("This post has no publish_at yet. Add it to the job file and produce it again.")
    post["draft"] = False
    post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Approved: {folder.name} will publish at {post['publish_at']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job", nargs="?", help="job JSON file")
    parser.add_argument("--offline", action="store_true", help="free layout test: no ElevenLabs/OpenAI calls")
    parser.add_argument("--approve", metavar="POST_FOLDER", help="mark a reviewed post ready to publish")
    args = parser.parse_args()

    if args.approve:
        return approve(Path(args.approve))
    if not args.job:
        parser.error("give a job file or --approve")

    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    if not args.offline and job["type"] == "reel":
        env = services.load_keys()
        print(f"Keys loaded from: {env}" if env else "No .env file found; using environment variables.")
    check_ffmpeg()

    out_dir = POSTS / folder_name(job)
    if args.offline:
        out_dir = BUILD / "offline-preview" / folder_name(job)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Producing {job['type']} #{job.get('bank_id')} -> {out_dir}")

    if job["type"] == "reel":
        media, cover = make_reel(job, out_dir, args.offline)
    elif job["type"] == "carousel":
        media, cover = make_carousel(job, out_dir)
    else:
        sys.exit("type must be reel or carousel")

    post = {
        "bank_id": job.get("bank_id"),
        "type": job["type"],
        "publish_at": job.get("publish_at"),
        "media": media,
        "share_to_feed": True,
        "draft": True,
        "caption": job["caption"],
    }
    if cover:
        post["cover"] = cover
    (out_dir / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Done. Review the files in {out_dir}. Then run:  python production/make_post.py --approve \"{out_dir}\"")


if __name__ == "__main__":
    main()
