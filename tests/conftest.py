import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db import Base
from bot import models  # noqa: F401 — регистрация таблиц
from bot.models import Couple, User
from bot.services.timeutil import now_utc


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(eng.sync_engine, "connect")
    def _fk_on(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def couple(session):
    c = Couple(timezone="Europe/Moscow", created_at=now_utc())
    session.add(c)
    await session.flush()
    session.add_all([
        User(tg_id=101, name="Маша", couple_id=c.id),
        User(tg_id=202, name="Дима", couple_id=c.id),
    ])
    await session.commit()
    return c


class FakeBot:
    """Мини-двойник aiogram.Bot: копит отправленные сообщения."""

    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text))
