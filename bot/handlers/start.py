from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import Invite, PairCb, Tz
from bot.handlers.menu import show_menu
from bot.models import Couple, User
from bot.services import pairing
from bot.services.notify import send_to

router = Router()


@router.message(CommandStart(deep_link=True))
async def start_with_code(
    message: Message, command: CommandObject, session: AsyncSession, user: User, couple: Couple | None
):
    code = command.args or ""
    if couple is not None:
        await message.answer(texts.ALREADY_PAIRED)
        return
    check = await pairing.check_invitation(session, code, user.tg_id)
    if not check.ok:
        await message.answer({
            "self": texts.INVITE_SELF,
            "author_paired": texts.AUTHOR_ALREADY_PAIRED,
        }.get(check.error, texts.INVITE_INVALID))
        return
    await message.answer(
        texts.INVITE_CONFIRM.format(name=check.author.name),
        reply_markup=keyboards.invite_confirm(code),
    )


@router.message(CommandStart())
async def start_plain(message: Message, session: AsyncSession, user: User, couple: Couple | None, partner: User | None):
    if couple is None:
        await message.answer(texts.WELCOME_NO_PAIR, reply_markup=keyboards.invite_start())
    else:
        await show_menu(message, session, user, couple, partner)


@router.callback_query(PairCb.filter(F.action == "invite"))
async def make_invite(query: CallbackQuery, session: AsyncSession, user: User, couple: Couple | None, bot: Bot):
    if couple is not None:
        await query.answer(texts.ALREADY_PAIRED, show_alert=True)
        return
    inv = await pairing.create_invitation(session, user)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={inv.code}"
    await query.message.answer(texts.INVITE_LINK_TEXT.format(link=link))
    await query.answer()


@router.callback_query(Invite.filter(F.action == "decline"))
async def invite_decline(query: CallbackQuery, callback_data: Invite, session: AsyncSession, user: User, bot: Bot):
    check = await pairing.check_invitation(session, callback_data.code, user.tg_id)
    await query.message.edit_text(texts.INVITE_DECLINED)
    if check.ok and check.author is not None:
        await send_to(bot, check.author.tg_id, texts.INVITE_DECLINED_AUTHOR.format(name=user.name))
    await query.answer()


@router.callback_query(Invite.filter(F.action == "accept"))
async def invite_accept(query: CallbackQuery, callback_data: Invite, session: AsyncSession, user: User, state: FSMContext):
    check = await pairing.check_invitation(session, callback_data.code, user.tg_id)
    if not check.ok:
        await query.message.edit_text({
            "self": texts.INVITE_SELF,
            "author_paired": texts.AUTHOR_ALREADY_PAIRED,
        }.get(check.error, texts.INVITE_INVALID))
        await query.answer()
        return
    await state.update_data(invite_code=callback_data.code)
    await query.message.edit_text(texts.CHOOSE_TZ, reply_markup=keyboards.tz_choice())
    await query.answer()


@router.callback_query(Tz.filter())
async def tz_chosen(
    query: CallbackQuery, callback_data: Tz, session: AsyncSession, user: User, state: FSMContext, bot: Bot
):
    data = await state.get_data()
    code = data.get("invite_code")
    if not code:
        await query.answer(texts.INVITE_INVALID, show_alert=True)
        return
    tz = keyboards.POPULAR_TZS[callback_data.idx]
    result = await pairing.accept_invitation(session, code, user, tz)
    if not result.ok:
        await query.message.edit_text({
            "self": texts.INVITE_SELF,
            "already_paired": texts.ALREADY_PAIRED,
            "author_paired": texts.AUTHOR_ALREADY_PAIRED,
        }.get(result.error, texts.INVITE_INVALID))
        await query.answer()
        return
    await state.clear()
    await query.message.edit_text(texts.PAIR_CREATED, reply_markup=keyboards.main_menu())
    delivered = await send_to(
        bot, result.author.tg_id,
        texts.PAIR_CREATED_PARTNER.format(name=user.name), keyboards.main_menu(),
    )
    if not delivered:
        await query.message.answer(texts.NOT_DELIVERED)
    await query.answer()
