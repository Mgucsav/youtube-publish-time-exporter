from datetime import date

from yayin_saati.donustur import bucket_for, filter_records, parse_duration, utc_to_tr


def test_parse_duration():
    assert parse_duration("PT45S") == 45
    assert parse_duration("PT1H24M16S") == 5056
    assert parse_duration("P0D") == 0
    assert parse_duration("") is None


def test_utc_to_turkey_rolls_to_next_day():
    converted = utc_to_tr("2026-09-30T22:30:00Z")
    assert converted.strftime("%Y-%m-%d %H:%M:%S") == "2026-10-01 01:30:00"


def test_bucket_boundaries():
    buckets = [
        {"ad": "Aksam", "bas": 17, "bit": 20},
        {"ad": "Prime", "bas": 20, "bit": 23},
        {"ad": "Gece_gec", "bas": 23, "bit": 24},
    ]
    assert bucket_for(20, buckets) == "Prime"
    assert bucket_for(19, buckets) == "Aksam"
    assert bucket_for(23, buckets) == "Gece_gec"


def test_tr_date_filter_excludes_utc_late_video():
    records = [{"tarih": "2026-10-01", "yayin_tr": "2026-10-01 01:30:00"}]
    assert filter_records(records, date(2026, 9, 1), date(2026, 9, 30)) == []
