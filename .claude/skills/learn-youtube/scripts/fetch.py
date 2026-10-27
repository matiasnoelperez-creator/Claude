#!/usr/bin/env python3
"""Turn a YouTube (or other yt-dlp supported) video into files Claude can read.

Writes to <out>/<video-id>/:
  meta.json       trimmed metadata (title, channel, stats, chapters, tags)
  transcript.md   timestamped, de-duplicated transcript
  frames/         stills: one per second for the hook, then evenly spaced

Usage:
  python3 fetch.py <url> [--out knowledge/youtube] [--max-frames 20]
                         [--hook-seconds 3] [--no-frames] [--keep-video]
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

META_KEYS = [
    "id", "title", "channel", "uploader", "channel_follower_count",
    "upload_date", "duration", "view_count", "like_count", "comment_count",
    "description", "tags", "categories", "chapters", "webpage_url",
]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def ytdlp():
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        print("Installing yt-dlp...", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yt-dlp"], check=True)
    return [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-playlist"]


def ts(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_vtt(path):
    """Return [(start_seconds, text)] with rolling auto-caption repeats removed."""
    cue_re = re.compile(r"(\d+):(\d{2}):(\d{2})\.\d+\s+-->")
    lines, start, seen = [], None, set()
    with open(path, encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            m = cue_re.match(raw)
            if m:
                h, mi, s = map(int, m.groups())
                start = h * 3600 + mi * 60 + s
                continue
            if not raw or start is None or raw.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
                continue
            text = re.sub(r"<[^>]+>", "", raw).strip()
            if text and text not in seen:
                seen.add(text)
                lines.append((start, text))
    return lines


def write_transcript(lines, path, chunk=15):
    """Group lines into ~15s paragraphs so the transcript stays readable."""
    out, para, para_start = [], [], None
    for start, text in lines:
        if para_start is None:
            para_start = start
        if start - para_start >= chunk and para:
            out.append(f"[{ts(para_start)}] {' '.join(para)}")
            para, para_start = [], start
        para.append(text)
    if para:
        out.append(f"[{ts(para_start)}] {' '.join(para)}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(out) + "\n")
    return len(out)


def frame_times(duration, max_frames, hook_seconds):
    hook = [float(t) for t in range(0, min(hook_seconds, int(duration)) + 1)]
    rest = max_frames - len(hook)
    if rest <= 0 or duration <= hook_seconds + 1:
        return hook
    step = (duration - hook_seconds) / (rest + 1)
    return hook + [round(hook_seconds + step * (i + 1), 1) for i in range(rest)]


def extract_frames(video, duration, frames_dir, max_frames, hook_seconds):
    os.makedirs(frames_dir, exist_ok=True)
    written = []
    for t in frame_times(duration, max_frames, hook_seconds):
        name = os.path.join(frames_dir, f"t{int(t):04d}s.jpg")
        r = run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", video,
                 "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", name])
        if r.returncode == 0 and os.path.exists(name):
            written.append(name)
    return written


def main():
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--out", default="knowledge/youtube")
    p.add_argument("--max-frames", type=int, default=20)
    p.add_argument("--hook-seconds", type=int, default=3)
    p.add_argument("--no-frames", action="store_true")
    p.add_argument("--keep-video", action="store_true")
    a = p.parse_args()

    base = ytdlp()
    r = run(base + ["--dump-single-json", "--skip-download", a.url])
    if r.returncode != 0:
        sys.exit(f"Could not read video metadata. yt-dlp said:\n{r.stderr.strip()}")
    full = json.loads(r.stdout)
    meta = {k: full.get(k) for k in META_KEYS if full.get(k) is not None}

    vid_dir = os.path.join(a.out, meta["id"])
    os.makedirs(vid_dir, exist_ok=True)
    with open(os.path.join(vid_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # Prefer human captions, fall back to auto-generated.
    run(base + ["--skip-download", "--write-subs", "--write-auto-subs",
                "--sub-langs", "en.*,en", "--sub-format", "vtt",
                "-o", os.path.join(vid_dir, "subs.%(ext)s"), a.url])
    vtts = sorted(glob.glob(os.path.join(vid_dir, "subs*.vtt")), key=lambda x: ("orig" in x, len(x)))
    paragraphs = 0
    if vtts:
        paragraphs = write_transcript(parse_vtt(vtts[0]), os.path.join(vid_dir, "transcript.md"))
        for v in vtts:
            os.remove(v)

    frames = []
    if not a.no_frames:
        if not shutil.which("ffmpeg"):
            print("ffmpeg not found, skipping frames.", file=sys.stderr)
        else:
            video = os.path.join(vid_dir, "video.mp4")
            run(base + ["-f", "bv*[height<=480]+ba/b[height<=480]/worst",
                        "--merge-output-format", "mp4", "-o", video, a.url])
            if os.path.exists(video):
                frames = extract_frames(video, meta.get("duration") or 0,
                                        os.path.join(vid_dir, "frames"),
                                        a.max_frames, a.hook_seconds)
                if not a.keep_video:
                    os.remove(video)

    print(json.dumps({
        "dir": vid_dir,
        "title": meta.get("title"),
        "channel": meta.get("channel") or meta.get("uploader"),
        "duration": meta.get("duration"),
        "transcript": os.path.join(vid_dir, "transcript.md") if paragraphs else None,
        "frames": frames,
    }, indent=2))


if __name__ == "__main__":
    main()
