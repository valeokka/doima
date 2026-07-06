from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import GiftCb, Menu
from bot.models import GiftWish, User
from bot.states import NewGift

router = Router()


@router.callback_query(Menu.filter(F.section == "gifts"))
async def gifts_menu(query: CallbackQuery):
    await query.message.edit_text(texts.BTN_GIFTS, reply_markup=keyboards.gifts_menu())
    await query.answer()


async def _wishes_of(session: AsyncSession, tg_id: int) -> list[GiftWish]:
    result = await session.execute(select(GiftWish).where(GiftWish.owner_tg_id == tg_id).order_by(GiftWish.id))
    return list(result.scalars())


@router.callback_query(GiftCb.filter(F.action == "my"))
async def gifts_my(query: CallbackQuery, session: AsyncSession, user: User):
    wishes = await _wishes_of(session, user.tg_id)
    rows = [(f"🎁 {w.text}", "noop") for w in wishes]
    text = texts.GIFT_MY_TITLE if wishes else texts.GIFT_MY_TITLE + "\n" + texts.GIFT_EMPTY
    await query.message.edit_text(text, reply_markup=keyboards.section_list(GiftCb(action="add"), rows))
    await query.answer()


@router.callback_query(GiftCb.filter(F.action == "partner"))
async def gifts_partner(query: CallbackQuery, session: AsyncSession, partner: User | None):
    """Read-only просмотр списка партнёра. Владельцу о просмотре не сообщается."""
    if partner is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    wishes = await _wishes_of(session, partner.tg_id)
    lines = [f"🎁 {w.text}" for w in wishes] or [texts.GIFT_EMPTY]
    await query.message.edit_text(
        texts.GIFT_PARTNER_TITLE.format(name=partner.name) + "\n" + "\n".join(lines),
        reply_markup=keyboards.back_home(),
    )
    await query.answer()


@router.callback_query(GiftCb.filter(F.action == "add"))
async def gift_add(query: CallbackQuery, state: FSMContext):
    await state.set_state(NewGift.text)
    await query.message.answer(texts.GIFT_PROMPT)
    await query.answer()


@router.message(NewGift.text, F.text)
async def gift_text(message: Message, state: FSMContext, session: AsyncSession, user: User):
    session.add(GiftWish(owner_tg_id=user.tg_id, text=message.text.strip()[:256]))
    await state.clear()
    await message.answer(texts.GIFT_ADDED)
