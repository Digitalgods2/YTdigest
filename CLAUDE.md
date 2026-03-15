# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YT Digest is a single-module Python application that monitors a YouTube channel via RSS, filters videos by type/duration, fetches transcripts, sends them to Google Gemini for top-5 highlights analysis, and stores results in SQLite. It runs as a scheduled task via OpenClaw Desktop (Clawdbot).

## Running

```bash
python yt_digest.py
```

On first run, the script self-installs to `%APPDATA%\YTDigest\`, auto-installs pip dependencies, and interactively prompts for YouTube channel ID and Gemini API key (stored in `config.ini`).

There are no tests or build steps. No linting configuration exists.

## Architecture

**Two files compose the entire application:**

- `yt_digest.py` (main app, ~900 lines) — single-file pipeline: dependency check → config load → DB init → RSS fetch → video filter → transcript fetch → Gemini analysis → DB store → log rotate
- `generate_ytdigest_pdf.py` — generates the PDF installation guide; not part of the runtime pipeline

**Execution flow in `yt_digest.py`:**

1. `check_dependencies()` — auto-installs missing pip packages (with PEP 668 fallback for Linux)
2. `load_config()` — reads `config.ini` from AppData; interactive setup on first run
3. `init_db()` — creates/migrates SQLite schema (`processed_videos` table)
4. `acquire_lock()` — PID-based instance lock to prevent overlapping runs
5. `get_recent_videos()` — RSS feed fetch (last 3 days), with yt-dlp fallback if RSS is blocked
6. `classify_video()` — multi-step filter: thumbnail pattern → URL pattern → HTML duration meta tag → title-based members-only detection
7. For each eligible video (≥30 min, not a Short, not members-only, not already in DB):
   - Enforce 10-minute rate limit (persistent via `last_api_call.txt`)
   - `fetch_transcript()` → `analyze_with_gemini()` → insert into SQLite
8. Log rotation (last 500 lines kept)

**Runtime files** (all in `%APPDATA%\YTDigest\`):
- `config.ini` — API keys and settings
- `ytdigest.db` — SQLite database (deduplication by `video_id` primary key)
- `ytdigest.log` — timestamped execution log
- `last_api_call.txt` — Unix timestamp for rate limiting

## Key Design Decisions

- **Rate limiting**: 10-minute minimum between API calls, persisted to disk. Each video requires 2 rate-limited calls (transcript + Gemini), so effective per-video time is 20+ minutes.
- **Video filtering pipeline**: Shorts detected by thumbnail URL pattern (`hq2.jpg`), URL path (`/shorts/`), or duration ≤60s. Members-only detected by title patterns (`[member access]`, `[members only]`). Videos under 30 minutes are skipped.
- **Transcript retry**: Videos without transcripts are marked `pending_transcript` and retried automatically (up to 9 attempts over ~48 hours at 6-hour cron intervals). After exhausting retries, status flips to `no_transcript`.
- **Three statuses**: `done` (fully processed), `pending_transcript` (retrying), `no_transcript` (gave up — use `--summarize` for manual import).
- **Manual summary**: `python yt_digest.py --summarize VIDEO_ID transcript.txt` imports an external transcript (e.g. from Whisper), runs Gemini on it, and marks the video `done`.
- **Schema migration**: `init_db()` auto-adds missing columns to existing tables.

## Dependencies

Defined in `requirements_ytdigest.txt`: `feedparser`, `requests`, `youtube-transcript-api`, `google-genai`.
