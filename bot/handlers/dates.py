from datetime import date

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import DateCb, Menu
from bot.models import Couple, ImportantDate, User
from bot.services.notify import send_to
from bot.services.reminders import schedule_important_date
from bot.states import NewDate

router = Router()


@router.callback_query(Menu.filter(F.section == "dates"))
async def dates_list(query: CallbackQuery, session: AsyncSession, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    result = await session.execute(
        select(ImportantDate).where(ImportantDate.couple_id == couple.id).order_by(ImportantDate.id)
    )
    items = list(result.scalars())
    rows = [(f"🎂 {i.title} — {i.local_date.strftime('%d.%m')}", "noop") for i in items]
    text = texts.BTN_DATES if items else texts.DATE_EMPTY
    await query.message.edit_text(text, reply_markup=keyboards.section_list(DateCb(action="add"), rows))
    await query.answer()


@router.callback_query(DateCb.filter(F.action == "add"))
async def date_add(query: CallbackQuery, state: FSMContext, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    await state.set_state(NewDate.title)
    await query.message.answer(texts.DATE_TITLE_PROMPT)
    await query.answer()


@router.message(NewDate.title, F.text)
async def date_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip()[:256])
    await state.set_state(NewDate.date)
    await message.answer(texts.DATE_DATE_PROMPT)


@router.message(NewDate.date, F.text)
async def date_value(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot,
):
    try:
        day, month = (int(x) for x in message.text.strip().split("."))
        local_date = date(date.today().year, month, day)
    except (ValueError, IndexError):
        await message.answer(texts.DATE_BAD)
        return
    data = await state.get_data()
    idate = ImportantDate(couple_id=couple.id, title=data["title"], local_date=local_date)
    session.add(idate)
    await session.flush()
    await schedule_important_date(session, idate, couple.timezone)
    await state.clear()
    await message.answer(texts.DATE_ADDED)
    if partner is not None:
        await send_to(
            bot, partner.tg_id,
            texts.DATE_ADDED_PARTNER.format(name=user.name, title=idate.title, date=local_date.strftime("%d.%m")),
        )
