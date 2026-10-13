"""YouTube Data API v3 istemcisi."""

from __future__ import annotations

import time
from typing import Any, Iterable

import requests


BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    """Kullaniciya gosterilebilecek YouTube API hatasi."""


class YouTubeApiClient:
    def __init__(self, api_key: str, timeout: int = 30, session: requests.Session | None = None):
        if not api_key or not api_key.strip():
            raise YouTubeApiError("YT_API_KEY bulunamadi. .env dosyasini kontrol et.")
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.session = session or requests.Session()

    def _get(self, resource: str, params: dict[str, Any]) -> dict[str, Any]:
        query = dict(params)
        query["key"] = self.api_key
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                response = self.session.get(
                    f"{BASE_URL}/{resource}", params=query, timeout=self.timeout
                )
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code >= 400:
                    self._raise_api_error(response)
                return response.json()
            except YouTubeApiError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt == 2:
                    break
                time.sleep(2**attempt)

        raise YouTubeApiError(f"YouTube API'ye ulasilamadi: {last_error}")

    @staticmethod
    def _raise_api_error(response: requests.Response) -> None:
        try:
            payload = response.json()
            errors = payload.get("error", {}).get("errors", [])
            reasons = {item.get("reason") for item in errors}
        except ValueError:
            reasons = set()

        if "quotaExceeded" in reasons:
            raise YouTubeApiError("Gunluk kota doldu, yarin tekrar dene.")
        if "accessNotConfigured" in reasons:
            raise YouTubeApiError("YouTube Data API v3 projede etkin degil.")
        if "keyInvalid" in reasons:
            raise YouTubeApiError("API anahtari gecersiz, .env dosyasini kontrol et.")
        raise YouTubeApiError(f"YouTube API hatasi ({response.status_code}). Ayrintilar: {reasons or response.text}")

    def resolve_channel_id(self, channel: dict[str, Any]) -> str:
        channel_id = channel.get("id")
        if channel_id:
            return str(channel_id)
        handle = str(channel.get("handle", "")).strip()
        if not handle:
            raise YouTubeApiError("Kanal taniminda id veya handle bulunmuyor.")
        data = self._get("channels", {"part": "id", "forHandle": handle.lstrip("@")})
        items = data.get("items", [])
        if not items:
            raise YouTubeApiError(f"Kanal bulunamadi: {handle}")
        return str(items[0]["id"])

    def uploads_playlist_id(self, channel_id: str) -> str:
        data = self._get("channels", {"part": "contentDetails", "id": channel_id})
        items = data.get("items", [])
        if not items:
            raise YouTubeApiError(f"Kanal bulunamadi veya herkese acik degil: {channel_id}")
        try:
            return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        except KeyError as exc:
            raise YouTubeApiError("Kanalin yuklemeler oynatma listesi bulunamadi.") from exc

    def list_upload_ids(self, playlist_id: str, before_utc=None) -> list[str]:
        """Yukleme listesini sayfalar; eski sayfadan sonra en fazla bir sayfa daha okur."""
        video_ids: list[str] = []
        page_token: str | None = None
        old_page_seen = False

        while True:
            params: dict[str, Any] = {
                "part": "contentDetails,snippet",
                "playlistId": playlist_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("playlistItems", params)
            items = data.get("items", [])
            if not items:
                break

            page_was_old = bool(before_utc) and all(
                self._item_published_at(item) is not None
                and self._item_published_at(item) < before_utc
                for item in items
            )
            for item in items:
                video_id = item.get("contentDetails", {}).get("videoId")
                if video_id:
                    video_ids.append(str(video_id))

            if old_page_seen or (page_was_old and not data.get("nextPageToken")):
                break
            if page_was_old:
                old_page_seen = True
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return video_ids

    @staticmethod
    def _item_published_at(item: dict[str, Any]):
        from datetime import datetime

        value = item.get("contentDetails", {}).get("videoPublishedAt") or item.get("snippet", {}).get("publishedAt")
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def get_videos(self, video_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = list(dict.fromkeys(video_ids))
        result: list[dict[str, Any]] = []
        for start in range(0, len(ids), 50):
            data = self._get(
                "videos",
                {
                    "part": "snippet,contentDetails,liveStreamingDetails",
                    "id": ",".join(ids[start : start + 50]),
                },
            )
            result.extend(data.get("items", []))
        return result

    def get_channel_videos(self, channel: dict[str, Any], before_utc=None) -> list[dict[str, Any]]:
        channel_id = self.resolve_channel_id(channel)
        playlist_id = self.uploads_playlist_id(channel_id)
        ids = self.list_upload_ids(playlist_id, before_utc=before_utc)
        return self.get_videos(ids)
