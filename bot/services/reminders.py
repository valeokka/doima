"""Движок напоминаний. Таблица Reminder — единственный источник истины.

Минутный asyncio-loop: каждый тик забирает pending с fire_at_utc <= now,
шлёт и идемпотентно помечает sent (optimistic UPDATE). Startup-scan — это
тот же первый тик: простой любой длины не теряет напоминаний.
"""

import asyncio
import logging
from datetime import date, datetime, time, timedelta

from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot import texts
from bot.models import (
    Audience,
    Couple,
    Event,
    ImportantDate,
    Reminder,
    ReminderStatus,
    Task,
    TaskStatus,
    User,
)
from bot.services.notify import send_to
from bot.services.timeutil import fmt_local, local_to_utc, now_utc, utc_to_local

log = logging.getLogger(__name__)

TICK_SECONDS = 60


# ---------- правила дефолтов (чистые функции — спека §5.7) ----------

def rules_for_event(starts_at_utc: datetime, custom_utc: datetime | None) -> list[tuple[datetime, str]]:
    """Событие: за день и за 2 часа; своё время заменяет дефолты."""
    if custom_utc is not None:
        return [(custom_utc, "custom")]
    return [
        (starts_at_utc - timedelta(days=1), "day_before"),
        (starts_at_utc - timedelta(hours=2), "2h_before"),
    ]


def rules_for_task(deadline_utc: datetime | None, tz: str) -> list[tuple[datetime, str]]:
    """Поручение с дедлайном: исполнителю — в 09:00 пояса пары в день дедлайна
    (если это уже прошло или позже дедлайна — за 2 часа до него);
    эскалация обоим — через час после просрочки."""
    if deadline_utc is None:
        return []
    local_deadline = utc_to_local(deadline_utc, tz)
    morning = local_to_utc(datetime.combine(local_deadline.date(), time(9, 0)), tz)
    day_fire = morning if morning < deadline_utc else deadline_utc - timedelta(hours=2)
    return [
        (day_fire, "deadline_day"),
        (deadline_utc + timedelta(hours=1), "escalation"),
    ]


def next_yearly_fire_utc(local_date: date, notify_time: time, tz: str, offset_days: int, after_utc: datetime) -> datetime:
    """Ближайшее будущее срабатывание yearly-даты со сдвигом offset_days.
    Пересчёт в поясе пары на каждый год — DST-корректно."""
    year = utc_to_local(after_utc, tz).year
    for y in (year, year + 1, year + 2):
        try:
            occurrence = date(y, local_date.month, local_date.day)
        except ValueError:  # 29 февраля в невисокосный год
            occurrence = date(y, 2, 28)
        fire_local = datetime.combine(occurrence - timedelta(days=offset_days), notify_time)
        fire_utc = local_to_utc(fire_local, tz)
        if fire_utc > after_utc:
            return fire_utc
    raise RuntimeError("unreachable")


# ---------- планирование ----------

async def schedule_event_reminders(
    session: AsyncSession, event: Event, tz: str, custom_utc: datetime | None
) -> None:
    now = now_utc()
    when = fmt_local(event.starts_at_utc, tz)
    labels = {
        "day_before": texts.REMIND_EVENT_DAY.format(title=event.title, when=when),
        "2h_before": texts.REMIND_EVENT_2H.format(title=event.title),
        "custom": texts.REMIND_CUSTOM.format(title=event.title, when=when),
    }
    for fire_at, kind in rules_for_event(event.starts_at_utc, custom_utc):
        if fire_at > now:
            session.add(Reminder(
                couple_id=event.couple_id, fire_at_utc=fire_at, audience=Audience.both,
                text=labels[kind], event_id=event.id,
            ))


async def schedule_task_reminders(session: AsyncSession, task: Task, tz: str) -> None:
    now = now_utc()
    for fire_at, kind in rules_for_task(task.deadline_utc, tz):
        if kind == "deadline_day":
            if fire_at > now:
                session.add(Reminder(
                    couple_id=task.couple_id, fire_at_utc=fire_at, audience=Audience.assignee,
                    text=texts.TASK_DEADLINE_TODAY.format(text=task.text), task_id=task.id,
                ))
        else:  # escalation — планируем всегда: _target_alive отфильтрует выполненные
            session.add(Reminder(
                couple_id=task.couple_id, fire_at_utc=fire_at, audience=Audience.both,
                text=texts.TASK_OVERDUE.format(text=task.text), task_id=task.id, is_escalation=True,
            ))


async def schedule_important_date(session: AsyncSession, idate: ImportantDate, tz: str) -> None:
    now = now_utc()
    session.add(Reminder(
        couple_id=idate.couple_id,
        fire_at_utc=next_yearly_fire_utc(idate.local_date, idate.notify_local_time, tz, 7, now),
        audience=Audience.both,
        text=texts.DATE_WEEK_BEFORE.format(title=idate.title),
        important_date_id=idate.id, reschedule_yearly=True, yearly_offset_days=7,
    ))
    session.add(Reminder(
        couple_id=idate.couple_id,
        fire_at_utc=next_yearly_fire_utc(idate.local_date, idate.notify_local_time, tz, 0, now),
        audience=Audience.both,
        text=texts.DATE_TODAY.format(title=idate.title),
        important_date_id=idate.id, reschedule_yearly=True,
    ))


# ---------- доставка ----------

async def _recipients(session: AsyncSession, reminder: Reminder) -> list[int]:
    if reminder.audience == Audience.assignee and reminder.task_id is not None:
        task = await session.get(Task, reminder.task_id)
        return [task.assignee_tg_id] if task else []
    result = await session.execute(select(User.tg_id).where(User.couple_id == reminder.couple_id))
    return [row[0] for row in result.all()]


async def _target_alive(session: AsyncSession, reminder: Reminder) -> bool:
    """Эскалация поручения не шлётся, если оно уже done/declined."""
    if reminder.task_id is not None:
        task = await session.get(Task, reminder.task_id)
        if task is None:
            return False
        if task.status in (TaskStatus.done, TaskStatus.declined):
            return False
    return True


async def process_due(session_factory: async_sessionmaker, bot: Bot) -> int:
    """Один тик: отправить всё созревшее. Возвращает число отправленных."""
    sent = 0
    async with session_factory() as session:
        result = await session.execute(
            select(Reminder).where(
                Reminder.status == ReminderStatus.pending,
                Reminder.fire_at_utc <= now_utc(),
            ).order_by(Reminder.fire_at_utc)
        )
        due = list(result.scalars())
        for reminder in due:
            # идемпотентность: помечаем sent до отправки; параллельный тик промахнётся
            res = await session.execute(
                update(Reminder)
                .where(Reminder.id == reminder.id, Reminder.status == ReminderStatus.pending)
                .values(status=ReminderStatus.sent)
            )
            if res.rowcount != 1:
                continue
            if await _target_alive(session, reminder):
                for tg_id in await _recipients(session, reminder):
                    await send_to(bot, tg_id, reminder.text)
                sent += 1
            if reminder.reschedule_yearly and reminder.important_date_id is not None:
                await _reschedule_yearly(session, reminder)
        await session.commit()
    return sent


async def _reschedule_yearly(session: AsyncSession, fired: Reminder) -> None:
    idate = await session.get(ImportantDate, fired.important_date_id)
    if idate is None or not idate.yearly:
        return
    couple = await session.get(Couple, fired.couple_id)
    if couple is None:
        return
    session.add(Reminder(
        couple_id=fired.couple_id,
        fire_at_utc=next_yearly_fire_utc(
            idate.local_date, idate.notify_local_time, couple.timezone,
            fired.yearly_offset_days, now_utc(),
        ),
        audience=Audience.both, text=fired.text,
        important_date_id=idate.id, reschedule_yearly=True,
        yearly_offset_days=fired.yearly_offset_days,
    ))


async def reminder_loop(session_factory: async_sessionmaker, bot: Bot) -> None:
    """Минутный цикл; первый тик — startup-scan (шлёт всё просроченное)."""
    while True:
        try:
            await process_due(session_factory, bot)
        except Exception:
            log.exception("reminder tick failed")
        await asyncio.sleep(TICK_SECONDS)
