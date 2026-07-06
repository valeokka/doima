from datetime import datetime, timedelta

from bot.models import (
    Audience,
    Event,
    ImportantDate,
    Reminder,
    ReminderStatus,
    Task,
    TaskStatus,
)
from bot.services import reminders
from bot.services.reminders import (
    next_yearly_fire_utc,
    process_due,
    rules_for_event,
    rules_for_task,
    schedule_event_reminders,
    schedule_important_date,
    schedule_task_reminders,
)
from bot.services.timeutil import local_to_utc, now_utc, utc_to_local

from sqlalchemy import select

from tests.conftest import FakeBot


def test_event_defaults():
    start = datetime(2026, 7, 10, 16, 0)
    rules = rules_for_event(start, None)
    assert (start - timedelta(days=1), "day_before") in rules
    assert (start - timedelta(hours=2), "2h_before") in rules


def test_event_custom_replaces_defaults():
    start = datetime(2026, 7, 10, 16, 0)
    custom = datetime(2026, 7, 9, 12, 0)
    rules = rules_for_event(start, custom)
    assert rules == [(custom, "custom")]


def test_task_rules_morning_of_deadline_day():
    # дедлайн 18:00 МСК → напоминание в 09:00 МСК того же дня
    deadline = local_to_utc(datetime(2026, 7, 15, 18, 0), "Europe/Moscow")
    rules = dict((k, v) for v, k in rules_for_task(deadline, "Europe/Moscow"))
    day_local = utc_to_local(rules["deadline_day"], "Europe/Moscow")
    assert (day_local.hour, day_local.minute) == (9, 0)
    assert rules["escalation"] == deadline + timedelta(hours=1)


def test_task_rules_early_deadline_falls_back():
    # дедлайн 08:00 — утро 09:00 позже дедлайна, откат на «за 2 часа»
    deadline = local_to_utc(datetime(2026, 7, 15, 8, 0), "Europe/Moscow")
    rules = dict((k, v) for v, k in rules_for_task(deadline, "Europe/Moscow"))
    assert rules["deadline_day"] == deadline - timedelta(hours=2)


def test_no_rules_without_deadline():
    assert rules_for_task(None, "Europe/Moscow") == []


def test_yearly_dst_recalculation():
    """DST-корректность: локальные 09:00 дают разный UTC-сдвиг зимой и летом."""
    from datetime import date, time

    tz = "Europe/Berlin"  # CET/CEST — есть переход
    after = local_to_utc(datetime(2026, 1, 1, 0, 0), tz)
    summer = next_yearly_fire_utc(date(2020, 7, 15), time(9, 0), tz, 0, after)
    winter = next_yearly_fire_utc(date(2020, 1, 15), time(9, 0), tz, 0, after)
    assert summer.hour == 7   # 09:00 CEST = 07:00 UTC
    assert winter.hour == 8   # 09:00 CET  = 08:00 UTC
    # и оба локально — ровно 09:00
    assert utc_to_local(summer, tz).hour == 9
    assert utc_to_local(winter, tz).hour == 9


async def test_startup_scan_sends_overdue_once(session_factory, couple):
    """Простой дольше часа: просроченное напоминание доходит ровно один раз."""
    async with session_factory() as s:
        s.add(Reminder(
            couple_id=couple.id,
            fire_at_utc=now_utc() - timedelta(hours=5),
            audience=Audience.both, text="переживший простой",
        ))
        await s.commit()

    bot = FakeBot()
    assert await process_due(session_factory, bot) == 1
    assert len(bot.sent) == 2  # обоим партнёрам
    # повторный тик идемпотентен
    assert await process_due(session_factory, bot) == 0
    assert len(bot.sent) == 2


async def test_escalation_skipped_for_done_task(session_factory, session, couple):
    task = Task(
        couple_id=couple.id, author_tg_id=101, assignee_tg_id=202,
        text="купи цветы", deadline_utc=now_utc() - timedelta(hours=2),
        status=TaskStatus.done, created_at=now_utc(),
    )
    session.add(task)
    await session.flush()
    session.add(Reminder(
        couple_id=couple.id, fire_at_utc=now_utc() - timedelta(hours=1),
        audience=Audience.both, text="просрочено", task_id=task.id, is_escalation=True,
    ))
    await session.commit()

    bot = FakeBot()
    await process_due(session_factory, bot)
    assert bot.sent == []  # выполненное поручение не эскалируется


async def test_yearly_reschedules_next_year(session_factory, session, couple):
    from datetime import date, time

    idate = ImportantDate(
        couple_id=couple.id, title="Годовщина",
        local_date=date(2020, 3, 10), notify_local_time=time(9, 0),
    )
    session.add(idate)
    await session.flush()
    session.add(Reminder(
        couple_id=couple.id, fire_at_utc=now_utc() - timedelta(minutes=5),
        audience=Audience.both, text="Сегодня — Годовщина!",
        important_date_id=idate.id, reschedule_yearly=True, yearly_offset_days=0,
    ))
    await session.commit()

    bot = FakeBot()
    await process_due(session_factory, bot)

    async with session_factory() as s:
        pending = (await s.execute(
            select(Reminder).where(Reminder.status == ReminderStatus.pending)
        )).scalars().all()
    assert len(pending) == 1  # запланирован следующий год
    assert pending[0].fire_at_utc > now_utc()


async def test_schedule_event_skips_past_reminders(session, couple):
    event = Event(
        couple_id=couple.id, title="Кино",
        starts_at_utc=now_utc() + timedelta(hours=1), created_by=101,
    )
    session.add(event)
    await session.flush()
    await schedule_event_reminders(session, event, couple.timezone, None)
    await session.commit()

    result = (await session.execute(select(Reminder))).scalars().all()
    # «за день» уже в прошлом — не планируется; «за 2 часа» тоже в прошлом
    assert result == []
