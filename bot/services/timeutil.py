"""Время: в БД — naive UTC; конвертация в пояс пары только на границах."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_to_utc(local_naive: datetime, tz: str) -> datetime:
    aware = local_naive.replace(tzinfo=ZoneInfo(tz))
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(utc_naive: datetime, tz: str) -> datetime:
    aware = utc_naive.replace(tzinfo=timezone.utc)
    return aware.astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def fmt_local(utc_naive: datetime, tz: str) -> str:
    return utc_to_local(utc_naive, tz).strftime("%d.%m %H:%M")


def parse_ddmm_hhmm(text: str, tz: str, base_year: int | None = None) -> datetime | None:
    """«ДД.ММ ЧЧ:ММ» в поясе пары -> naive UTC. Прошедшая дата уходит на следующий год."""
    try:
        dm, hm = text.strip().split()
        day, month = (int(x) for x in dm.split("."))
        hour, minute = (int(x) for x in hm.split(":"))
        year = base_year or utc_to_local(now_utc(), tz).year
        local = datetime(year, month, day, hour, minute)
        if base_year is None and local_to_utc(local, tz) < now_utc():
            local = local.replace(year=year + 1)
        return local_to_utc(local, tz)
    except (ValueError, IndexError):
        return None


def parse_hhmm(text: str) -> tuple[int, int] | None:
    try:
        hour, minute = (int(x) for x in text.strip().split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            return None
        return hour, minute
    except (ValueError, IndexError):
        return None
