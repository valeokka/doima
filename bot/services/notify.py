import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

log = logging.getLogger(__name__)


async def send_to(bot: Bot, tg_id: int, text: str, kb: InlineKeyboardMarkup | None = None) -> bool:
    """Доставка пользователю. Блокировка бота не роняет действие инициатора."""
    try:
        await bot.send_message(tg_id, text, reply_markup=kb)
        return True
    except TelegramForbiddenError:
        log.warning("delivery failed: bot blocked by %s", tg_id)
        return False
    except TelegramAPIError:
        log.exception("delivery failed to %s", tg_id)
        return False
