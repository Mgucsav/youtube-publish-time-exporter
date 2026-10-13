"""CSV cikti yazimi ve kisa ozet."""

from __future__ import annotations

import csv
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Iterable


FIELDNAMES = [
    "kanal", "video_id", "baslik", "url", "yayin_utc", "yayin_tr", "tarih", "ay", "gun", "gun_no",
    "saat", "dakika", "kova", "hafta_sonu", "sure_sn", "format_tahmini", "format_kaynagi",
    "zaman_kaynagi", "canli_planlanan", "canli_baslangic", "canli_bitis", "cekim_zamani",
]


def write_csv(records: Iterable[dict], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def summary(records: list[dict]) -> str:
    formats = Counter(row["format_tahmini"] for row in records)
    hours = Counter(row["saat"] for row in records)
    format_text = ", ".join(f"{name}: {formats[name]}" for name in ("Shorts", "Video", "Canli", "Premiere_olasi") if formats[name]) or "yok"
    top_hours = ", ".join(f"{hour:02d}:00 ({count})" for hour, count in hours.most_common(3)) or "yok"
    return f"Toplam video: {len(records)} | Format: {format_text} | En sik 3 saat: {top_hours}"
