#!/usr/bin/env python3
"""Monitor new comments on Lhugueny's Undertale the Musical video.

Requires a YouTube Data API v3 key in YOUTUBE_API_KEY.
This records public comment text and public display names locally; it does not
identify bots. It reports activity patterns for manual investigation.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

VIDEO_ID = "MobkO51msMI"
API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
DATA_DIR = Path("data")
LOG_PATH = DATA_DIR / "comments.jsonl"
STATE_PATH = DATA_DIR / "seen_ids.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def api_get(api_key: str, page_token: str | None = None) -> dict:
    params = {
        "part": "snippet",
        "videoId": VIDEO_ID,
        "maxResults": "100",
        "order": "time",
        "textFormat": "plainText",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"User-Agent": "LhuguenyUndertaleTheMusicalCommentTracker/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"YouTube API HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def unpack(item: dict) -> dict:
    top = item["snippet"]["topLevelComment"]
    snippet = top["snippet"]
    return {
        "id": top["id"],
        "published_at": snippet.get("publishedAt"),
        "author": snippet.get("authorDisplayName", "[unknown author]"),
        "text": snippet.get("textDisplay", ""),
        "like_count": snippet.get("likeCount", 0),
    }


def fetch_latest(api_key: str, seen_ids: set[str]) -> tuple[list[dict], int]:
    """Fetch newest pages until a known comment is reached (up to 5 pages)."""
    fresh: list[dict] = []
    checked = 0
    token = None
    for _ in range(5):
        data = api_get(api_key, token)
        items = data.get("items", [])
        checked += len(items)
        found_old = False
        for item in items:
            comment = unpack(item)
            if comment["id"] in seen_ids:
                found_old = True
                break
            fresh.append(comment)
        if found_old or not data.get("nextPageToken"):
            break
        token = data["nextPageToken"]
    fresh.sort(key=lambda c: c.get("published_at") or "")
    return fresh, checked


def load_seen() -> set[str]:
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return set()
    except (json.JSONDecodeError, OSError):
        print(f"Warning: couldn't read {STATE_PATH}; starting without saved IDs.", file=sys.stderr)
        return set()


def save_state(seen_ids: set[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(sorted(seen_ids)), encoding="utf-8")
    temp.replace(STATE_PATH)


def append_log(comment: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(comment, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch new comments on Story of Undertale.")
    parser.add_argument("--interval", type=int, default=15, help="seconds between API polls (default: 15; minimum: 10)")
    parser.add_argument("--include-existing", action="store_true", help="print/log comments found on the first run instead of using them as a baseline")
    args = parser.parse_args()
    if args.interval < 10:
        parser.error("--interval must be at least 10 seconds to avoid unnecessary API requests")

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("Missing YOUTUBE_API_KEY. Set a YouTube Data API v3 key first.", file=sys.stderr)
        print("Example: export YOUTUBE_API_KEY='your-key-here'", file=sys.stderr)
        return 2

    print("Lhugueny Undertale The Musical Comment Tracker")
    print(f"Video: https://youtu.be/{VIDEO_ID}")
    print(f"Polling every {args.interval}s. Ctrl+C to stop.")
    print("Note: activity patterns are clues, not proof that an account is a bot.\n")

    seen = load_seen()
    first_run = not seen
    per_author: Counter[str] = Counter()
    recent_times: deque[datetime] = deque()

    try:
        latest, checked = fetch_latest(api_key, seen)
        if first_run and not args.include_existing:
            seen.update(c["id"] for c in latest)
            save_state(seen)
            print(f"Baseline set: found {len(latest)} recent comments. Waiting for new ones...")
        else:
            for comment in latest:
                seen.add(comment["id"])
                append_log(comment)
                per_author[comment["author"]] += 1
                stamp = comment.get("published_at") or "unknown time"
                print(f"[{stamp}] @{comment['author']}: {comment['text']}")
            save_state(seen)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    try:
        while True:
            time.sleep(args.interval)
            try:
                fresh, _ = fetch_latest(api_key, seen)
            except RuntimeError as exc:
                print(f"\nPoll failed: {exc}", file=sys.stderr)
                continue

            now = utc_now()
            while recent_times and (now - recent_times[0]).total_seconds() > 60:
                recent_times.popleft()

            if not fresh:
                print(f"[{now.strftime('%H:%M:%S UTC')}] No new comments in the latest results.")
                continue

            for comment in fresh:
                comment["observed_at"] = now.isoformat()
                seen.add(comment["id"])
                append_log(comment)
                per_author[comment["author"]] += 1
                recent_times.append(now)
                stamp = comment.get("published_at") or "unknown time"
                print(f"\n[{stamp}] @{comment['author']}: {comment['text']}")
                print(f"  New comments observed this minute: {len(recent_times)}")
                print(f"  Comments logged from this display name: {per_author[comment['author']]}")
            save_state(seen)
    except KeyboardInterrupt:
        save_state(seen)
        print(f"\nStopped. New comments are saved in {LOG_PATH}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
