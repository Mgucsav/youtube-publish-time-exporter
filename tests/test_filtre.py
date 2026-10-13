from datetime import datetime, timezone

from yayin_saati.api import YouTubeApiClient


class FakeClient(YouTubeApiClient):
    def __init__(self, pages):
        self.pages = iter(pages)

    def _get(self, resource, params):
        return next(self.pages)


def item(video_id, published_at):
    return {
        "contentDetails": {"videoId": video_id, "videoPublishedAt": published_at},
        "snippet": {"publishedAt": published_at},
    }


def test_early_stop_reads_at_most_one_page_after_old_page():
    old = "2026-08-01T00:00:00Z"
    pages = [
        {"items": [item("new", "2026-09-20T00:00:00Z")], "nextPageToken": "p2"},
        {"items": [item("old-1", old)], "nextPageToken": "p3"},
        {"items": [item("old-2", old)], "nextPageToken": "p4"},
        {"items": [item("should-not-read", old)], "nextPageToken": "p5"},
    ]
    client = FakeClient(pages)
    before = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ids = client.list_upload_ids("uploads", before_utc=before)
    assert ids == ["new", "old-1", "old-2"]
