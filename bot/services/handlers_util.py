from aiogram.types import Message

from bot import texts
from bot.models import Couple


async def require_pair(message: Message, couple: Couple | None) -> bool:
    if couple is None:
        await message.answer(texts.NOT_PAIRED)
        return False
    return True
