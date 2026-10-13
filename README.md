# YouTube Publish Time Exporter

A reusable Python CLI that exports public YouTube video publish times in a configurable local time zone. It supports date filtering, channel handles and IDs, live-stream timestamps, format estimation, and Excel-compatible CSV output.

## Features

- Select a channel by `@handle`, YouTube channel ID, or an optional alias in `config.yaml`.
- Export a custom date range, the previous calendar month, the last N days, or the channel's full public history.
- Convert UTC timestamps with Python `zoneinfo` instead of using a fixed UTC offset.
- Use the actual or scheduled start time for live streams when available.
- Estimate `Shorts`, `Video`, `Live`, and possible Premiere formats.
- Retry temporary network and YouTube API errors.
- Write CSV files atomically with UTF-8 BOM for Excel compatibility.
- Keep API keys and generated datasets out of Git.

## Requirements

- Python 3.10 or newer
- A Google Cloud API key with YouTube Data API v3 enabled

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder with your API key:

```env
YT_API_KEY=your_api_key_here
```

Do not put the real key in `.env.example`, `config.yaml`, source files, or publicly visible repository settings.

## Usage

PowerShell treats `@` specially in some contexts, so quote channel handles:

```powershell
python -m yayin_saati --kanal "@YourChannelHandle" --bas 2026-01-01 --bit 2026-01-31
python -m yayin_saati --kanal "@YourChannelHandle" --gecen-ay
python -m yayin_saati --kanal "@YourChannelHandle" --son-gun 90
python -m yayin_saati --kanal UCxxxxxxxxxxxxxxxxxxxxxxx --tum
```

You can process multiple channels by separating them with commas:

```powershell
python -m yayin_saati --kanal "@FirstChannel,@SecondChannel" --gecen-ay
```

Exactly one date mode is required:

- `--bas YYYY-MM-DD --bit YYYY-MM-DD`: inclusive local dates
- `--gecen-ay`: previous calendar month
- `--son-gun N`: today plus the previous N-1 days
- `--tum`: all public uploads

Use `--cikti path.csv` to choose an output path. Add `--shorts-dogrula` to verify Shorts with YouTube URL checks.

## Optional channel aliases

You can save frequently used channels in `config.yaml`:

```yaml
kanallar:
  primary:
    ad: Primary Channel
    handle: "@YourChannelHandle"
```

Then run:

```powershell
python -m yayin_saati --kanal primary --gecen-ay
```

Keep private or organization-specific aliases in a local config file if you do not want them published.

## CSV output

Generated files contain the video ID, title, URL, UTC and local publish times, date parts, time bucket, duration, estimated format, timestamp source, live-stream timestamps, and collection time. Rows are sorted by local publish time.

The output uses comma-separated UTF-8 with BOM. Generated CSV files are written under `cikti/` by default and are ignored by Git.

## Tests

Run the complete test suite:

```powershell
python -m pytest -q
```

Run only the API-free end-to-end smoke test:

```powershell
python -m pytest -q tests/test_smoke.py
```

The smoke test exercises CLI parsing, channel selection, time-zone conversion, date filtering, format classification, sorting, and CSV writing without using an API key or quota.

## Security and public repositories

Before every public push, check staged files:

```powershell
git status
git diff --cached
```

The following local files must not be committed:

- `.env`
- `cikti/*.csv`
- virtual environments, caches, and logs

Never use `git add -f` for ignored secrets or generated data. If an API key is ever committed, revoke or rotate it in Google Cloud immediately; deleting it in a later commit does not remove it from Git history.

## Known limitations

- Private, unlisted, and deleted videos are not available with an API key.
- Format detection is an estimate; YouTube Studio remains the authoritative source.
- Premiere versus live-stream classification is heuristic.
- Shorts URL verification depends on YouTube's current redirect behavior.
