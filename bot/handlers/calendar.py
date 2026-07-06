from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import Cal, Menu, Wizard
from bot.models import Couple, Event, User
from bot.services.notify import send_to
from bot.services.reminders import schedule_event_reminders
from bot.services.timeutil import fmt_local, local_to_utc, now_utc, parse_ddmm_hhmm, parse_hhmm, utc_to_local
from bot.states import NewEvent

router = Router()


async def _event_days(session: AsyncSession, couple: Couple, year: int, month: int) -> set[int]:
    month_start = local_to_utc(datetime(year, month, 1), couple.timezone)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    month_end = local_to_utc(datetime(next_y, next_m, 1), couple.timezone)
    result = await session.execute(
        select(Event.starts_at_utc).where(
            Event.couple_id == couple.id,
            Event.starts_at_utc >= month_start,
            Event.starts_at_utc < month_end,
        )
    )
    return {utc_to_local(row[0], couple.timezone).day for row in result.all()}


async def _show_month(target_message, session: AsyncSession, couple: Couple, year: int, month: int):
    days = await _event_days(session, couple, year, month)
    await target_message.edit_text(
        keyboards.month_title(year, month),
        reply_markup=keyboards.month_grid(year, month, days),
    )


@router.callback_query(Menu.filter(F.section == "cal"))
async def calendar_open(query: CallbackQuery, session: AsyncSession, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    local_now = utc_to_local(now_utc(), couple.timezone)
    await _show_month(query.message, session, couple, local_now.year, local_now.month)
    await query.answer()


@router.callback_query(Cal.filter(F.action == "show"))
async def calendar_nav(query: CallbackQuery, callback_data: Cal, session: AsyncSession, couple: Couple | None):
    await _show_month(query.message, session, couple, callback_data.year, callback_data.month)
    await query.answer()


@router.callback_query(Cal.filter(F.action == "day"))
async def calendar_day(query: CallbackQuery, callback_data: Cal, session: AsyncSession, couple: Couple | None):
    day_start = local_to_utc(datetime(callback_data.year, callback_data.month, callback_data.day), couple.timezone)
    day_end = day_start + timedelta(days=1)
    result = await session.execute(
        select(Event).where(
            Event.couple_id == couple.id,
            Event.starts_at_utc >= day_start,
            Event.starts_at_utc < day_end,
        ).order_by(Event.starts_at_utc)
    )
    events = list(result.scalars())
    if not events:
        await query.answer(texts.EVENT_EMPTY_DAY)
        return
    lines = [f"• {fmt_local(e.starts_at_utc, couple.timezone)} {e.title}" for e in events]
    rows = [(f"🗑 {e.title}", Cal(action="del", item_id=e.id).pack()) for e in events]
    await query.message.edit_text("\n".join(lines), reply_markup=keyboards.section_list(Cal(action="new"), rows))
    await query.answer()


@router.callback_query(Cal.filter(F.action == "del"))
async def calendar_delete(query: CallbackQuery, callback_data: Cal, session: AsyncSession, couple: Couple | None):
    event = await session.get(Event, callback_data.item_id)
    if event is not None and couple is not None and event.couple_id == couple.id:
        await session.delete(event)  # Reminder уйдёт каскадом (FK ON DELETE CASCADE)
    local_now = utc_to_local(now_utc(), couple.timezone)
    await session.flush()
    await _show_month(query.message, session, couple, local_now.year, local_now.month)
    await query.answer(texts.EVENT_DELETED)


# ---------- мастер создания события ----------

@router.callback_query(Cal.filter(F.action == "new"))
async def event_new(query: CallbackQuery, state: FSMContext, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    await state.set_state(NewEvent.title)
    await query.message.answer(texts.EVENT_TITLE_PROMPT)
    await query.answer()


@router.message(NewEvent.title, F.text)
async def event_title(message: Message, state: FSMContext, couple: Couple):
    await state.update_data(title=message.text.strip()[:256])
    await state.set_state(NewEvent.date)
    local_now = utc_to_local(now_utc(), couple.timezone)
    await message.answer(
        texts.EVENT_DATE_PROMPT,
        reply_markup=keyboards.day_pick(local_now.year, local_now.month),
    )


@router.callback_query(NewEvent.date, Cal.filter(F.action == "pickdaynav"))
async def event_date_nav(query: CallbackQuery, callback_data: Cal):
    await query.message.edit_reply_markup(
        reply_markup=keyboards.day_pick(callback_data.year, callback_data.month)
    )
    await query.answer()


@router.callback_query(NewEvent.date, Cal.filter(F.action == "pickday"))
async def event_date(query: CallbackQuery, callback_data: Cal, state: FSMContext):
    await state.update_data(year=callback_data.year, month=callback_data.month, day=callback_data.day)
    await state.set_state(NewEvent.time)
    await query.message.answer(texts.EVENT_TIME_PROMPT)
    await query.answer()


@router.message(NewEvent.time, F.text)
async def event_time(message: Message, state: FSMContext, couple: Couple):
    hm = parse_hhmm(message.text)
    if hm is None:
        await message.answer(texts.EVENT_TIME_BAD)
        return
    data = await state.get_data()
    local_dt = datetime(data["year"], data["month"], data["day"], hm[0], hm[1])
    await state.update_data(starts_at_utc=local_to_utc(local_dt, couple.timezone).isoformat())
    await state.set_state(NewEvent.remind)
    await message.answer(texts.EVENT_REMIND_PROMPT, reply_markup=keyboards.remind_choice())


async def _create_event(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot, custom_utc: datetime | None,
):
    data = await state.get_data()
    event = Event(
        couple_id=couple.id, title=data["title"],
        starts_at_utc=datetime.fromisoformat(data["starts_at_utc"]), created_by=user.tg_id,
    )
    session.add(event)
    await session.flush()
    await schedule_event_reminders(session, event, couple.timezone, custom_utc)
    await state.clear()
    when = fmt_local(event.starts_at_utc, couple.timezone)
    await message.answer(texts.EVENT_CREATED.format(title=event.title, when=when))
    if partner is not None:
        delivered = await send_to(
            bot, partner.tg_id,
            texts.EVENT_CREATED_PARTNER.format(name=user.name, title=event.title, when=when),
        )
        if not delivered:
            await message.answer(texts.NOT_DELIVERED)


@router.callback_query(NewEvent.remind, Wizard.filter(F.action == "remind_default"))
async def event_remind_default(
    query: CallbackQuery, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot,
):
    await _create_event(query.message, state, session, user, couple, partner, bot, None)
    await query.answer()


@router.callback_query(NewEvent.remind, Wizard.filter(F.action == "remind_custom"))
async def event_remind_custom(query: CallbackQuery, state: FSMContext):
    await state.set_state(NewEvent.custom_remind)
    await query.message.answer(texts.EVENT_REMIND_CUSTOM_PROMPT)
    await query.answer()


@router.message(NewEvent.custom_remind, F.text)
async def event_custom_remind(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot,
):
    custom = parse_ddmm_hhmm(message.text, couple.timezone)
    if custom is None:
        await message.answer(texts.TASK_DT_BAD)
        return
    await _create_event(message, state, session, user, couple, partner, bot, custom)
