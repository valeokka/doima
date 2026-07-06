from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import Menu, PairCb
from bot.models import Couple, User
from bot.services import pairing
from bot.services.notify import send_to
from bot.services.timeutil import now_utc

router = Router()


@router.callback_query(Menu.filter(F.section == "pair"))
async def pair_info(query: CallbackQuery, user: User, couple: Couple | None, partner: User | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    days = (now_utc() - couple.created_at).days
    await query.message.edit_text(
        texts.PAIR_INFO.format(a=user.name, b=partner.name if partner else "?", days=days, tz=couple.timezone),
        reply_markup=keyboards.pair_menu(),
    )
    await query.answer()


@router.callback_query(PairCb.filter(F.action == "unpair"))
async def unpair_ask(query: CallbackQuery, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    await query.message.edit_text(texts.UNPAIR_CONFIRM, reply_markup=keyboards.unpair_confirm())
    await query.answer()


@router.callback_query(PairCb.filter(F.action == "unpair_yes"))
async def unpair_do(
    query: CallbackQuery, session: AsyncSession, user: User, couple: Couple | None, partner: User | None, bot: Bot
):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    await pairing.unpair(session, couple.id)
    await query.message.edit_text(texts.UNPAIRED)
    if partner is not None:
        await send_to(bot, partner.tg_id, texts.UNPAIRED_PARTNER.format(name=user.name))
    await query.answer()
