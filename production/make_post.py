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
# Paid assets (voice, AI images) are kept here and committed, so re-renders never pay twice.
CACHE = HERE / "cache"
W, H = brand.REEL_SIZE
FPS = brand.FPS
HOOK_SECONDS = 3.0
END_CARD_SECONDS = 1.4
XFADE = 0.5  # seconds of cross-fade between scenes


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


def _plain(word: str) -> str:
    """Arabic word without diacritics, tatweel or punctuation, for matching."""
    import re
    word = re.sub(r"[\u064B-\u0652\u0670\u0640]", "", word)
    word = re.sub(r"[^\w]", "", word)
    return word.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")


def scene_starts(scenes, words, main_len):
    """Start time of each scene: on its "at" phrase if given, else evenly spaced."""
    n = len(scenes)
    starts = [main_len * i / n for i in range(n)]
    plain = [_plain(w) for w, _, _ in words]
    pos = 0
    for i, scene in enumerate(scenes):
        phrase = [_plain(w) for w in scene.get("at", "").split() if _plain(w)]
        if i == 0:
            starts[0] = 0.0
            continue
        if not phrase:
            continue
        for k in range(pos, len(plain) - len(phrase) + 1):
            if plain[k:k + len(phrase)] == phrase:
                starts[i] = max(words[k][1] - 0.15, starts[i - 1] + 1.0)
                pos = k + 1
                break
        else:
            print(f"  warning: scene {i + 1} phrase not found: {scene['at']}")
    for i in range(1, n):  # keep order and at least 1 s per scene
        starts[i] = max(starts[i], starts[i - 1] + 1.0)
    return starts


# --- reel ----------------------------------------------------------------------------

def make_reel(job: dict, out_dir: Path, offline: bool):
    work = BUILD / job["slug"]
    work.mkdir(parents=True, exist_ok=True)
    paid = work if offline else CACHE / job["slug"]
    paid.mkdir(parents=True, exist_ok=True)

    # 1. Voice: our own recording(s) if the job lists them, else ElevenLabs text-to-speech
    voice = paid / "voice.mp3"
    words_file = paid / "words.json"
    recorded = [ROOT / f for f in job.get("voice_files", [])]
    if recorded:
        gap = float(job.get("voice_gap", 0.6))
        parts = []
        for k, f in enumerate(recorded):
            if k:
                parts += ["-f", "lavfi", "-t", f"{gap}", "-i", "anullsrc=r=44100:cl=mono"]
            parts += ["-i", str(f)]
        n_in = len(recorded) * 2 - 1
        mix = "".join(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono[a{k}];" for k in range(n_in))
        mix += "".join(f"[a{k}]" for k in range(n_in)) + f"concat=n={n_in}:v=0:a=1[out]"
        run(["ffmpeg", "-y", *parts, "-filter_complex", mix, "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(voice)])
        if offline:
            words = fake_words(job["voiceover"])
            scale = duration(voice) / (words[-1][2] + 0.4)
            words = [(w, a * scale, b * scale) for w, a, b in words]
        elif words_file.exists():
            words = json.loads(words_file.read_text(encoding="utf-8"))
            print("  voice: recorded, reusing cached timings")
        else:
            print("  voice: recorded, aligning words (ElevenLabs)...")
            words = services.align_words(voice, job["voiceover"])
            words_file.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    elif offline:
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
        img_path = paid / f"scene{i + 1}.jpg"
        if offline:
            graphics.placeholder_scene(i, scene["image_prompt"]).save(img_path)
        elif img_path.exists():
            print(f"  image {i + 1}: reusing cached image")
        else:
            print(f"  image {i + 1}/{len(scenes)}: OpenAI...")
            services.generate_image(scene["image_prompt"], img_path)
        images.append(img_path)

    # 3. Scene clips with a smooth slow zoom (alternating in / out).
    # A scene can start on a phrase of the voice-over ("at"); otherwise scenes share the time equally.
    # Clips overlap by XFADE seconds so each image melts into the next (no black flash).
    main_len = voice_len + 0.5
    n = len(images)
    starts = scene_starts(scenes, words, main_len)
    lengths = [((starts[i + 1] if i + 1 < n else main_len) - starts[i]) + (XFADE if i + 1 < n else 0)
               for i in range(n)]
    clips, clip_frames = [], []
    for i, img in enumerate(images):
        clip = work / f"clip{i + 1}.mp4"
        frames = max(int(round(lengths[i] * FPS)), 2)
        # zoom computed from the frame number, so it moves evenly without jitter
        zoom = (f"1+0.10*on/{frames}" if i % 2 == 0 else f"1.10-0.10*on/{frames}")
        vf = (f"crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=2160:3840,"
              f"zoompan=z='{zoom}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
              f"format=yuv420p")
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(img), "-vf", vf,
             "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-r", str(FPS), str(clip)])
        clips.append(clip)
        clip_frames.append(frames)

    # 4. End card clip
    end_png = work / "endcard.png"
    graphics.end_card(job.get("end_text", "احفظيها لوقت الحاجة")).save(end_png)
    end_clip = work / "endcard.mp4"
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(end_png), "-vf", "format=yuv420p",
         "-t", f"{END_CARD_SECONDS + XFADE}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-r", str(FPS), str(end_clip)])

    # 5. Join clips with cross-fades
    parts = clips + [end_clip]
    inputs, chain = [], []
    for p in parts:
        inputs += ["-i", str(p)]
    offset, last, acc = 0.0, "[0:v]", clip_frames[0] / FPS
    for k in range(1, len(parts)):
        offset = acc - XFADE
        label = f"[x{k}]"
        chain.append(f"{last}[{k}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}{label}")
        last = label
        if k < n:
            acc = offset + clip_frames[k] / FPS
    base = work / "base.mp4"
    run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", last,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), str(base)])
    main_len = acc
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
            img = graphics.slide_cover(s["title"], s.get("subtitle", ""), job.get("series") or job.get("pillar", ""))
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


# --- comic (funny mention posts) --------------------------------------------------------

def make_comic(job: dict, out_dir: Path, offline: bool):
    """One cartoon per panel: 1 panel = image post, 2-10 panels = carousel."""
    paid = BUILD / job["slug"] if offline else CACHE / job["slug"]
    paid.mkdir(parents=True, exist_ok=True)
    style = f"{brand.COMIC_CHARACTER} {brand.COMIC_LIMITS}"
    files = []
    for i, panel in enumerate(job["panels"]):
        pic_path = paid / f"panel{i + 1}.jpg"
        if offline:
            graphics.placeholder_scene(i, "").save(pic_path, quality=90)
        elif not pic_path.exists():
            print(f"  image {i + 1}: generating")
            brief = (f"Create a funny, original cartoon that makes mothers laugh and tag a friend. "
                     f"The joke (written above the picture by us): «{panel['text']}». "
                     f"Situation: {panel['idea']}. "
                     "You choose the scene, composition, expressions and the funny details.")
            services.generate_image(brief, pic_path, style=style)
        else:
            print(f"  image {i + 1}: cached")
        name = f"{i + 1:02d}.jpg"
        graphics.comic_panel(Image.open(pic_path), panel["text"]).save(out_dir / name, quality=92)
        files.append(name)
    if not 1 <= len(files) <= 10:
        raise ValueError("A comic post needs 1 to 10 panels.")
    return files, None


# --- main --------------------------------------------------------------------------------

def approve(folder: Path, at: str = None):
    post_file = folder / "post.json"
    post = json.loads(post_file.read_text(encoding="utf-8"))
    if at:
        dt.datetime.fromisoformat(at)  # validates the format
        post["publish_at"] = at
    if not post.get("publish_at"):
        sys.exit("This post has no publish time. Use --at 2026-11-22T13:00:00+03:00")
    post["draft"] = False
    post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    slug = folder.name.split("-", 4)[-1] if not folder.name.startswith("_review-") else folder.name[len("_review-"):]
    target = POSTS / f"{dt.datetime.fromisoformat(post['publish_at']):%Y-%m-%d-%H%M}-{slug}"
    if target != folder:
        folder.rename(target)
    print(f"Approved: {target.name} will publish at {post['publish_at']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("job", nargs="?", help="job JSON file")
    parser.add_argument("--offline", action="store_true", help="free layout test: no ElevenLabs/OpenAI calls")
    parser.add_argument("--approve", metavar="POST_FOLDER", help="mark a reviewed post ready to publish")
    parser.add_argument("--at", help="publish time for --approve, e.g. 2026-11-22T13:00:00+03:00")
    args = parser.parse_args()

    if args.approve:
        return approve(Path(args.approve), args.at)
    if not args.job:
        parser.error("give a job file or --approve")

    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    if not args.offline and job["type"] in ("reel", "comic"):
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
    elif job["type"] == "comic":
        media, cover = make_comic(job, out_dir, args.offline)
    else:
        sys.exit("type must be reel, carousel or comic")

    post = {
        "bank_id": job.get("bank_id"),
        "type": ("image" if len(media) == 1 else "carousel") if job["type"] == "comic" else job["type"],
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
