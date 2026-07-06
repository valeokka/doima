from datetime import datetime

from bot.services.timeutil import fmt_local, local_to_utc, parse_ddmm_hhmm, parse_hhmm, utc_to_local


def test_roundtrip_moscow():
    local = datetime(2026, 7, 10, 19, 0)
    utc = local_to_utc(local, "Europe/Moscow")
    assert utc.hour == 16  # МСК = UTC+3
    assert utc_to_local(utc, "Europe/Moscow") == local


def test_parse_ddmm_hhmm_future():
    utc = parse_ddmm_hhmm("31.12 23:00", "Europe/Moscow", base_year=2026)
    assert utc == local_to_utc(datetime(2026, 12, 31, 23, 0), "Europe/Moscow")


def test_parse_ddmm_hhmm_invalid():
    assert parse_ddmm_hhmm("не дата", "Europe/Moscow") is None
    assert parse_ddmm_hhmm("40.15 99:99", "Europe/Moscow") is None


def test_parse_hhmm():
    assert parse_hhmm("19:00") == (19, 0)
    assert parse_hhmm("24:00") is None
    assert parse_hhmm("abc") is None


def test_fmt_local():
    utc = local_to_utc(datetime(2026, 7, 10, 19, 0), "Europe/Moscow")
    assert fmt_local(utc, "Europe/Moscow") == "10.07 19:00"
