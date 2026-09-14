# freetuve

Base repository for the FreeTuve app.

## Upstream engines

FreeTuve is wired to two upstream projects and pins them to known commits for reproducibility:

- `yt-dlp/yt-dlp` for media extraction and download.
- `FFmpeg/FFmpeg` for media merging, remuxing and transcoding.

The pinned revisions live in `upstream.lock.json`. The upstream source trees are intentionally not copied into FreeTuve's Git history; `scripts/sync_upstream.py` checks out the exact pinned revisions into `.vendor/` when needed.

## Bootstrap

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/sync_upstream.py
```

`yt-dlp` is installed directly from its pinned GitHub commit. The FFmpeg source checkout is kept in `.vendor/ffmpeg`; the application layer can use an installed FFmpeg binary or a build produced from that pinned source.

## Repository layout

- `upstream.lock.json`: pinned upstream repository URLs and commits.
- `scripts/sync_upstream.py`: reproducible upstream checkout.
- `requirements.txt`: Python dependency on the pinned yt-dlp revision.
- `.vendor/`: local upstream source checkouts, ignored by Git.

Only download media you are authorized to download and use.
