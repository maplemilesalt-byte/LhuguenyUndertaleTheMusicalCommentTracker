# LhuguenyUndertaleTheMusicalCommentTracker

A small Python monitor for new comments on Lhugueny's **Undertale the Musical** video. Made to investigate an unusual burst of apparently random comments, without assuming they are bots.

**Tracked video:** https://youtu.be/MobkO51msMI

## Requirements

- Python 3.10+
- A YouTube Data API v3 key. Enable **YouTube Data API v3** in a Google Cloud project and create an API key. Keep the key private; do not commit it to GitHub.

The tracker uses only Python's standard library; no pip packages are required.

## Run on CachyOS / Arch Linux

```bash
git clone https://github.com/maplemilesalt-byte/LhuguenyUndertaleTheMusicalCommentTracker.git
cd LhuguenyUndertaleTheMusicalCommentTracker

# Set your key for this terminal session:
export YOUTUBE_API_KEY='PASTE_YOUR_API_KEY_HERE'

# Start monitoring:
python main.py
```

Poll every 15 seconds by default. You can use a longer interval, for example:

```bash
python main.py --interval 30
```

On the first run, the newest comments establish a baseline; the script then prints and logs comments it sees afterward. To print/log comments returned on the first run too:

```bash
python main.py --include-existing
```

Press Ctrl+C to stop.

## Output

- New comments appear in the terminal with their publication time, display name, and text.
- New observations are appended to `data/comments.jsonl`.
- Seen comment IDs are stored in `data/seen_ids.json` so a restart can avoid reprocessing them.

These files are local and are not automatically uploaded anywhere.

## Important limitations

- This uses the official YouTube Data API. API access requires a key and is subject to quota, API availability, and the video's comment settings.
- It polls; it is not a true live stream. A comment may appear late, and an exceptionally large burst between polls can exceed the API pages checked.
- The API exposes public comment metadata, not the author's private account details.
- Repeated comments, high posting rates, strange display names, and random text can be useful observations, but **do not prove that an account is automated or that a particular user organized a raid**. Treat the output as evidence to inspect, not a bot verdict.
