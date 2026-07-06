from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import Menu, ShopCb
from bot.models import Couple, ShoppingItem, User
from bot.services.notify import send_to
from bot.states import NewShopping

router = Router()


async def _render(session: AsyncSession, couple: Couple):
    result = await session.execute(
        select(ShoppingItem).where(ShoppingItem.couple_id == couple.id)
        .order_by(ShoppingItem.bought, ShoppingItem.id)
    )
    items = list(result.scalars())
    rows = [
        (("✅ " if i.bought else "⬜ ") + i.text,
         "noop" if i.bought else ShopCb(action="buy", item_id=i.id).pack())
        for i in items
    ]
    text = texts.BTN_SHOPPING if items else texts.SHOPPING_EMPTY
    return text, keyboards.section_list(ShopCb(action="add"), rows)


@router.callback_query(Menu.filter(F.section == "shop"))
async def shopping_list(query: CallbackQuery, session: AsyncSession, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    text, kb = await _render(session, couple)
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer()


@router.callback_query(ShopCb.filter(F.action == "add"))
async def shopping_add(query: CallbackQuery, state: FSMContext, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    await state.set_state(NewShopping.items)
    await query.message.answer(texts.SHOPPING_PROMPT)
    await query.answer()


async def add_items(
    raw: str, message: Message, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot,
):
    items = [part.strip()[:256] for part in raw.split(",") if part.strip()]
    for text in items:
        session.add(ShoppingItem(couple_id=couple.id, text=text, created_by=user.tg_id))
    await message.answer(texts.SHOPPING_ADDED)
    if partner is not None and items:
        await send_to(bot, partner.tg_id, texts.SHOPPING_ADDED_PARTNER.format(name=user.name, items=", ".join(items)))


@router.message(NewShopping.items, F.text)
async def shopping_items(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple | None, partner: User | None, bot: Bot,
):
    await add_items(message.text, message, session, user, couple, partner, bot)
    await state.clear()


@router.callback_query(ShopCb.filter(F.action == "buy"))
async def shopping_buy(query: CallbackQuery, callback_data: ShopCb, session: AsyncSession, couple: Couple | None):
    res = await session.execute(
        update(ShoppingItem)
        .where(ShoppingItem.id == callback_data.item_id, ShoppingItem.bought.is_(False))
        .values(bought=True)
    )
    if res.rowcount != 1:
        await query.answer(texts.TASK_ALREADY_CHANGED)
        return
    text, kb = await _render(session, couple)
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer(texts.SHOPPING_BOUGHT)
