"""
YT Digest - YouTube Transcript Analyzer (Cron-Triggered)

Run via cron/scheduled task. Each execution:
1. Fetches the latest video from a hardcoded YouTube channel
2. Checks if the transcript is available
3. If available and not already processed, pulls the transcript
4. Sends it to Gemini for 3-5 key highlights
5. Saves the summary to AppData

Tracks processed videos in SQLite to avoid re-processing.
Rotates summaries, logs, and DB entries to prevent data accumulation.
"""

import os
import sys
import time
import sqlite3
import subprocess
import configparser
import importlib.metadata
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Dependency Check ───────────────────────────────────────────────────────
# Mapping: pip package name -> (import name, minimum version)
REQUIRED_PACKAGES = {
    "feedparser":             ("feedparser",             "6.0.0"),
    "requests":               ("requests",               "2.25.0"),
    "youtube-transcript-api": ("youtube_transcript_api", "1.2.0"),
    "google-generativeai":    ("google.generativeai",    "0.8.0"),
}


def check_dependencies():
    """Verify all required packages are installed and meet minimum versions.
    Attempts auto-install from requirements file if any are missing."""
    missing = []
    outdated = []

    for pip_name, (import_name, min_version) in REQUIRED_PACKAGES.items():
        # Check if the package is importable
        top_module = import_name.split(".")[0]
        try:
            importlib.import_module(top_module)
        except ImportError:
            missing.append(pip_name)
            continue

        # Check installed version against minimum
        try:
            installed = importlib.metadata.version(pip_name)
            if _version_tuple(installed) < _version_tuple(min_version):
                outdated.append(
                    f"  {pip_name}: installed {installed}, requires >={min_version}"
                )
        except importlib.metadata.PackageNotFoundError:
            missing.append(pip_name)

    # Attempt auto-install if there are problems
    if missing or outdated:
        req_file = Path(__file__).parent / "requirements_ytdigest.txt"
        if req_file.exists():
            print(f"[SETUP] Missing or outdated packages detected. "
                  f"Installing from {req_file}...")
            # Try standard pip install first, then with --break-system-packages
            # for Debian/Ubuntu/RPi systems that enforce PEP 668
            pip_base = [sys.executable, "-m", "pip", "install",
                        "-r", str(req_file), "--quiet"]
            result = subprocess.run(
                pip_base, capture_output=True, text=True
            )
            if result.returncode != 0 and "externally-managed" in result.stderr:
                print("[SETUP] Detected externally-managed environment. "
                      "Retrying with --break-system-packages...")
                result = subprocess.run(
                    pip_base + ["--break-system-packages"],
                    capture_output=True, text=True
                )
            if result.returncode == 0:
                print("[SETUP] Dependencies installed successfully.")
                # Re-verify after install
                return _verify_all_installed()
            else:
                print(f"[SETUP] pip install failed:\n{result.stderr}")

        # If auto-install wasn't possible or failed, report and exit
        print("\n" + "=" * 60)
        print("DEPENDENCY CHECK FAILED")
        print("=" * 60)
        if missing:
            print("\nMissing packages:")
            for pkg in missing:
                print(f"  - {pkg}")
        if outdated:
            print("\nOutdated packages:")
            for line in outdated:
                print(line)
        print(f"\nTo fix, run:")
        print(f"  pip install -r requirements_ytdigest.txt")
        print(f"\nOr install individually:")
        for pkg in missing:
            min_ver = REQUIRED_PACKAGES[pkg][1]
            print(f"  pip install \"{pkg}>={min_ver}\"")
        print("=" * 60)
        sys.exit(1)


def _verify_all_installed() -> None:
    """Final verification that all packages are importable after install."""
    # Clear the metadata cache so freshly-installed packages are visible
    importlib.invalidate_caches()
    if hasattr(importlib.metadata, "_cache"):
        importlib.metadata._cache.clear()

    failures = []
    for pip_name, (import_name, min_version) in REQUIRED_PACKAGES.items():
        top_module = import_name.split(".")[0]
        try:
            # Force re-import after install
            if top_module in sys.modules:
                del sys.modules[top_module]
            importlib.import_module(top_module)
        except ImportError:
            failures.append(pip_name)
            continue

        try:
            # Re-read metadata fresh from disk
            dist = importlib.metadata.Distribution.from_name(pip_name)
            installed = dist.metadata["Version"]
            if _version_tuple(installed) < _version_tuple(min_version):
                failures.append(f"{pip_name} (version {installed} < {min_version})")
        except importlib.metadata.PackageNotFoundError:
            failures.append(pip_name)

    if failures:
        print("\n[ERROR] The following packages are still not available "
              "after auto-install attempt:")
        for f in failures:
            print(f"  - {f}")
        print("\nPlease install manually:")
        print("  pip install -r requirements_ytdigest.txt")
        sys.exit(1)


def _version_tuple(version_str: str) -> tuple:
    """Convert a version string like '1.2.3' to a comparable tuple."""
    parts = []
    for part in version_str.split("."):
        # Handle versions like '1.2.3rc1' — strip non-numeric suffixes
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


# Run dependency check before importing third-party packages
check_dependencies()
# ───────────────────────────────────────────────────────────────────────────

import re
import feedparser
import requests
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai

# ── Paths ──────────────────────────────────────────────────────────────────
APP_DIR = Path(os.environ.get("APPDATA", "")) / "YTDigest"
CONFIG_PATH = APP_DIR / "config.ini"
DB_PATH = APP_DIR / "ytdigest.db"
LOG_PATH = APP_DIR / "ytdigest.log"
LAST_API_CALL_FILE = APP_DIR / "last_api_call.txt"
LOCK_FILE = APP_DIR / "ytdigest.lock"

# Rate limiting
MIN_API_INTERVAL_SECS = 600  # 10 minutes between API calls
LOOKBACK_DAYS = 3            # On first run, check videos from the last N days

# Video filtering (durations in seconds)
MIN_DURATION_SECS = 1800     # 30 minutes — skip anything shorter

# ── Default Configuration ──────────────────────────────────────────────────
DEFAULTS = {
    "youtube_channel_id": "REPLACE_WITH_CHANNEL_ID",
    "gemini_api_key": "REPLACE_WITH_GEMINI_API_KEY",
    "gemini_model": "gemini-2.5-flash",
    "db_retention_days": "",      # Empty = keep forever, or a number to prune
    "max_log_lines": "500",
}


def _prompt_for_config() -> dict:
    """Interactive first-run setup: ask user for required settings."""
    print()
    print("=" * 60)
    print("  YT Digest — First-Run Setup")
    print("=" * 60)
    print()
    print("  You need a YouTube Channel ID and a Google Gemini API key.")
    print("  Channel IDs start with 'UC' (24 characters).")
    print("  Get a Gemini API key free at: https://aistudio.google.com")
    print()

    channel_id = input("  YouTube Channel ID: ").strip()
    api_key = input("  Gemini API Key: ").strip()
    print()

    overrides = {}
    if channel_id:
        overrides["youtube_channel_id"] = channel_id
    if api_key:
        overrides["gemini_api_key"] = api_key

    return overrides


def _write_config(config: configparser.ConfigParser):
    """Write config to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("; YT Digest Configuration\n")
        f.write("; Edit the values below. This file is located at:\n")
        f.write(f";   {CONFIG_PATH}\n\n")
        config.write(f)


def _install_to_appdata():
    """Copy the script and requirements into %APPDATA%\\YTDigest if not already there."""
    import shutil
    APP_DIR.mkdir(parents=True, exist_ok=True)

    script_src = Path(__file__).resolve()
    script_dst = APP_DIR / script_src.name
    req_src = script_src.parent / "requirements_ytdigest.txt"
    req_dst = APP_DIR / "requirements_ytdigest.txt"

    # Skip if already running from AppData
    if script_src.parent.resolve() == APP_DIR.resolve():
        return

    # Copy script
    if not script_dst.exists() or script_src.stat().st_mtime > script_dst.stat().st_mtime:
        shutil.copy2(script_src, script_dst)
        print(f"[SETUP] Installed {script_src.name} -> {APP_DIR}")

    # Copy requirements
    if req_src.exists():
        if not req_dst.exists() or req_src.stat().st_mtime > req_dst.stat().st_mtime:
            shutil.copy2(req_src, req_dst)
            print(f"[SETUP] Installed requirements_ytdigest.txt -> {APP_DIR}")

    print(f"[SETUP] App installed to: {APP_DIR}")
    print(f"[SETUP] Future runs: python \"{script_dst}\"")


def load_config() -> configparser.ConfigParser:
    """Load config from config.ini. On first run, prompt for required values."""
    _install_to_appdata()

    config = configparser.ConfigParser()
    config["ytdigest"] = DEFAULTS

    first_run = not CONFIG_PATH.exists()

    if not first_run:
        config.read(str(CONFIG_PATH), encoding="utf-8")

    # Check if required values are still placeholders
    needs_setup = (
        config.get("ytdigest", "youtube_channel_id") == "REPLACE_WITH_CHANNEL_ID"
        or config.get("ytdigest", "gemini_api_key") == "REPLACE_WITH_GEMINI_API_KEY"
    )

    if needs_setup and sys.stdin.isatty():
        overrides = _prompt_for_config()
        for key, value in overrides.items():
            config.set("ytdigest", key, value)
        _write_config(config)
        print(f"[SETUP] Config saved to: {CONFIG_PATH}")
    elif first_run:
        _write_config(config)
        print(f"[SETUP] Default config created at: {CONFIG_PATH}")
        print("[SETUP] Please edit config.ini with your API key and channel ID.")

    return config


# Load configuration
_cfg = load_config()
YOUTUBE_CHANNEL_ID = _cfg.get("ytdigest", "youtube_channel_id")
GEMINI_API_KEY = _cfg.get("ytdigest", "gemini_api_key")
GEMINI_MODEL = _cfg.get("ytdigest", "gemini_model")

_db_ret = _cfg.get("ytdigest", "db_retention_days").strip()
DB_RETENTION_DAYS = int(_db_ret) if _db_ret else None

MAX_LOG_LINES = _cfg.getint("ytdigest", "max_log_lines", fallback=500)
# ───────────────────────────────────────────────────────────────────────────


def log(msg: str):
    """Append a timestamped message to the log file and print to console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def init_dirs():
    """Create application directories if they don't exist."""
    APP_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> sqlite3.Connection:
    """Initialize SQLite database and return a connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_videos (
            video_id     TEXT PRIMARY KEY,
            title        TEXT,
            published    DATETIME,
            processed_at DATETIME,
            status       TEXT DEFAULT 'done',
            summary      TEXT,
            transcript   TEXT
        )
    """)
    conn.commit()

    # Migrate older schema if columns are missing
    cursor = conn.execute("PRAGMA table_info(processed_videos)")
    columns = {row[1] for row in cursor.fetchall()}
    if "transcript" not in columns:
        conn.execute("ALTER TABLE processed_videos ADD COLUMN transcript TEXT")
    if "summary" not in columns:
        conn.execute("ALTER TABLE processed_videos ADD COLUMN summary TEXT")
    if "status" not in columns:
        conn.execute("ALTER TABLE processed_videos ADD COLUMN status TEXT DEFAULT 'done'")
    conn.commit()

    return conn


def is_processed(conn: sqlite3.Connection, video_id: str) -> bool:
    """Check if a video has already been processed."""
    row = conn.execute(
        "SELECT 1 FROM processed_videos WHERE video_id = ?", (video_id,)
    ).fetchone()
    return row is not None


def mark_processed(conn: sqlite3.Connection, video_id: str, title: str,
                   published: str, summary: str, transcript: str):
    """Record a video as processed with its transcript and summary."""
    conn.execute(
        """INSERT OR REPLACE INTO processed_videos
           (video_id, title, published, processed_at, status, summary, transcript)
           VALUES (?, ?, ?, ?, 'done', ?, ?)""",
        (video_id, title, published, datetime.now().isoformat(),
         summary, transcript),
    )
    conn.commit()


def mark_skipped(conn: sqlite3.Connection, video_id: str, title: str,
                 published: str, reason: str):
    """Record a video as skipped so it won't be retried on future runs."""
    conn.execute(
        """INSERT OR IGNORE INTO processed_videos
           (video_id, title, published, processed_at, status)
           VALUES (?, ?, ?, ?, ?)""",
        (video_id, title, published, datetime.now().isoformat(), reason),
    )
    conn.commit()


def parse_iso8601_duration(duration_str: str) -> int:
    """Parse an ISO 8601 duration like PT1H30M45S into total seconds."""
    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str, re.IGNORECASE
    )
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def get_video_duration(video_id: str) -> int | None:
    """Fetch the video page and extract duration from meta tag. Returns seconds."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })
        # Look for <meta itemprop="duration" content="PT1H30M45S">
        match = re.search(
            r'<meta\s+itemprop="duration"\s+content="([^"]+)"', resp.text
        )
        if match:
            return parse_iso8601_duration(match.group(1))
    except Exception as e:
        log(f"Could not fetch duration for {video_id}: {e}")
    return None


def is_short_by_thumbnail(entry) -> bool:
    """Quick check: Shorts typically use hq2.jpg thumbnail instead of hqdefault.jpg."""
    # feedparser stores media:thumbnail in media_thumbnail list
    thumbnails = getattr(entry, "media_thumbnail", [])
    for thumb in thumbnails:
        url = thumb.get("url", "")
        if "hq2.jpg" in url:
            return True
    return False


def is_short_by_url(entry) -> bool:
    """Check if the video link uses the /shorts/ URL pattern."""
    link = getattr(entry, "link", "")
    return "/shorts/" in link


def classify_video_by_duration(video_id: str) -> str:
    """Classify a video using only page metadata (for yt-dlp fallback entries)."""
    duration = get_video_duration(video_id)
    if duration is None:
        return "eligible"
    if duration <= 60:
        return "short"
    elif duration < MIN_DURATION_SECS:
        return "too_short"
    return "eligible"


def classify_video(entry, video_id: str) -> str:
    """
    Classify a video as 'short', 'too_short', or 'eligible'.
    Uses fast RSS-based checks first, then falls back to page metadata.
    """
    # Fast check 1: thumbnail pattern
    if is_short_by_thumbnail(entry):
        return "short"

    # Fast check 2: URL pattern
    if is_short_by_url(entry):
        return "short"

    # Detailed check: fetch actual duration from video page
    duration = get_video_duration(video_id)
    if duration is None:
        # Can't determine duration — include it to be safe
        return "eligible"

    if duration <= 60:
        return "short"
    elif duration < MIN_DURATION_SECS:
        return "too_short"
    else:
        return "eligible"


def _fetch_via_rss() -> list[dict]:
    """Try to get video entries from the YouTube RSS feed."""
    feed_url = (
        f"https://www.youtube.com/feeds/videos.xml?channel_id={YOUTUBE_CHANNEL_ID}"
    )
    log(f"Fetching RSS feed for channel: {YOUTUBE_CHANNEL_ID}")
    feed = feedparser.parse(feed_url)

    if not feed.entries:
        return []

    from email.utils import parsedate_to_datetime
    entries = []
    for entry in feed.entries:
        try:
            pub_date = parsedate_to_datetime(entry.published)
        except Exception:
            pub_date = datetime.now(timezone.utc)
        entries.append({
            "video_id": entry.get("yt_videoid", entry.link.split("v=")[-1]),
            "title": entry.title,
            "link": entry.link,
            "pub_date": pub_date,
            "_entry": entry,  # keep for thumbnail/URL checks
        })
    return entries


def _fetch_via_ytdlp() -> list[dict]:
    """Fallback: use yt-dlp to discover recent videos when RSS is blocked."""
    import json as _json
    channel_url = f"https://www.youtube.com/channel/{YOUTUBE_CHANNEL_ID}/videos"
    log("RSS feed unavailable. Trying yt-dlp fallback...")
    try:
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-json",
             "--playlist-items", "1:15", channel_url],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            log(f"yt-dlp failed: {result.stderr.strip()}")
            return []
    except FileNotFoundError:
        log("yt-dlp not installed. Install with: pip install yt-dlp")
        return []
    except subprocess.TimeoutExpired:
        log("yt-dlp timed out.")
        return []

    entries = []
    for line in result.stdout.strip().splitlines():
        try:
            data = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        video_id = data.get("id", "")
        title = data.get("title", "")
        # yt-dlp uses YYYYMMDD format for upload_date
        upload_date = data.get("upload_date", "")
        if upload_date and len(upload_date) == 8:
            try:
                pub_date = datetime(
                    int(upload_date[:4]), int(upload_date[4:6]),
                    int(upload_date[6:8]), tzinfo=timezone.utc
                )
            except ValueError:
                pub_date = datetime.now(timezone.utc)
        else:
            pub_date = datetime.now(timezone.utc)

        entries.append({
            "video_id": video_id,
            "title": title,
            "link": f"https://www.youtube.com/watch?v={video_id}",
            "pub_date": pub_date,
            "_entry": None,
        })

    log(f"yt-dlp found {len(entries)} videos.")
    return entries


def get_recent_videos(lookback_days: int = LOOKBACK_DAYS) -> list[dict]:
    """Fetch eligible videos from the last N days. Tries RSS, falls back to yt-dlp."""
    # Try RSS first, fall back to yt-dlp
    raw_entries = _fetch_via_rss()
    if not raw_entries:
        raw_entries = _fetch_via_ytdlp()
    if not raw_entries:
        log("No videos found from any source.")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    videos = []
    skipped_short = 0
    skipped_too_short = 0

    for item in raw_entries:
        if item["pub_date"] < cutoff:
            continue

        video_id = item["video_id"]
        entry = item.get("_entry")  # may be None for yt-dlp entries

        # Classification: use RSS entry checks if available, else duration only
        if entry is not None:
            classification = classify_video(entry, video_id)
        else:
            classification = classify_video_by_duration(video_id)

        if classification == "short":
            skipped_short += 1
            log(f"  Skipping Short: \"{item['title']}\"")
            continue
        elif classification == "too_short":
            skipped_too_short += 1
            log(f"  Skipping (under {MIN_DURATION_SECS // 60} min): \"{item['title']}\"")
            continue

        videos.append({
            "video_id": video_id,
            "title": item["title"],
            "published": item["pub_date"].isoformat(),
            "link": item["link"],
            "pub_date": item["pub_date"],
        })

    # Sort oldest first so we process in chronological order
    videos.sort(key=lambda v: v["pub_date"])
    log(f"Eligible videos: {len(videos)} "
        f"(skipped {skipped_short} shorts, "
        f"{skipped_too_short} too short)")
    return videos


def fetch_transcript(video_id: str) -> str | None:
    """
    Retrieve the transcript for a given video ID.
    Uses the proven pattern from YTtranscriptReady/gettranscript.py.
    """
    log(f"Fetching transcript for video: {video_id}")
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)

        lines = []
        for snippet in transcript:
            total_seconds = int(snippet.start)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60

            if hours > 0:
                timestamp = f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"
            else:
                timestamp = f"[{minutes:02d}:{seconds:02d}]"

            lines.append(f"{timestamp} {snippet.text}")

        return "\n".join(lines)

    except Exception as e:
        error_msg = str(e)
        if "No transcripts" in error_msg or "not available" in error_msg.lower():
            log(f"Transcript not yet available for {video_id}.")
        else:
            log(f"Failed to fetch transcript: {e}")
        return None


def analyze_with_gemini(transcript: str, title: str) -> str:
    """Send the transcript to Gemini and get 3-5 key highlights."""
    log("Sending transcript to Gemini for analysis...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    prompt = (
        "You are an expert content analyst. Given the following YouTube video "
        "transcript, identify the TOP 5 HIGHLIGHTS -- the most interesting, "
        "insightful, entertaining, or important moments from the video.\n\n"
        "For each highlight:\n"
        "1. Give it a short, punchy title\n"
        "2. Do Not include any timestamps\n"
        "3. Write a 2-3 sentence summary of what happens and why it matters\n"
        "4. If the speaker identifies themselves, use their name in the text. "
        "Replace \"host name,\" \"host,\" or \"speaker\" with the actual name "
        "provided by the speaker in the transcript.\n\n"
        "Focus on substance -- key ideas, memorable quotes, turning points, or "
        "standout moments that a viewer would most want to know about. Skip "
        "intros, filler, and music-only segments.\n\n"
        f"Video Title: {title}\n\n"
        "TRANSCRIPT:\n"
        f'"""\n{transcript}\n"""\n\n'
        "Return the 5 highlights now:"
    )

    response = model.generate_content(prompt)
    return response.text


# ── Housekeeping ───────────────────────────────────────────────────────────

def prune_db(conn: sqlite3.Connection):
    """Remove DB entries older than DB_RETENTION_DAYS. Skips if set to None."""
    if DB_RETENTION_DAYS is None:
        return
    cutoff = (datetime.now() - timedelta(days=DB_RETENTION_DAYS)).isoformat()
    deleted = conn.execute(
        "DELETE FROM processed_videos WHERE processed_at < ?", (cutoff,)
    ).rowcount
    conn.commit()
    if deleted:
        log(f"Pruned {deleted} old database entries.")


def rotate_log():
    """Trim the log file if it exceeds MAX_LOG_LINES."""
    if not LOG_PATH.exists():
        return
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_LOG_LINES:
            trimmed = lines[-MAX_LOG_LINES:]
            LOG_PATH.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
    except Exception:
        pass


# ── Rate Limiting ─────────────────────────────────────────────────────────

def get_last_api_call_time() -> float:
    """Read the timestamp of the last API call from disk. Returns 0 if none."""
    try:
        if LAST_API_CALL_FILE.exists():
            return float(LAST_API_CALL_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        pass
    return 0.0


def record_api_call_time():
    """Write the current time as the last API call timestamp."""
    try:
        LAST_API_CALL_FILE.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def enforce_rate_limit():
    """Wait if needed to respect the 10-minute minimum between API calls."""
    last_call = get_last_api_call_time()
    if last_call == 0.0:
        return  # No previous call recorded

    elapsed = time.time() - last_call
    remaining = MIN_API_INTERVAL_SECS - elapsed

    if remaining > 0:
        minutes = remaining / 60
        log(f"Rate limit: waiting {minutes:.1f} minutes before next API call...")
        time.sleep(remaining)


# ── Main ──────────────────────────────────────────────────────────────────

def process_single_video(conn: sqlite3.Connection, video: dict) -> bool:
    """
    Process a single video: fetch transcript, analyze, save.
    Returns True if processed, False if transcript not available.
    Enforces rate limiting and records API call times.
    """
    video_id = video["video_id"]

    # Already processed?
    if is_processed(conn, video_id):
        log(f"Video {video_id} already processed. Skipping.")
        return True

    # Enforce rate limit before any API call
    enforce_rate_limit()

    # Fetch transcript
    transcript = fetch_transcript(video_id)
    record_api_call_time()

    if not transcript:
        log(f"Transcript not available for \"{video['title']}\". Marking as no_transcript.")
        mark_skipped(conn, video_id, video["title"],
                     video["published"], "no_transcript")
        return False

    log(f"Transcript retrieved: {len(transcript)} characters")

    # Enforce rate limit before Gemini call
    enforce_rate_limit()

    # Analyze with Gemini
    try:
        highlights = analyze_with_gemini(transcript, video["title"])
        record_api_call_time()
    except Exception as e:
        log(f"Gemini analysis failed: {e}")
        return False

    # Store transcript + summary in DB
    mark_processed(conn, video_id, video["title"],
                   video["published"], highlights, transcript)
    log(f"Summary stored in database.")

    log(f"Successfully processed: \"{video['title']}\"")
    return True


def acquire_lock() -> bool:
    """Try to acquire a file lock. Returns True if successful."""
    try:
        if LOCK_FILE.exists():
            # Check if the PID in the lock file is still running
            pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            try:
                os.kill(pid, 0)  # signal 0 = check if process exists
                return False     # process is alive, lock is held
            except OSError:
                pass             # process is dead, stale lock
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception:
        return False


def release_lock():
    """Release the file lock."""
    try:
        if LOCK_FILE.exists():
            # Only remove if we own it
            pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            if pid == os.getpid():
                LOCK_FILE.unlink()
    except Exception:
        pass


def main():
    init_dirs()

    if not acquire_lock():
        print("[SKIP] Another instance is already running. Exiting.")
        sys.exit(0)

    try:
        _main()
    finally:
        release_lock()


def _main():
    rotate_log()

    log("=" * 60)
    log("YT Digest run started.")

    if YOUTUBE_CHANNEL_ID == "REPLACE_WITH_CHANNEL_ID":
        log(f"ERROR: Please set youtube_channel_id in {CONFIG_PATH}")
        sys.exit(1)
    if GEMINI_API_KEY == "REPLACE_WITH_GEMINI_API_KEY":
        log(f"ERROR: Please set gemini_api_key in {CONFIG_PATH}")
        sys.exit(1)

    conn = init_db()

    try:
        # Get videos from the last LOOKBACK_DAYS days
        videos = get_recent_videos()
        if not videos:
            log("No recent videos found. Exiting.")
            return

        processed = 0
        skipped = 0

        for video in videos:
            video_id = video["video_id"]
            log(f"Checking: \"{video['title']}\" ({video_id})")

            if is_processed(conn, video_id):
                log(f"  Already processed. Skipping.")
                skipped += 1
                continue

            success = process_single_video(conn, video)
            if success:
                processed += 1
            else:
                skipped += 1

        # Housekeeping
        prune_db(conn)

        log(f"Done. Processed: {processed}, Skipped: {skipped}, "
            f"Total checked: {len(videos)}.")

    finally:
        conn.close()
        log("YT Digest run complete.")


if __name__ == "__main__":
    main()
