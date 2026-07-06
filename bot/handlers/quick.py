"""Быстрые команды: /todo, /buy, /idea — для власти-пользователей."""

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import texts
from bot.models import Couple, Task, User
from bot.services.handlers_util import require_pair
from bot.services.notify import send_to
from bot.services.timeutil import now_utc

from bot.handlers.ideas import add_idea
from bot.handlers.shopping import add_items

router = Router()


@router.message(Command("todo"))
async def quick_todo(
    message: Message, command: CommandObject, session: AsyncSession,
    user: User, couple: Couple | None, partner: User | None, bot: Bot,
):
    if not await require_pair(message, couple):
        return
    text = (command.args or "").strip()
    if not text:
        await message.answer(texts.TASK_TEXT_PROMPT)
        return
    task = Task(
        couple_id=couple.id, author_tg_id=user.tg_id,
        assignee_tg_id=partner.tg_id if partner else user.tg_id,
        text=text[:512], deadline_utc=None, created_at=now_utc(),
    )
    session.add(task)
    await session.flush()
    await message.answer(texts.TASK_SENT)
    if partner is not None:
        from bot import keyboards
        await send_to(
            bot, partner.tg_id,
            texts.TASK_INCOMING.format(name=user.name, text=task.text, deadline=""),
            keyboards.task_incoming(task.id),
        )


@router.message(Command("buy"))
async def quick_buy(
    message: Message, command: CommandObject, session: AsyncSession,
    user: User, couple: Couple | None, partner: User | None, bot: Bot,
):
    if not await require_pair(message, couple):
        return
    raw = (command.args or "").strip()
    if not raw:
        await message.answer(texts.SHOPPING_PROMPT)
        return
    await add_items(raw, message, session, user, couple, partner, bot)


@router.message(Command("idea"))
async def quick_idea(
    message: Message, command: CommandObject, session: AsyncSession,
    user: User, couple: Couple | None, partner: User | None, bot: Bot,
):
    if not await require_pair(message, couple):
        return
    raw = (command.args or "").strip()
    if not raw:
        await message.answer(texts.IDEA_PROMPT)
        return
    await add_idea(raw, message, session, user, couple, partner, bot)
