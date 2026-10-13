"""YouTube API cevaplarini analiz CSV satirlarina donusturur."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo


TR_DAYS = ("Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar")
_DURATION_RE = re.compile(r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$")


def parse_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = _DURATION_RE.fullmatch(value)
    if not match:
        return None
    parts = {key: int(raw or 0) for key, raw in match.groupdict().items()}
    return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def utc_to_tr(value: str | datetime, tz_name: str = "Europe/Istanbul") -> datetime:
    utc_value = parse_utc(value) if isinstance(value, str) else value.astimezone(timezone.utc)
    return utc_value.astimezone(ZoneInfo(tz_name))


def date_bounds_utc(start: date | None, end: date | None, tz_name: str = "Europe/Istanbul"):
    """TR gun baslangic ve bitisini UTC datetime olarak verir."""
    tz = ZoneInfo(tz_name)
    start_utc = datetime.combine(start, time.min, tzinfo=tz).astimezone(timezone.utc) if start else None
    end_utc = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc) if end else None
    return start_utc, end_utc


def bucket_for(hour: int, buckets: Iterable[dict[str, Any]]) -> str:
    for bucket in buckets:
        if int(bucket["bas"]) <= hour < int(bucket["bit"]):
            return str(bucket["ad"])
    raise ValueError(f"Saat kovasi kapsami disinda: {hour}")


def live_times(live: dict[str, Any] | None, tz_name: str):
    if not live:
        return None, None, None, None
    if live.get("actualStartTime"):
        source = "actualStartTime"
        selected = live["actualStartTime"]
    elif live.get("scheduledStartTime"):
        source = "scheduledStartTime"
        selected = live["scheduledStartTime"]
    else:
        source = "publishedAt"
        selected = None
    planned = utc_to_tr(live["scheduledStartTime"], tz_name) if live.get("scheduledStartTime") else None
    started = utc_to_tr(live["actualStartTime"], tz_name) if live.get("actualStartTime") else None
    ended = utc_to_tr(live["actualEndTime"], tz_name) if live.get("actualEndTime") else None
    return selected, planned, started, ended


def classify_format(
    item: dict[str, Any],
    duration_seconds: int | None,
    shorts_threshold: int,
    shorts_checker: Callable[[str], bool] | None = None,
):
    live = item.get("liveStreamingDetails")
    if live:
        stream_start = live.get("actualStartTime")
        stream_end = live.get("actualEndTime")
        stream_seconds = None
        if stream_start and stream_end:
            stream_seconds = (parse_utc(stream_end) - parse_utc(stream_start)).total_seconds()
        if duration_seconds is not None and duration_seconds <= 7200 and duration_seconds > 0 and stream_seconds is not None:
            if abs(stream_seconds - duration_seconds) <= duration_seconds * 0.10:
                return "Premiere_olasi", "canli_alani"
        return "Canli", "canli_alani"

    video_id = item.get("id", "")
    if shorts_checker and video_id:
        try:
            if shorts_checker(video_id):
                return "Shorts", "url_kontrol"
            return "Video", "url_kontrol"
        except Exception:
            pass
    if duration_seconds is not None and duration_seconds <= shorts_threshold:
        return "Shorts", "sure_esigi"
    return "Video", "sure_esigi"


def build_record(
    item: dict[str, Any],
    channel_key: str,
    tz_name: str,
    buckets: Iterable[dict[str, Any]],
    shorts_threshold: int = 180,
    shorts_checker: Callable[[str], bool] | None = None,
    captured_at: datetime | None = None,
) -> dict[str, Any] | None:
    snippet = item.get("snippet", {})
    details = item.get("contentDetails", {})
    live = item.get("liveStreamingDetails")
    selected_live, planned, started, ended = live_times(live, tz_name)
    publish_value = selected_live or snippet.get("publishedAt")
    if not publish_value:
        return None
    publish_utc = parse_utc(publish_value)
    publish_tr = publish_utc.astimezone(ZoneInfo(tz_name))
    duration_seconds = parse_duration(details.get("duration"))
    format_guess, format_source = classify_format(item, duration_seconds, shorts_threshold, shorts_checker)
    captured = captured_at or datetime.now(ZoneInfo(tz_name))
    return {
        "kanal": channel_key,
        "video_id": str(item.get("id", "")),
        "baslik": snippet.get("title", ""),
        "url": f"https://youtu.be/{item.get('id', '')}",
        "yayin_utc": publish_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "yayin_tr": publish_tr.strftime("%Y-%m-%d %H:%M:%S"),
        "tarih": publish_tr.strftime("%Y-%m-%d"),
        "ay": publish_tr.strftime("%Y-%m"),
        "gun": TR_DAYS[publish_tr.weekday()],
        "gun_no": publish_tr.isoweekday(),
        "saat": publish_tr.hour,
        "dakika": publish_tr.minute,
        "kova": bucket_for(publish_tr.hour, buckets),
        "hafta_sonu": int(publish_tr.weekday() >= 5),
        "sure_sn": duration_seconds,
        "format_tahmini": format_guess,
        "format_kaynagi": format_source,
        "zaman_kaynagi": selected_live and ("actualStartTime" if live.get("actualStartTime") else "scheduledStartTime") or "publishedAt",
        "canli_planlanan": planned.strftime("%Y-%m-%d %H:%M:%S") if planned else "",
        "canli_baslangic": started.strftime("%Y-%m-%d %H:%M:%S") if started else "",
        "canli_bitis": ended.strftime("%Y-%m-%d %H:%M:%S") if ended else "",
        "cekim_zamani": captured.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S"),
    }


def filter_records(records: Iterable[dict[str, Any]], start: date | None, end: date | None) -> list[dict[str, Any]]:
    result = []
    for record in records:
        record_date = date.fromisoformat(record["tarih"])
        if start and record_date < start:
            continue
        if end and record_date > end:
            continue
        result.append(record)
    return sorted(result, key=lambda row: row["yayin_tr"])
