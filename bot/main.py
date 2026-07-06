import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.db import async_session, init_db
from bot.handlers import calendar, dates, gifts, ideas, menu, pair, quick, shopping, start, tasks
from bot.middlewares import DbSessionMiddleware
from bot.services.reminders import reminder_loop

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    if not settings.bot_token:
        raise SystemExit("BOT_TOKEN не задан: создайте .env по образцу .env.example")

    await init_db()

    bot = Bot(settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())  # незавершённый мастер при рестарте сбрасывается (v1)
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.include_routers(
        start.router, menu.router, tasks.router, shopping.router,
        calendar.router, ideas.router, dates.router, gifts.router,
        pair.router, quick.router,
    )

    # первый тик цикла — startup-scan: отправляет всё просроченное за время простоя
    reminders = asyncio.create_task(reminder_loop(async_session, bot))
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()


if __name__ == "__main__":
    asyncio.run(main())
