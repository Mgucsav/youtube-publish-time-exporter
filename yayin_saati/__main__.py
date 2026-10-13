"""CLI: python -m yayin_saati"""

from __future__ import annotations

import argparse
import os
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

from .api import YouTubeApiClient, YouTubeApiError
from .cikti import summary, write_csv
from .donustur import build_record, date_bounds_utc, filter_records


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Gecersiz tarih: {value}. YYYY-MM-DD kullan.") from exc


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="YouTube videolarinin Turkiye saatine gore yayin zamanlarini CSV'ye aktarir.")
    p.add_argument("--kanal", required=True, help="config anahtari, @handle, veya UC... kanal ID'si; virgulle birden fazla")
    p.add_argument("--bas", type=parse_date, help="Baslangic tarihi (dahil), YYYY-MM-DD")
    p.add_argument("--bit", type=parse_date, help="Bitis tarihi (dahil), YYYY-MM-DD")
    period = p.add_mutually_exclusive_group()
    period.add_argument("--gecen-ay", action="store_true", help="Bir onceki takvim ayi")
    period.add_argument("--son-gun", type=int, metavar="N", help="Bugun dahil geriye dogru N gun")
    period.add_argument("--tum", action="store_true", help="Kanalin herkese acik tum gecmisi")
    p.add_argument("--cikti", help="Tek kanal icin cikti yolu; varsayilan cikti/ klasorudur")
    p.add_argument("--shorts-dogrula", action="store_true", help="Shorts URL'sini HEAD istegiyle kontrol et")
    p.add_argument("--config", default="config.yaml", help="Yapilandirma dosyasi")
    return p


def resolve_period(args, tz_name: str) -> tuple[date | None, date | None]:
    choices = int(args.gecen_ay) + int(args.son_gun is not None) + int(args.tum)
    manual = args.bas is not None or args.bit is not None
    if manual and choices:
        raise ValueError("Tarih araligi seceneklerinden yalnizca birini kullan.")
    if args.bas is not None and args.bit is None or args.bit is not None and args.bas is None:
        raise ValueError("--bas ve --bit birlikte verilmelidir.")
    if not manual and choices != 1:
        raise ValueError("Tam olarak bir tarih sec: --bas/--bit, --gecen-ay, --son-gun N veya --tum.")
    if args.bas and args.bit and args.bas > args.bit:
        raise ValueError("--bas, --bit tarihinden sonra olamaz.")
    if manual:
        return args.bas, args.bit
    today = datetime.now(ZoneInfo(tz_name)).date()
    if args.tum:
        return None, None
    if args.son_gun is not None:
        if args.son_gun <= 0:
            raise ValueError("--son-gun pozitif bir sayi olmali.")
        return today - timedelta(days=args.son_gun - 1), today
    first_this_month = today.replace(day=1)
    previous_last = first_this_month - timedelta(days=1)
    return previous_last.replace(day=1), previous_last


def load_config(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    config.setdefault("saat_dilimi", "Europe/Istanbul")
    config.setdefault("kanallar", {})
    config.setdefault("kovalar", [])
    config.setdefault("shorts_esik_sn", 180)
    if not config["kovalar"]:
        raise ValueError("config.yaml icinde en az bir saat kovasi tanimlanmali.")
    return config


def channel_specs(selection: str, configured: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    result = []
    for token in (part.strip() for part in selection.split(",")):
        if not token:
            raise ValueError("--kanal icinde bos bir secim var.")
        if token in configured:
            spec = dict(configured[token])
            result.append((token, spec))
        elif token.startswith("@"):
            result.append((token.lstrip("@").lower(), {"ad": token, "handle": token}))
        elif token.startswith("UC"):
            result.append((token, {"ad": token, "id": token}))
        else:
            known = ", ".join(configured) or "yok"
            raise ValueError(f"Kanal bulunamadi: {token}. Kayitli kanallar: {known}. @handle da kullanabilirsin.")
    return result


def shorts_head_checker():
    import time
    import requests

    last_request = [0.0]

    def check(video_id: str) -> bool:
        elapsed = time.monotonic() - last_request[0]
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        last_request[0] = time.monotonic()
        response = requests.head(f"https://www.youtube.com/shorts/{video_id}", allow_redirects=False, timeout=10)
        return response.status_code == 200

    return check


def output_path(args, key: str, start: date | None, end: date | None, multiple: bool) -> Path:
    if args.cikti:
        if multiple:
            base = Path(args.cikti)
            if base.suffix.lower() == ".csv":
                return base.with_name(f"{base.stem}_{key}{base.suffix}")
            return base / f"{key}_yayin_saatleri.csv"
        return Path(args.cikti)
    start_text, end_text = (start.isoformat() if start else "tum"), (end.isoformat() if end else "bugune")
    return Path("cikti") / f"{key}_yayin_saatleri_{start_text}_{end_text}.csv"


def run(args) -> int:
    config = load_config(args.config)
    tz_name = config["saat_dilimi"]
    start, end = resolve_period(args, tz_name)
    channels = channel_specs(args.kanal, config["kanallar"])
    api_key = os.getenv("YT_API_KEY", "")
    client = YouTubeApiClient(api_key)
    before_utc, _ = date_bounds_utc(start, end, tz_name)
    checker = shorts_head_checker() if args.shorts_dogrula else None
    captured_at = datetime.now(ZoneInfo(tz_name))
    all_channel_records: dict[str, list[dict]] = {}

    # Butun veri yazma islemi, API cekimleri tamamlandiktan sonra yapilir.
    # Boylece kota/agir hata durumunda yarim CSV kalmaz.
    for key, channel in channels:
        print(f"{key}: videolar aliniyor...")
        raw_items = client.get_channel_videos(channel, before_utc=before_utc)
        records = []
        for item in raw_items:
            record = build_record(
                item, key, tz_name, config["kovalar"], int(config["shorts_esik_sn"]), checker, captured_at
            )
            if record:
                records.append(record)
        all_channel_records[key] = filter_records(records, start, end)

    multiple = len(channels) > 1
    for key, _ in channels:
        records = all_channel_records[key]
        destination = write_csv(records, output_path(args, key, start, end, multiple))
        print(f"{summary(records)} | Cikti: {destination}")
    return 0


def main() -> int:
    args = parser().parse_args()
    load_dotenv()
    try:
        return run(args)
    except (ValueError, YouTubeApiError, OSError) as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
