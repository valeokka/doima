from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import Cal, IdeaCb, Menu
from bot.models import Couple, Event, User, WishItem
from bot.services.notify import send_to
from bot.services.reminders import schedule_event_reminders
from bot.services.timeutil import fmt_local, local_to_utc, now_utc, parse_hhmm, utc_to_local
from bot.states import NewIdea, PlanIdea

router = Router()


@router.callback_query(Menu.filter(F.section == "ideas"))
async def ideas_list(query: CallbackQuery, session: AsyncSession, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    result = await session.execute(
        select(WishItem).where(WishItem.couple_id == couple.id).order_by(WishItem.id)
    )
    items = list(result.scalars())
    rows = [(f"💡 {i.text} → {texts.IDEA_SCHEDULE_BTN}", IdeaCb(action="plan", item_id=i.id).pack()) for i in items]
    text = texts.BTN_IDEAS if items else texts.IDEA_EMPTY
    await query.message.edit_text(text, reply_markup=keyboards.section_list(IdeaCb(action="add"), rows))
    await query.answer()


@router.callback_query(IdeaCb.filter(F.action == "add"))
async def idea_add(query: CallbackQuery, state: FSMContext, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    await state.set_state(NewIdea.text)
    await query.message.answer(texts.IDEA_PROMPT)
    await query.answer()


async def add_idea(
    raw: str, message: Message, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot,
):
    text = raw.strip()[:256]
    session.add(WishItem(couple_id=couple.id, text=text, created_by=user.tg_id))
    await message.answer(texts.IDEA_ADDED)
    if partner is not None:
        await send_to(bot, partner.tg_id, texts.IDEA_ADDED_PARTNER.format(name=user.name, text=text))


@router.message(NewIdea.text, F.text)
async def idea_text(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple | None, partner: User | None, bot: Bot,
):
    await add_idea(message.text, message, session, user, couple, partner, bot)
    await state.clear()


# ---------- идея → событие ----------

@router.callback_query(IdeaCb.filter(F.action == "plan"))
async def idea_plan(query: CallbackQuery, callback_data: IdeaCb, state: FSMContext, couple: Couple | None):
    await state.set_state(PlanIdea.date)
    await state.update_data(idea_id=callback_data.item_id)
    local_now = utc_to_local(now_utc(), couple.timezone)
    await query.message.answer(
        texts.EVENT_DATE_PROMPT,
        reply_markup=keyboards.day_pick(local_now.year, local_now.month),
    )
    await query.answer()


@router.callback_query(PlanIdea.date, Cal.filter(F.action == "pickdaynav"))
async def idea_plan_nav(query: CallbackQuery, callback_data: Cal):
    await query.message.edit_reply_markup(
        reply_markup=keyboards.day_pick(callback_data.year, callback_data.month)
    )
    await query.answer()


@router.callback_query(PlanIdea.date, Cal.filter(F.action == "pickday"))
async def idea_plan_date(query: CallbackQuery, callback_data: Cal, state: FSMContext):
    await state.update_data(year=callback_data.year, month=callback_data.month, day=callback_data.day)
    await state.set_state(PlanIdea.time)
    await query.message.answer(texts.EVENT_TIME_PROMPT)
    await query.answer()


@router.message(PlanIdea.time, F.text)
async def idea_plan_time(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot,
):
    hm = parse_hhmm(message.text)
    if hm is None:
        await message.answer(texts.EVENT_TIME_BAD)
        return
    data = await state.get_data()
    idea = await session.get(WishItem, data["idea_id"])
    if idea is None:
        await state.clear()
        await message.answer(texts.TASK_ALREADY_CHANGED)
        return
    local_dt = datetime(data["year"], data["month"], data["day"], hm[0], hm[1])
    event = Event(
        couple_id=couple.id, title=idea.text,
        starts_at_utc=local_to_utc(local_dt, couple.timezone), created_by=user.tg_id,
    )
    session.add(event)
    await session.delete(idea)
    await session.flush()
    await schedule_event_reminders(session, event, couple.timezone, None)
    await state.clear()
    when = fmt_local(event.starts_at_utc, couple.timezone)
    await message.answer(texts.IDEA_SCHEDULED + f"\n{event.title} — {when}")
    if partner is not None:
        await send_to(
            bot, partner.tg_id,
            texts.EVENT_CREATED_PARTNER.format(name=user.name, title=event.title, when=when),
        )
