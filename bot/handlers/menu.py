from datetime import timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import Menu
from bot.models import Couple, Event, Task, TaskStatus, User
from bot.services.timeutil import fmt_local, local_to_utc, now_utc, utc_to_local

router = Router()


async def build_digest(session: AsyncSession, couple: Couple) -> str:
    """Шапка меню: ближайшее событие сегодня + открытые поручения."""
    local_now = utc_to_local(now_utc(), couple.timezone)
    day_start = local_to_utc(local_now.replace(hour=0, minute=0, second=0, microsecond=0), couple.timezone)
    day_end = day_start + timedelta(days=1)
    event = (await session.execute(
        select(Event).where(
            Event.couple_id == couple.id,
            Event.starts_at_utc >= now_utc(),
            Event.starts_at_utc < day_end,
        ).order_by(Event.starts_at_utc).limit(1)
    )).scalar_one_or_none()
    open_tasks = (await session.execute(
        select(func.count()).select_from(Task).where(
            Task.couple_id == couple.id,
            Task.status.in_([TaskStatus.sent, TaskStatus.accepted]),
        )
    )).scalar_one()

    parts = []
    if event is not None:
        parts.append(texts.DIGEST_EVENT.format(event=f"{event.title} {fmt_local(event.starts_at_utc, couple.timezone)}"))
    if open_tasks:
        parts.append(texts.DIGEST_TASKS.format(n=open_tasks))
    return "\n".join(parts) if parts else texts.DIGEST_EMPTY


async def menu_text(session: AsyncSession, user: User, couple: Couple, partner: User | None) -> str:
    names = f"👩‍❤️‍👨 {user.name}" + (f" и {partner.name}" if partner else "")
    return texts.MENU_TITLE.format(names=names, digest=await build_digest(session, couple))


async def show_menu(message: Message, session: AsyncSession, user: User, couple: Couple, partner: User | None):
    await message.answer(await menu_text(session, user, couple, partner), reply_markup=keyboards.main_menu())


@router.callback_query(Menu.filter(F.section == "home"))
async def go_home(query: CallbackQuery, session: AsyncSession, user: User, couple: Couple | None, partner: User | None):
    if couple is None:
        await query.message.edit_text(texts.WELCOME_NO_PAIR, reply_markup=keyboards.invite_start())
    else:
        await query.message.edit_text(
            await menu_text(session, user, couple, partner), reply_markup=keyboards.main_menu()
        )
    await query.answer()


@router.callback_query(F.data == "noop")
async def noop(query: CallbackQuery):
    await query.answer()
