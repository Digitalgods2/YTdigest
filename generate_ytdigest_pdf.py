"""Generate the YT Digest Installation & Reference Guide PDF (v3)."""

import base64
import io
import tempfile
import urllib.request
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from datetime import datetime

OUTPUT = "YT_Digest_Installation_Guide_v3.pdf"

doc = SimpleDocTemplate(
    OUTPUT, pagesize=letter,
    leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    topMargin=0.75 * inch, bottomMargin=0.75 * inch,
)

styles = getSampleStyleSheet()

# Custom styles
styles.add(ParagraphStyle(
    "DocTitle", parent=styles["Title"], fontSize=22,
    textColor=HexColor("#1a1a2e"), spaceAfter=6,
))
styles.add(ParagraphStyle(
    "DocSubtitle", parent=styles["Normal"], fontSize=12,
    textColor=HexColor("#555555"), alignment=TA_CENTER, spaceAfter=20,
))
styles.add(ParagraphStyle(
    "SectionHead", parent=styles["Heading1"], fontSize=16,
    textColor=HexColor("#0f3460"), spaceBefore=18, spaceAfter=8,
))
styles.add(ParagraphStyle(
    "SubHead", parent=styles["Heading2"], fontSize=13,
    textColor=HexColor("#16213e"), spaceBefore=12, spaceAfter=6,
))
styles.add(ParagraphStyle(
    "Body", parent=styles["Normal"], fontSize=10,
    leading=14, spaceAfter=6,
))
styles.add(ParagraphStyle(
    "CodeBlock", parent=styles["Normal"], fontName="Courier", fontSize=9,
    leading=12, backColor=HexColor("#f0f0f0"), leftIndent=18,
    rightIndent=18, spaceAfter=8, spaceBefore=4,
))
styles.add(ParagraphStyle(
    "BulletItem", parent=styles["Normal"], fontSize=10,
    leading=14, leftIndent=24, bulletIndent=12, spaceAfter=4,
))
styles.add(ParagraphStyle(
    "Note", parent=styles["Normal"], fontSize=9,
    leading=12, textColor=HexColor("#c0392b"), leftIndent=18,
    spaceBefore=4, spaceAfter=8,
))
styles.add(ParagraphStyle(
    "TableCell", parent=styles["Normal"], fontSize=9, leading=11,
))
styles.add(ParagraphStyle(
    "TableCellCode", parent=styles["Normal"], fontName="Courier",
    fontSize=8, leading=11,
))
styles.add(ParagraphStyle(
    "DiagramCaption", parent=styles["Normal"], fontSize=9,
    textColor=HexColor("#555555"), alignment=TA_CENTER,
    spaceBefore=4, spaceAfter=12,
))

story = []
S = Spacer
HR = lambda: HRFlowable(width="100%", thickness=1, color=HexColor("#cccccc"),
                         spaceBefore=6, spaceAfter=10)

TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0f3460")),
    ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
    ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 6),
])


def title(text):
    story.append(Paragraph(text, styles["DocTitle"]))

def subtitle(text):
    story.append(Paragraph(text, styles["DocSubtitle"]))

def section(text):
    story.append(Paragraph(text, styles["SectionHead"]))

def sub(text):
    story.append(Paragraph(text, styles["SubHead"]))

def body(text):
    story.append(Paragraph(text, styles["Body"]))

def code(text):
    story.append(Paragraph(text.replace("\n", "<br/>"), styles["CodeBlock"]))

def bullet(text):
    story.append(Paragraph(f"\u2022 {text}", styles["BulletItem"]))

def note(text):
    story.append(Paragraph(f"<b>NOTE:</b> {text}", styles["Note"]))

def spacer(h=0.15):
    story.append(S(1, h * inch))

def make_table(headers, rows, col_widths):
    data = [[Paragraph(f"<b>{h}</b>", styles["TableCell"]) for h in headers]]
    for row in rows:
        data.append([
            Paragraph(cell, styles["TableCellCode"] if i == 0 else styles["TableCell"])
            for i, cell in enumerate(row)
        ])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TABLE_STYLE)
    story.append(t)


def render_mermaid(mermaid_src: str, width: float = 6.0 * inch,
                   caption: str = "") -> list:
    """Render a Mermaid diagram via mermaid.ink and return flowables."""
    encoded = base64.urlsafe_b64encode(mermaid_src.encode("utf-8")).decode("utf-8")
    url = f"https://mermaid.ink/img/{encoded}?bgColor=white"
    flowables = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            img_data = resp.read()
        img_buf = io.BytesIO(img_data)
        img = Image(img_buf, width=width, height=None)
        # Maintain aspect ratio, cap height to fit on page
        max_height = 7.5 * inch
        iw, ih = img.imageWidth, img.imageHeight
        if iw and ih:
            natural_height = width * (ih / iw)
            if natural_height > max_height:
                # Scale down width proportionally to fit
                scale = max_height / natural_height
                img.drawWidth = width * scale
                img.drawHeight = max_height
            else:
                img.drawHeight = natural_height
        flowables.append(img)
        if caption:
            flowables.append(Paragraph(caption, styles["DiagramCaption"]))
    except Exception as e:
        # Fallback: show the Mermaid source as code
        print(f"Warning: Could not render Mermaid diagram ({e}). Using text fallback.")
        flowables.append(Paragraph(
            mermaid_src.replace("\n", "<br/>").replace(" ", "&nbsp;"),
            styles["CodeBlock"],
        ))
        if caption:
            flowables.append(Paragraph(caption, styles["DiagramCaption"]))
    return flowables


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 1: TITLE
# ═══════════════════════════════════════════════════════════════════════════
spacer(1.5)
title("YT Digest")
subtitle("YouTube Transcript Analyzer &mdash; Installation &amp; Reference Guide")
spacer(0.3)
story.append(HR())
body(f"Document generated: {datetime.now().strftime('%B %d, %Y')}")
body("Version: 4.0")
body("Platform: Windows 11 / Python 3.13+")
body("Execution: OpenClaw (Clawdbot) &mdash; Scheduled Task (Cron)")
spacer(0.3)
story.append(HR())

body("This document provides complete instructions for installing, configuring, "
     "and running the YT Digest program via OpenClaw (Clawdbot). It covers "
     "file placement, dependencies, external configuration, database schema, "
     "video filtering, rate limiting, scheduled task setup, and troubleshooting.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS
# ═══════════════════════════════════════════════════════════════════════════
section("Table of Contents")
story.append(HR())
toc_items = [
    "1. Overview",
    "2. Architecture Diagram",
    "3. Prerequisites",
    "4. File Locations &amp; Placement",
    "5. Dependency Installation",
    "6. Configuration (config.ini)",
    "7. Video Filtering &amp; Classification",
    "8. Rate Limiting",
    "9. Database Schema &amp; Storage",
    "10. Program Execution Flow",
    "11. Transcript Retry &amp; Manual Summary",
    "12. OpenClaw Scheduled Task Setup",
    "13. Log File &amp; Housekeeping",
    "14. Troubleshooting",
    "15. Quick Reference Card",
]
for item in toc_items:
    body(item)
spacer(0.5)

# ═══════════════════════════════════════════════════════════════════════════
# 1. OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════
section("1. Overview")
story.append(HR())
body("YT Digest is a Python script designed to run as a background scheduled task "
     "via OpenClaw (Clawdbot). Each execution performs the following steps:")
spacer(0.1)
bullet("Fetches the YouTube channel's RSS feed and identifies recent videos")
bullet("Filters out Shorts, videos under 30 minutes, and members-only videos")
bullet("On first run, looks back 3 days and processes videos chronologically")
bullet("Checks if each video has already been processed (via SQLite lookup)")
bullet("Fetches transcripts from YouTube when available")
bullet("Retries videos without transcripts over 48 hours (9 attempts at 6-hour intervals)")
bullet("Enforces 10-minute rate limiting between API calls (tracked on disk)")
bullet("Sends transcripts to Google Gemini for top-5 highlights analysis")
bullet("Stores the title, dates, transcript, and summary in a SQLite database")
bullet("Supports manual transcript import via --summarize for videos with no auto-transcript")
spacer(0.1)
body("The script is idempotent &mdash; running it multiple times for the same video "
     "has no effect after the first successful processing. All configuration is "
     "externalized in a config.ini file under %APPDATA%.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 2. ARCHITECTURE DIAGRAM
# ═══════════════════════════════════════════════════════════════════════════
section("2. Architecture Diagram")
story.append(HR())
body("The following diagram shows the high-level system architecture and data flow:")
spacer(0.2)

arch_mermaid = """flowchart TB
    subgraph OpenClaw["OpenClaw Desktop (Scheduler)"]
        CRON["Cron Trigger<br/>*/15 6-18 * * *"]
    end

    subgraph Script["yt_digest.py"]
        DEP["Dependency Check"]
        CFG["Load config.ini"]
        RSS["Fetch RSS Feed"]
        FILT["Video Filter<br/>(Shorts / Duration)"]
        DEDUP["SQLite Dedup Check"]
        TRANS["Fetch Transcript"]
        RATE["Rate Limiter<br/>(10 min)"]
        GEMINI["Gemini Analysis<br/>(Top 5 Highlights)"]
        STORE["Store in SQLite"]
    end

    subgraph External["External Services"]
        YT_RSS["YouTube RSS"]
        YT_PAGE["YouTube Page<br/>(Duration Meta)"]
        YT_TRANS["YouTube<br/>Transcript API"]
        GEM_API["Google Gemini<br/>2.5 Flash"]
    end

    subgraph Storage["Local Storage (%APPDATA%)"]
        DB[("ytdigest.db<br/>SQLite")]
        LOG["ytdigest.log"]
        CONF["config.ini"]
        RATELIM["last_api_call.txt"]
    end

    CRON --> DEP --> CFG --> RSS
    RSS --> FILT --> DEDUP --> TRANS --> RATE --> GEMINI --> STORE
    RSS --> YT_RSS
    FILT --> YT_PAGE
    TRANS --> YT_TRANS
    GEMINI --> GEM_API
    CFG --> CONF
    DEDUP --> DB
    STORE --> DB
    STORE --> LOG
    RATE --> RATELIM
"""
story.extend(render_mermaid(arch_mermaid, width=6.5 * inch,
                            caption="Figure 1: YT Digest System Architecture"))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 3. PREREQUISITES
# ═══════════════════════════════════════════════════════════════════════════
section("3. Prerequisites")
story.append(HR())

sub("3.1 System Requirements")
bullet("Windows 10 or 11")
bullet("Python 3.10 or later (3.13 recommended) installed and on PATH")
bullet("pip (included with Python)")
bullet("Internet access (for YouTube RSS, transcript API, and Gemini API)")

sub("3.2 API Keys Required")
make_table(
    ["Service", "Key Type", "Where to Get"],
    [
        ["Google Gemini", "API Key", "Google AI Studio (aistudio.google.com)"],
        ["YouTube", "None required", "RSS feed + transcript API &mdash; no auth needed"],
    ],
    [1.5*inch, 1.5*inch, 3.5*inch],
)

sub("3.3 OpenClaw (Clawdbot)")
bullet("OpenClaw Desktop app must be installed")
bullet("The app must be <b>running</b> for scheduled tasks to fire")
bullet("On reboot, relaunch the Desktop app &mdash; tasks auto-resume")
bullet("Missed runs are caught up (most recent missed run only)")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 4. FILE LOCATIONS
# ═══════════════════════════════════════════════════════════════════════════
section("4. File Locations &amp; Placement")
story.append(HR())

body("All files must be in the correct locations for the system to function.")

sub("4.1 Application Directory")
body("All files &mdash; the script, requirements, configuration, database, and logs &mdash; "
     "live together under a single folder in %APPDATA%. This keeps the Desktop clean "
     "and works the same on every Windows machine regardless of username.")
spacer(0.1)
code("%APPDATA%\\YTDigest\\")
body("Which resolves to: C:\\Users\\&lt;USERNAME&gt;\\AppData\\Roaming\\YTDigest\\")

sub("4.2 File Inventory")
body("The directory is created automatically on first run. All files below are "
     "stored in %APPDATA%\\YTDigest\\:")
make_table(
    ["File", "Type", "Purpose"],
    [
        ["yt_digest.py",
         "Python script",
         "Main application script"],
        ["requirements_ytdigest.txt",
         "Text file",
         "pip dependency manifest (must be alongside yt_digest.py)"],
        ["config.ini",
         "INI file",
         "API keys, channel ID, model settings (auto-created on first run)"],
        ["ytdigest.db",
         "SQLite DB",
         "Processed videos, transcripts, summaries"],
        ["ytdigest.log",
         "Text file",
         "Timestamped execution log"],
        ["last_api_call.txt",
         "Text file",
         "Persistent rate-limit timestamp"],
    ],
    [2.2*inch, 1.2*inch, 3.1*inch],
)
spacer(0.1)
note("The requirements file MUST be in the same directory as yt_digest.py. "
     "The script looks for it relative to its own location for auto-install.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 5. DEPENDENCY INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════
section("5. Dependency Installation")
story.append(HR())

sub("5.1 Requirements File Contents")
body("File: requirements_ytdigest.txt")
code("feedparser&gt;=6.0.0\n"
     "requests&gt;=2.25.0\n"
     "youtube-transcript-api&gt;=1.2.0\n"
     "google-genai&gt;=1.0.0")

sub("5.2 Manual Installation")
body("Open a terminal and run:")
code("pip install -r %APPDATA%\\YTDigest\\requirements_ytdigest.txt")

sub("5.3 Automatic Dependency Check (Built-In)")
body("The script includes a comprehensive startup dependency checker that runs "
     "before any third-party imports. On each execution it:")
spacer(0.1)
bullet("Verifies each required package is importable")
bullet("Checks each package meets the minimum version requirement")
bullet("If any package is missing or outdated, attempts <b>auto-install</b> "
       "from requirements_ytdigest.txt using pip")
bullet("Re-verifies all packages after auto-install")
bullet("If auto-install fails, prints detailed error messages with exact "
       "pip commands and exits with code 1")
spacer(0.1)
note("The auto-install requires that requirements_ytdigest.txt is in the same "
     "directory as yt_digest.py. If the file is missing, auto-install is skipped "
     "and the script exits with instructions for manual installation.")

sub("5.4 Dependency Details")
make_table(
    ["Package", "Min Version", "Purpose"],
    [
        ["feedparser", "6.0.0",
         "Parses the YouTube channel RSS/Atom feed to discover recent videos"],
        ["requests", "2.25.0",
         "HTTP requests for fetching video page metadata (duration detection)"],
        ["youtube-transcript-api", "1.2.0",
         "Fetches auto-generated or manual transcripts from YouTube (no API key needed)"],
        ["google-genai", "1.0.0",
         "Google Gemini SDK for sending transcript to Gemini and receiving analysis"],
    ],
    [2*inch, 1*inch, 3.5*inch],
)

sub("5.5 Standard Library Dependencies (No Install Needed)")
body("These are included with Python and require no installation:")
bullet("<b>os, sys, time, re</b> &mdash; System operations and regex")
bullet("<b>sqlite3</b> &mdash; Database operations")
bullet("<b>subprocess</b> &mdash; Running pip for auto-install")
bullet("<b>configparser</b> &mdash; External config.ini parsing")
bullet("<b>importlib.metadata</b> &mdash; Package version checking")
bullet("<b>datetime</b> &mdash; Timestamps, date math, timezone handling")
bullet("<b>pathlib</b> &mdash; Cross-platform file path handling")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 6. CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
section("6. Configuration (config.ini)")
story.append(HR())

body("All user-configurable settings are stored in an external INI file, "
     "not hardcoded in the script. The config file is created automatically "
     "on first run with placeholder values.")

sub("6.1 Config File Location")
code("C:\\Users\\&lt;USERNAME&gt;\\AppData\\Roaming\\YTDigest\\config.ini")

sub("6.2 Config File Format")
code("[ytdigest]\n"
     "youtube_channel_id = REPLACE_WITH_CHANNEL_ID\n"
     "gemini_api_key = REPLACE_WITH_GEMINI_API_KEY\n"
     "gemini_model = gemini-2.5-flash\n"
     "db_retention_days =\n"
     "max_log_lines = 500")

sub("6.3 Settings Reference")
make_table(
    ["Setting", "Default", "Description"],
    [
        ["youtube_channel_id", "REPLACE_WITH_CHANNEL_ID",
         "YouTube channel ID (starts with UC, 24 chars). Must be set before first run."],
        ["gemini_api_key", "REPLACE_WITH_GEMINI_API_KEY",
         "Google Gemini API key from AI Studio. Must be set before first run."],
        ["gemini_model", "gemini-2.5-flash",
         "Gemini model ID. Use gemini-2.5-flash for best speed/cost balance."],
        ["db_retention_days", "(empty = forever)",
         "Days to keep DB records. Leave empty for permanent storage, or set a number (e.g. 365)."],
        ["max_log_lines", "500",
         "Log file trimmed to this many lines on each run."],
    ],
    [1.8*inch, 1.7*inch, 3*inch],
)

sub("6.4 Changing the YouTube Channel")
body("To monitor a different channel:")
bullet("Find the channel ID using: <b>yt-dlp --print channel_id --playlist-items 1 "
       "\"https://www.youtube.com/@ChannelHandle\"</b>")
bullet("Edit config.ini and replace the youtube_channel_id value")
bullet("The channel ID always starts with <b>UC</b> followed by 22 characters")

sub("6.5 Changing the Gemini Model")
body("Available models as of March 2026:")
bullet("<b>gemini-2.5-flash</b> &mdash; Fast, cost-effective (recommended)")
bullet("<b>gemini-2.5-flash-lite</b> &mdash; Even faster/cheaper for high volume")
bullet("<b>gemini-2.5-pro</b> &mdash; Higher quality analysis, slower, more expensive")
note("gemini-2.0-flash is being retired June 1, 2026. Do not use it.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 7. VIDEO FILTERING
# ═══════════════════════════════════════════════════════════════════════════
section("7. Video Filtering &amp; Classification")
story.append(HR())

body("Not every video on a channel is suitable for transcript analysis. "
     "YT Digest uses a multi-layered filtering pipeline to identify only "
     "long-form content (30 minutes and up).")

sub("7.1 Filter Pipeline")
body("Each video from the RSS feed is classified in this order:")
spacer(0.1)

filter_mermaid = """flowchart TD
    A["RSS Feed Entry"] --> M{"Title contains<br/>[member access] or<br/>[members only]?"}
    M -- Yes --> MEMBERS["SKIP: Members-Only"]
    M -- No --> B{"Thumbnail URL<br/>contains hq2.jpg?"}
    B -- Yes --> SHORT["SKIP: Short"]
    B -- No --> C{"Link URL<br/>contains /shorts/?"}
    C -- Yes --> SHORT
    C -- No --> D["Fetch Video Page<br/>(HTTP GET)"]
    D --> E{"Duration from<br/>meta tag?"}
    E -- "Not found" --> ELIGIBLE["ELIGIBLE<br/>(include to be safe)"]
    E -- Found --> F{"&le; 60 seconds?"}
    F -- Yes --> SHORT
    F -- No --> G{"&lt; 30 minutes?"}
    G -- Yes --> TOO_SHORT["SKIP: Too Short"]
    G -- No --> ELIGIBLE

    style SHORT fill:#ff6b6b,color:#fff
    style TOO_SHORT fill:#ffa94d,color:#fff
    style MEMBERS fill:#ffa94d,color:#fff
    style ELIGIBLE fill:#51cf66,color:#fff
"""
story.extend(render_mermaid(filter_mermaid, width=5.0 * inch,
                            caption="Figure 2: Video Classification Pipeline"))

sub("7.2 Classification Details")
make_table(
    ["Classification", "Criteria", "Action"],
    [
        ["members-only", "Title contains [member access] or [members only]",
         "Skipped &mdash; no accessible transcript"],
        ["short", "hq2.jpg thumbnail, /shorts/ URL, or duration &le; 60s",
         "Skipped &mdash; not suitable for transcript analysis"],
        ["too_short", "Duration &lt; 30 minutes (1800 seconds)",
         "Skipped &mdash; below minimum length threshold"],
        ["eligible", "Duration 30 min or longer, or duration unknown",
         "Processed &mdash; transcript fetched and analyzed"],
    ],
    [1.2*inch, 2.5*inch, 2.8*inch],
)
spacer(0.1)
body("Duration is extracted from the video page's HTML meta tag: "
     "<b>&lt;meta itemprop=\"duration\" content=\"PT1H30M45S\"&gt;</b> "
     "(ISO 8601 duration format).")

sub("7.3 Lookback Window")
body("On each run, the script checks the RSS feed for videos published in the "
     "last <b>3 days</b> (LOOKBACK_DAYS = 3). Videos are processed in "
     "chronological order (oldest first). This ensures that on first run "
     "or after an outage, recent videos are caught up.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 8. RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════
section("8. Rate Limiting")
story.append(HR())

body("To avoid hitting YouTube's API quotas, YT Digest enforces a "
     "<b>10-minute minimum interval</b> between transcript fetch calls. "
     "Gemini calls are not rate-limited (free tier allows 15 requests/minute).")

sub("8.1 How It Works")
bullet("After each transcript fetch, the current Unix timestamp is written to "
       "<b>last_api_call.txt</b>")
bullet("Before the next transcript fetch, the script reads this file and "
       "calculates elapsed time")
bullet("If less than 10 minutes have passed, the script <b>sleeps</b> for the "
       "remaining time")
bullet("The timestamp file persists across runs &mdash; rate limiting works "
       "even if the script is restarted")

sub("8.2 Rate Limit Timing")
make_table(
    ["Event", "Rate Limit Applied"],
    [
        ["Transcript fetch", "Yes &mdash; waits if &lt; 10 min since last call"],
        ["Gemini analysis", "No &mdash; Gemini free tier allows 15 req/min"],
        ["RSS feed fetch", "No &mdash; lightweight, no rate limit needed"],
        ["Video page fetch (duration)", "No &mdash; simple HTTP GET"],
    ],
    [2.5*inch, 4*inch],
)
spacer(0.1)
note("Each video requires one rate-limited call (transcript fetch) plus one "
     "un-limited call (Gemini). Effective per-video time is ~10 minutes when "
     "processing back-to-back.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 9. DATABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════
section("9. Database Schema &amp; Storage")
story.append(HR())

sub("9.1 Database File")
body("Location: C:\\Users\\&lt;USERNAME&gt;\\AppData\\Roaming\\YTDigest\\ytdigest.db")
body("Engine: SQLite 3 (built into Python, no external server required)")

sub("9.2 Table: processed_videos")
make_table(
    ["Column", "Type", "Description"],
    [
        ["video_id", "TEXT (PK)",
         "YouTube video ID (e.g., qdRrvIbvdRQ). Primary key &mdash; prevents duplicates."],
        ["title", "TEXT",
         "Video title as it appears on YouTube"],
        ["published", "DATETIME",
         "Original publish date from YouTube RSS feed (ISO 8601 format)"],
        ["processed_at", "DATETIME",
         "Timestamp when YT Digest processed this video (ISO 8601 format)"],
        ["status", "TEXT",
         "done, pending_transcript, or no_transcript (see section 9.3)"],
        ["summary", "TEXT",
         "Gemini's top 5 highlights analysis (full text stored in DB)"],
        ["transcript", "TEXT",
         "Full transcript with timestamps, e.g., [01:23] Hello world"],
        ["retry_count", "INTEGER",
         "Number of transcript fetch attempts (used for pending_transcript retries)"],
    ],
    [1.3*inch, 1*inch, 4.2*inch],
)
spacer(0.1)
note("Summaries are stored directly in the database &mdash; no separate "
     "summary files are written to disk. The <b>published</b> and "
     "<b>processed_at</b> columns use DATETIME type for proper date sorting "
     "and comparison.")

sub("9.3 Video Statuses")
body("Each video record has a status field that controls processing behavior:")
make_table(
    ["Status", "Meaning", "Behavior"],
    [
        ["done", "Transcript fetched and Gemini highlights generated",
         "Skipped on future runs"],
        ["pending_transcript", "No transcript available yet",
         "Retried automatically every 6 hours (up to 9 attempts over ~48 hours)"],
        ["no_transcript", "Gave up after 9 retry attempts",
         "Permanently skipped. Use --summarize to manually import a transcript."],
    ],
    [1.5*inch, 2*inch, 3*inch],
)

sub("9.4 Schema Migration")
body("The script includes automatic schema migration. If the database was created "
     "by an earlier version (before transcript/summary/status/retry_count columns "
     "were added), ALTER TABLE is run automatically. No manual intervention is needed.")

sub("9.5 Querying the Database")
body("You can inspect the database at any time using the sqlite3 CLI or any "
     "SQLite browser (e.g., DB Browser for SQLite):")
code("sqlite3 \"%APPDATA%\\YTDigest\\ytdigest.db\"")
spacer(0.1)
body("Useful queries:")
code("-- List all processed videos\n"
     "SELECT video_id, title, published, processed_at\n"
     "FROM processed_videos ORDER BY published DESC;\n\n"
     "-- Get the latest summary\n"
     "SELECT title, summary FROM processed_videos\n"
     "ORDER BY processed_at DESC LIMIT 1;\n\n"
     "-- Get a specific transcript\n"
     "SELECT transcript FROM processed_videos\n"
     "WHERE video_id = 'VIDEO_ID_HERE';\n\n"
     "-- Count total processed videos\n"
     "SELECT COUNT(*) FROM processed_videos;\n\n"
     "-- Videos processed in the last 7 days\n"
     "SELECT title, processed_at FROM processed_videos\n"
     "WHERE processed_at &gt;= datetime('now', '-7 days');\n\n"
     "-- Videos awaiting transcript\n"
     "SELECT title, retry_count FROM processed_videos\n"
     "WHERE status = 'pending_transcript';\n\n"
     "-- Videos that gave up (candidates for --summarize)\n"
     "SELECT video_id, title FROM processed_videos\n"
     "WHERE status = 'no_transcript';")

sub("9.6 Retention")
body("db_retention_days is set to empty (keep forever) by default. All records "
     "(transcripts, summaries, titles, dates) are kept permanently. To enable "
     "pruning, set db_retention_days in config.ini to the desired number of days.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 10. EXECUTION FLOW
# ═══════════════════════════════════════════════════════════════════════════
section("10. Program Execution Flow")
story.append(HR())

body("The following diagram shows the complete execution flow for each run:")
spacer(0.2)

flow_mermaid = """flowchart TD
    START(["Start"]) --> DEPS["Check Dependencies<br/>(auto-install if needed)"]
    DEPS --> CONFIG["Load config.ini"]
    CONFIG --> VALIDATE{"API key &<br/>Channel ID set?"}
    VALIDATE -- No --> EXIT_ERR["Exit with error"]
    VALIDATE -- Yes --> DB["Init SQLite DB"]
    DB --> RSS["Fetch RSS Feed<br/>(last 3 days)"]
    RSS --> FILTER["Filter & Classify Videos"]
    FILTER --> LOOP{"More eligible<br/>videos?"}
    LOOP -- No --> HOUSEKEEP["Prune DB / Rotate Log"]
    LOOP -- Yes --> DEDUP{"Already done<br/>or no_transcript?"}
    DEDUP -- Yes --> LOOP
    DEDUP -- No --> RATE1["Enforce Rate Limit"]
    RATE1 --> TRANSCRIPT["Fetch Transcript"]
    TRANSCRIPT --> AVAIL{"Transcript<br/>available?"}
    AVAIL -- No --> PENDING["Mark pending_transcript<br/>(retry_count + 1)"]
    PENDING --> MAXRETRY{"Retries<br/>&ge; 9?"}
    MAXRETRY -- Yes --> GIVEUP["Mark no_transcript"]
    MAXRETRY -- No --> LOOP
    AVAIL -- Yes --> RATE2["Enforce Rate Limit"]
    RATE2 --> GEMINI["Send to Gemini<br/>(Top 5 Highlights)"]
    GEMINI --> STORE["Store in SQLite<br/>(status = done)"]
    STORE --> LOOP
    GIVEUP --> LOOP
    HOUSEKEEP --> DONE(["Done"])

    style EXIT_ERR fill:#ff6b6b,color:#fff
    style DONE fill:#51cf66,color:#fff
    style START fill:#339af0,color:#fff
    style PENDING fill:#ffa94d,color:#fff
    style GIVEUP fill:#ff6b6b,color:#fff
"""
story.extend(render_mermaid(flow_mermaid, width=4.5 * inch,
                            caption="Figure 3: Complete Execution Flow"))

spacer(0.2)

sub("10.1 Exit Conditions (Normal)")
body("The script exits cleanly (code 0) in these cases:")
bullet("No eligible videos found in the lookback window")
bullet("All eligible videos already processed (status = done or no_transcript)")
bullet("Transcript not yet available &mdash; marked as pending_transcript for retry on next run")
bullet("Successful processing complete")

sub("10.2 Exit Conditions (Error)")
body("The script exits with code 1 in these cases:")
bullet("youtube_channel_id is still set to placeholder in config.ini")
bullet("gemini_api_key is still set to placeholder in config.ini")
bullet("Dependency check failed and auto-install failed")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 11. TRANSCRIPT RETRY & MANUAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
section("11. Transcript Retry &amp; Manual Summary")
story.append(HR())

sub("11.1 Automatic Retry (pending_transcript)")
body("YouTube can take up to 24 hours (or more) to generate auto-captions for a "
     "newly uploaded video. When a video is discovered but has no transcript, "
     "the script marks it as <b>pending_transcript</b> and retries on subsequent runs.")
spacer(0.1)
bullet("First run: video discovered, transcript fetch fails &rarr; status = pending_transcript, retry_count = 1")
bullet("Every 6 hours: cron runs again, retries pending_transcript videos")
bullet("After 9 attempts (~48 hours): status flips to <b>no_transcript</b> (gives up)")
spacer(0.1)
body("The retry_count column tracks how many attempts have been made. Videos with "
     "status = pending_transcript are retried automatically &mdash; no user action needed.")

sub("11.2 Manual Summary (--summarize)")
body("If a video ends up as <b>no_transcript</b> (or if you have your own transcript "
     "from Whisper or another tool), you can manually import it:")
spacer(0.1)
code("python yt_digest.py --summarize VIDEO_ID path\\to\\transcript.txt")
spacer(0.1)
body("This command:")
bullet("Reads the transcript from the specified text file")
bullet("Looks up the video's title and publish date from the existing DB record")
bullet("Sends the transcript to Gemini for top-5 highlights analysis")
bullet("Marks the video as <b>done</b> with the transcript and summary stored in the database")
spacer(0.1)
note("The --summarize command bypasses the instance lock and can be run at any time, "
     "even while a cron job is active. Rate limiting still applies to the Gemini call.")

sub("11.3 Example Workflow")
body("Typical lifecycle for a video without auto-captions:")
spacer(0.1)
bullet("Run 1 (00:00): Video discovered, no transcript &rarr; pending_transcript (1/9)")
bullet("Run 2 (06:00): Retry &rarr; still no transcript (2/9)")
bullet("Run 3 (12:00): Retry &rarr; transcript appears! &rarr; Gemini analysis &rarr; done")
spacer(0.1)
body("Or, if transcripts never appear:")
spacer(0.1)
bullet("Runs 1-9 over 48 hours: all fail &rarr; status flips to no_transcript")
bullet("User runs Whisper on the video and produces transcript.txt")
bullet("User runs: python yt_digest.py --summarize VIDEO_ID transcript.txt")
bullet("Video is now status = done with transcript and summary in the database")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 12. OPENCLAW SCHEDULED TASK
# ═══════════════════════════════════════════════════════════════════════════
section("12. OpenClaw Scheduled Task Setup")
story.append(HR())

sub("12.1 Overview")
body("The script is executed by OpenClaw (Clawdbot) as a scheduled task (cron job). "
     "OpenClaw has its own built-in scheduler &mdash; it does NOT use Windows Task "
     "Scheduler. The Desktop app must be running for tasks to fire.")

sub("12.2 Creating the Scheduled Task")
body("In OpenClaw Desktop:")
bullet("Open the Desktop app")
bullet("Navigate to the Schedule feature")
bullet("Create a new scheduled task named <b>\"yt-digest\"</b>")
bullet("Set the schedule to run every 6 hours")
bullet("Set the prompt/instruction to:")
spacer(0.1)
code("Run the command: python %APPDATA%\\YTDigest\\yt_digest.py")
spacer(0.1)
body("Alternatively, the task is stored on disk and can be edited directly:")
code("~/.claude/scheduled-tasks/yt-digest/SKILL.md")

sub("12.3 Recommended Cron Schedule")
body("Run every 6 hours to catch new videos and retry pending transcripts:")
code("0 */6 * * *")
spacer(0.1)
body("This means: at the top of the hour, every 6 hours (midnight, 6 AM, noon, 6 PM), "
     "every day. This schedule allows up to 9 retries over 48 hours for pending transcripts.")
spacer(0.1)
note("The script is idempotent. Once a video is processed, subsequent runs "
     "for the same video exit immediately with 'already processed'. There is "
     "no penalty for running it frequently.")

sub("12.4 What Happens on Reboot")
bullet("Scheduled tasks are <b>persistent</b> &mdash; stored on disk, survive restarts")
bullet("When the Desktop app starts, it auto-resumes all scheduled tasks")
bullet("It catches up the <b>most recent missed run</b> (checks last 7 days)")
bullet("Older missed runs are discarded (no queue of 50+ runs after long outage)")
bullet("A notification appears when a catch-up run starts")

sub("12.5 Requirements for Scheduled Tasks to Run")
bullet("OpenClaw Desktop app must be <b>running</b>")
bullet("Computer must be <b>awake</b> (not sleeping/hibernating)")
bullet("Consider enabling 'Keep computer awake' in OpenClaw Desktop settings")
bullet("Internet connection must be available")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 13. LOG FILE
# ═══════════════════════════════════════════════════════════════════════════
section("13. Log File &amp; Housekeeping")
story.append(HR())

sub("13.1 Log File")
body("Location: C:\\Users\\&lt;USERNAME&gt;\\AppData\\Roaming\\YTDigest\\ytdigest.log")
body("Format: [YYYY-MM-DD HH:MM:SS] message")
body("The log captures every action: RSS fetch, video classification, transcript "
     "status, rate limiting waits, Gemini calls, errors, and housekeeping. "
     "It is both printed to console and written to file.")
spacer(0.1)
body("Example log entries:")
code("[2026-03-12 09:15:00] ============================================================\n"
     "[2026-03-12 09:15:00] YT Digest run started.\n"
     "[2026-03-12 09:15:00] Fetching RSS feed for channel: UCZk3...\n"
     "[2026-03-12 09:15:01] Eligible videos: 2 (skipped 8 shorts, 3 too short, 0 members-only)\n"
     "[2026-03-12 09:15:01] Checking: \"Deep Dive into Transformers\" (abc123)\n"
     "[2026-03-12 09:15:01] Fetching transcript for video: abc123\n"
     "[2026-03-12 09:15:02] Transcript retrieved: 24523 characters\n"
     "[2026-03-12 09:15:02] Rate limit: waiting 8.3 minutes before next API call...\n"
     "[2026-03-12 09:23:22] Sending transcript to Gemini for analysis...\n"
     "[2026-03-12 09:23:28] Summary stored in database.\n"
     "[2026-03-12 09:23:28] Successfully processed: \"Deep Dive into Transformers\"\n"
     "[2026-03-12 09:23:28] Done. Processed: 1, Skipped: 1, Total checked: 2.\n"
     "[2026-03-12 09:23:28] YT Digest run complete.")

sub("13.2 Log Rotation")
body("The log file is trimmed to the last 500 lines at the start of each run "
     "(configurable via max_log_lines in config.ini). This prevents unbounded "
     "growth while keeping enough history for debugging.")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 14. TROUBLESHOOTING
# ═══════════════════════════════════════════════════════════════════════════
section("14. Troubleshooting")
story.append(HR())

sub("14.1 Script Won't Run &mdash; ModuleNotFoundError")
body("The built-in dependency checker should handle this automatically. If it fails:")
code("pip install -r %APPDATA%\\YTDigest\\requirements_ytdigest.txt")
note("Make sure you're using the same Python that OpenClaw uses. Check with: python --version")

sub("14.2 'Please set youtube_channel_id / gemini_api_key in config.ini'")
body("Edit the config file and replace the placeholder values:")
code("notepad \"%APPDATA%\\YTDigest\\config.ini\"")

sub("14.3 'No Videos Found in RSS Feed'")
bullet("Verify the channel ID is correct in config.ini")
bullet("Check internet connectivity")
bullet("YouTube may be temporarily down or rate-limiting")
bullet("Try opening the feed URL in a browser")

sub("14.4 'Transcript Not Yet Available'")
body("This is <b>normal</b> for recently uploaded videos. YouTube takes time to "
     "generate auto-captions (typically 15 minutes to several hours). The video "
     "will be marked as <b>pending_transcript</b> and retried automatically every "
     "6 hours for up to 48 hours (9 attempts). After that, it becomes "
     "<b>no_transcript</b> and you can use --summarize to manually import one.")

sub("14.5 'Gemini Analysis Failed'")
bullet("Check that gemini_api_key is valid and not expired in config.ini")
bullet("Check Gemini API quotas at aistudio.google.com")
bullet("The model name may have changed &mdash; verify gemini_model is current")
bullet("Network issues can cause timeouts &mdash; the next run will retry")

sub("14.6 Scheduled Task Not Firing")
bullet("Is OpenClaw Desktop app running?")
bullet("Is the computer awake (not sleeping)?")
bullet("Check the task is enabled in the Desktop app's schedule settings")
bullet("Review ~/.claude/scheduled-tasks/yt-digest/SKILL.md exists")

sub("14.7 Database Locked Error")
body("SQLite can only handle one writer at a time. If two runs overlap:")
bullet("The instance lock should prevent this (PID-based lock file)")
bullet("If it does happen, the script will fail and retry on the next run")
bullet("Check for orphaned Python processes: tasklist | findstr python")

sub("14.8 Resetting the Database")
body("To start fresh (reprocess all videos from the last 3 days):")
code("del \"%APPDATA%\\YTDigest\\ytdigest.db\"")
body("The script will create a new database on the next run.")

sub("14.9 Resetting the Rate Limiter")
body("If the rate limiter is blocking and you want to force an immediate run:")
code("del \"%APPDATA%\\YTDigest\\last_api_call.txt\"")

story.append(PageBreak())

# ═══════════════════════════════════════════════════════════════════════════
# 15. QUICK REFERENCE
# ═══════════════════════════════════════════════════════════════════════════
section("15. Quick Reference Card")
story.append(HR())

sub("File Locations")
code("App Directory:  %APPDATA%\\YTDigest\\\n"
     "Script:         %APPDATA%\\YTDigest\\yt_digest.py\n"
     "Requirements:   %APPDATA%\\YTDigest\\requirements_ytdigest.txt\n"
     "Config:         %APPDATA%\\YTDigest\\config.ini\n"
     "Database:       %APPDATA%\\YTDigest\\ytdigest.db\n"
     "Log:            %APPDATA%\\YTDigest\\ytdigest.log\n"
     "Rate Limiter:   %APPDATA%\\YTDigest\\last_api_call.txt\n"
     "Cron Task:      ~/.claude/scheduled-tasks/yt-digest/SKILL.md")

sub("Key Commands")
code("# Run manually\n"
     "python %APPDATA%\\YTDigest\\yt_digest.py\n\n"
     "# Manually summarize a video with your own transcript\n"
     "python yt_digest.py --summarize VIDEO_ID transcript.txt\n\n"
     "# Install dependencies\n"
     "pip install -r %APPDATA%\\YTDigest\\requirements_ytdigest.txt\n\n"
     "# Edit configuration\n"
     "notepad \"%APPDATA%\\YTDigest\\config.ini\"\n\n"
     "# Query the database\n"
     "sqlite3 \"%APPDATA%\\YTDigest\\ytdigest.db\" \\\n"
     "  \"SELECT title, status, processed_at FROM processed_videos;\"\n\n"
     "# Check pending retries\n"
     "sqlite3 \"%APPDATA%\\YTDigest\\ytdigest.db\" \\\n"
     "  \"SELECT video_id, title, retry_count FROM processed_videos WHERE status='pending_transcript';\"\n\n"
     "# Reset (delete database to reprocess all)\n"
     "del \"%APPDATA%\\YTDigest\\ytdigest.db\"\n\n"
     "# Check log\n"
     "type \"%APPDATA%\\YTDigest\\ytdigest.log\"")

sub("Configuration At-a-Glance")
code("Config File:     %APPDATA%\\YTDigest\\config.ini\n"
     "Gemini Model:    gemini-2.5-flash\n"
     "DB Retention:    Forever (empty)\n"
     "Log Rotation:    500 lines\n"
     "Rate Limit:      10 min between API calls\n"
     "Lookback:        3 days\n"
     "Min Duration:    30 minutes\n"
     "Max Duration:    None (no upper limit)\n"
     "Cron Schedule:   Every 6 hours (0 */6 * * *)")

sub("Video Filtering Summary")
code("SKIP:  YouTube Shorts (hq2.jpg thumbnail or /shorts/ URL)\n"
     "SKIP:  Videos under 60 seconds (detected Shorts)\n"
     "SKIP:  Videos under 30 minutes (too short)\n"
     "SKIP:  Members-only (title pattern match)\n"
     "KEEP:  Videos 30 min and up (no upper limit)")

spacer(0.5)
story.append(HR())
body(f"End of document. Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}.")


# ═══════════════════════════════════════════════════════════════════════════
# BUILD PDF
# ═══════════════════════════════════════════════════════════════════════════
doc.build(story)
print(f"PDF generated: {OUTPUT}")
