# Project Report

## Scope

This repository contains a reusable Python command-line tool for exporting public YouTube video publish times to CSV. The implementation is channel-agnostic: users can supply any public channel handle or ID at runtime.

## Implementation summary

- Environment-based API key loading with `python-dotenv`.
- YouTube Data API v3 client with pagination, batching, retries, and readable API errors.
- Channel lookup by handle or channel ID.
- Time-zone conversion through `zoneinfo`.
- Inclusive local-date filtering.
- Duration parsing and estimated content-format classification.
- Live-stream timestamp selection and possible Premiere detection.
- Optional Shorts URL verification with request throttling.
- Atomic, UTF-8 BOM CSV output.
- VS Code tasks for common date ranges.
- Unit and API-free smoke tests.

## Security and data handling

- The real API key belongs only in the ignored `.env` file.
- `.env.example` contains a placeholder and is safe to publish.
- Generated files under `cikti/` are ignored, except for `.gitkeep`.
- No generated channel data is required by the application or tests.
- Tests use synthetic records and do not consume API quota.

## Verification

Run:

```powershell
python -m pytest -q
python -m pytest -q tests/test_smoke.py
```

The smoke test covers the main CLI-to-CSV path using synthetic API responses, including a UTC timestamp that moves into the next local calendar day.

## Public repository checklist

Before publishing:

1. Confirm `.env` is absent from `git status`.
2. Confirm generated CSV files are absent from `git status`.
3. Inspect `git diff --cached` before committing.
4. Rotate the API key immediately if it is ever committed.
