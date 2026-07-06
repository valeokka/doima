from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from bot.config import settings


class Base(DeclarativeBase):
    pass


def make_engine(db_path: str | None = None):
    url = f"sqlite+aiosqlite:///{db_path or settings.db_path}"
    eng = create_async_engine(url)

    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return eng


engine = make_engine()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(eng=None) -> None:
    from bot import models  # noqa: F401  (регистрация таблиц в Base.metadata)

    async with (eng or engine).begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
