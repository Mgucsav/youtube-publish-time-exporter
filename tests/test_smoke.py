"""API anahtari harcamadan ana uygulama akisini dogrulayan smoke test."""

import csv
from datetime import datetime, timezone
from pathlib import Path

from yayin_saati.__main__ import parser, run
from yayin_saati.api import YouTubeApiClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def video(video_id, title, published_at, duration, live=None):
    item = {
        "id": video_id,
        "snippet": {"title": title, "publishedAt": published_at},
        "contentDetails": {"duration": duration},
    }
    if live is not None:
        item["liveStreamingDetails"] = live
    return item


def test_cli_to_csv_smoke(monkeypatch, tmp_path, capsys):
    api_items = [
        video("short-1", "Kisa video", "2026-09-01T17:00:00Z", "PT45S"),
        video("video-1", "Normal video", "2026-09-02T18:05:00Z", "PT10M"),
        video(
            "live-1",
            "Canli yayin",
            "2026-09-03T17:55:00Z",
            "PT1H",
            {
                "scheduledStartTime": "2026-09-03T18:00:00Z",
                "actualStartTime": "2026-09-03T18:05:00Z",
                "actualEndTime": "2026-09-03T19:15:00Z",
            },
        ),
        # UTC'de Eylul, fakat TR saatinde 1 Ekim: ciktiya girmemeli.
        video("out-of-range", "Aralik disi", "2026-09-30T22:30:00Z", "PT5M"),
    ]
    observed = {}

    def fake_get_channel_videos(self, channel, before_utc=None):
        observed["channel"] = channel
        observed["before_utc"] = before_utc
        return api_items

    monkeypatch.setenv("YT_API_KEY", "smoke-test-only")
    monkeypatch.setattr(YouTubeApiClient, "get_channel_videos", fake_get_channel_videos)

    output = tmp_path / "smoke.csv"
    args = parser().parse_args(
        [
            "--kanal",
            "@ExampleChannel",
            "--bas",
            "2026-09-01",
            "--bit",
            "2026-09-30",
            "--cikti",
            str(output),
            "--config",
            str(PROJECT_ROOT / "config.yaml"),
        ]
    )

    assert run(args) == 0
    assert observed["channel"]["handle"] == "@ExampleChannel"
    assert observed["before_utc"] == datetime(2026, 8, 31, 21, 0, tzinfo=timezone.utc)
    assert output.read_bytes().startswith(bytes([239, 187, 191]))

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["video_id"] for row in rows] == ["short-1", "video-1", "live-1"]
    assert [row["format_tahmini"] for row in rows] == ["Shorts", "Video", "Canli"]
    assert rows[0]["yayin_tr"] == "2026-09-01 20:00:00"
    assert rows[2]["zaman_kaynagi"] == "actualStartTime"
    assert "Toplam video: 3" in capsys.readouterr().out
