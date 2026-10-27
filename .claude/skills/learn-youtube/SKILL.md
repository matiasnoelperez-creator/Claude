---
name: learn-youtube
description: Watch a YouTube video (or Short) by pulling its transcript, key frames and metadata, then write a content teardown or learning notes and add what it learned to a running knowledge file. Use when the user shares a YouTube link and wants it analyzed, broken down, studied for a brand or creator, or "learned from".
argument-hint: <youtube-url> [teardown|learn] [knowledge-file-name]
---

# Learn from a YouTube video

Claude cannot play video, so this skill turns the video into things it can read:
the transcript (what is said), stills (what is shown) and metadata (how it performed).
The "learning" lives in markdown files under `knowledge/` that future sessions read.

## Arguments

- `$1` URL. Required. Ask for it if missing.
- `$2` mode. `teardown` (default) studies the video as content: hook, pacing, edit, voice, CTA.
  `learn` studies it for the ideas: claims, frameworks, steps, things to try.
- `$3` knowledge file name, such as `tracksmith`, `running-brands` or `claude-code`.
  Default to the channel name in kebab case.

## Steps

1. **Fetch.** From the repo root run:
   ```bash
   python3 .claude/skills/learn-youtube/scripts/fetch.py "<url>"
   ```
   It prints JSON with the output folder, transcript path and frame paths.
   Add `--no-frames` in `learn` mode when visuals clearly do not matter (podcasts, talking heads).
   If it fails with a network or 403 error, tell the user the host is blocked or YouTube refused
   the request. Do not invent content. Offer to work from a pasted transcript instead.

2. **Read everything.** Read `meta.json` and `transcript.md` in full. Read every frame image
   with the Read tool. Frames named `t0000s` to `t0003s` are the hook, so study them closely.
   If there is no transcript, say so and rely on frames and description.

3. **Write notes** to `<dir>/notes.md` using the template for the mode in
   [templates.md](templates.md). Cite timestamps like `[01:24]` for every claim
   about the video so the user can check it.

4. **Update the knowledge file** `knowledge/<name>.md`. Create it from the knowledge
   template if it does not exist. Merge, do not just append: strengthen patterns that repeat
   across videos, add new ones, and log the video in the Sources table. This file is
   what makes later videos and later copy better.

5. **Reply** with a short summary: the three most useful takeaways and the paths written.

## Writing rules

- Plain, specific language. No em dashes. Avoid the "it's not X, it's Y" construction and
  other filler phrasing.
- Separate what the video shows from your opinion. Label opinions as such.
- Numbers come only from `meta.json`. Never estimate views, retention or engagement.
- When a brand or client is named, judge the video against that brand's voice and audience,
  and phrase recommendations in a way that brand could actually use.
