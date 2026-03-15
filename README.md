# YT Digest

**YouTube Transcript Analyzer** — Automated highlights from your favorite channels.

YT Digest is a Python script that monitors a YouTube channel, fetches transcripts from long-form videos, and sends them to Google Gemini for top-5 highlights analysis. Everything is stored in a local SQLite database for easy retrieval.

## Features

- **RSS Feed Monitoring** — Polls a YouTube channel's RSS feed for recent videos
- **Smart Video Filtering** — Skips Shorts, clips under 30 min, and members-only videos; no upper duration limit
- **Self-Installing** — On first run, copies itself into `%APPDATA%\YTDigest` so everything lives in one place
- **Transcript Retrieval** — Fetches auto-generated or manual transcripts via YouTube's API
- **AI-Powered Highlights** — Sends transcripts to Google Gemini 2.5 Flash for top-5 highlights
- **SQLite Storage** — Stores titles, dates, transcripts, and summaries permanently
- **Rate Limiting** — 10-minute minimum between API calls, tracked persistently on disk
- **3-Day Lookback** — On first run (or after outage), catches up on recent videos chronologically
- **Auto-Dependency Check** — Verifies and auto-installs pip packages on startup
- **External Config** — All settings in `config.ini` (no hardcoded API keys)

## Architecture

```
OpenClaw (Cron) → yt_digest.py
                    ├── YouTube RSS Feed
                    ├── Video Filter (Shorts / Duration)
                    ├── YouTube Transcript API
                    ├── Google Gemini 2.5 Flash
                    └── SQLite Database
```

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/Digitalgods2/YTdigest.git
```

### 2. Run it

```bash
cd YTdigest
python yt_digest.py
```

That's it. The script handles everything automatically:

1. **Installs dependencies** — auto-detects missing pip packages and installs them
2. **Copies itself to AppData** — installs `yt_digest.py` and `requirements_ytdigest.txt` into `%APPDATA%\YTDigest\`
3. **Prompts for setup** — asks for your YouTube Channel ID and Gemini API key, saves to `config.ini`
4. **Starts processing** — fetches videos, transcripts, and generates highlights

After the first run, everything lives in `%APPDATA%\YTDigest\` and the clone folder can be deleted.

**Finding a Channel ID:**
```bash
yt-dlp --print channel_id --playlist-items 1 "https://www.youtube.com/@ChannelHandle"
```

**Getting a Gemini API key:** Sign up free at [Google AI Studio](https://aistudio.google.com)

### 3. Schedule (optional)

Set up as a scheduled task in OpenClaw (Clawdbot) with cron: `*/15 6-18 * * *`

```
Run the command: python "%APPDATA%\YTDigest\yt_digest.py"
```

## File Layout

```
%APPDATA%\YTDigest\
├── yt_digest.py              # Main script
├── requirements_ytdigest.txt # Dependencies
├── config.ini                # API keys & settings (auto-created)
├── ytdigest.db               # SQLite database
├── ytdigest.log              # Execution log
└── last_api_call.txt         # Rate limiter state
```

## Database Schema

| Column | Type | Description |
|---|---|---|
| `video_id` | TEXT (PK) | YouTube video ID |
| `title` | TEXT | Video title |
| `published` | DATETIME | Original publish date (ISO 8601) |
| `processed_at` | DATETIME | When YT Digest processed it |
| `summary` | TEXT | Gemini's top 5 highlights |
| `transcript` | TEXT | Full transcript with timestamps |

## Video Filtering

Videos are classified through a multi-step pipeline:

1. **Thumbnail check** — `hq2.jpg` pattern indicates a Short
2. **URL check** — `/shorts/` in the link
3. **Duration check** — Fetched from video page meta tag (`PT1H30M45S` format)

| Result | Criteria |
|---|---|
| Skip | Shorts (any detection method) |
| Skip | Under 30 minutes |
| Skip | Members-only (title contains `[member access]` or `[members only]`) |
| Process | 30 minutes and up (no upper limit) |

## Dependencies

| Package | Min Version | Purpose |
|---|---|---|
| `feedparser` | 6.0.0 | RSS feed parsing |
| `requests` | 2.25.0 | HTTP requests for duration detection |
| `youtube-transcript-api` | 1.2.0 | Transcript fetching |
| `google-genai` | 1.0.0 | Gemini API SDK |

## Documentation

See [YT_Digest_Installation_Guide_v3.pdf](YT_Digest_Installation_Guide_v3.pdf) for the full installation and reference guide, including architecture diagrams, OpenClaw scheduled task setup, and troubleshooting.

## License

MIT
