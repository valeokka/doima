"""Инжект user/couple/partner в хендлеры по ключам data."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.db import async_session
from bot.models import Couple
from bot.services.pairing import get_or_create_user, partner_of


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or async_session

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        async with self.session_factory() as session:
            data["session"] = session
            if tg_user is not None:
                user = await get_or_create_user(session, tg_user.id, tg_user.full_name)
                data["user"] = user
                data["couple"] = await session.get(Couple, user.couple_id) if user.couple_id else None
                data["partner"] = await partner_of(session, user)
            result = await handler(event, data)
            await session.commit()
            return result
