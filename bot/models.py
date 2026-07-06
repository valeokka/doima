from __future__ import annotations

import enum
from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db import Base


class Couple(Base):
    __tablename__ = "couple"

    id: Mapped[int] = mapped_column(primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64))  # IANA, напр. Europe/Moscow
    created_at: Mapped[datetime] = mapped_column(DateTime)  # UTC

    users: Mapped[list[User]] = relationship(back_populates="couple")


class User(Base):
    __tablename__ = "user"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    couple_id: Mapped[int | None] = mapped_column(ForeignKey("couple.id", ondelete="SET NULL"))

    couple: Mapped[Couple | None] = relationship(back_populates="users")


class InvitationStatus(enum.StrEnum):
    pending = "pending"
    used = "used"
    cancelled = "cancelled"


class Invitation(Base):
    __tablename__ = "invitation"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    author_tg_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.tg_id", ondelete="CASCADE"))
    status: Mapped[InvitationStatus] = mapped_column(Enum(InvitationStatus), default=InvitationStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couple.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    starts_at_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_by: Mapped[int] = mapped_column(BigInteger)


class WishItem(Base):
    """Идея «куда сходить» — общий список пары, без даты."""

    __tablename__ = "wish_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couple.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(256))
    created_by: Mapped[int] = mapped_column(BigInteger)


class TaskStatus(enum.StrEnum):
    sent = "sent"
    accepted = "accepted"
    declined = "declined"
    done = "done"


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couple.id", ondelete="CASCADE"), index=True)
    author_tg_id: Mapped[int] = mapped_column(BigInteger)
    assignee_tg_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(String(512))
    deadline_utc: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.sent)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ShoppingItem(Base):
    __tablename__ = "shopping_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couple.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(256))
    bought: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(BigInteger)


class ImportantDate(Base):
    """Ежегодная дата: хранится локальная дата/время напоминания; fire_at_utc
    пересчитывается в поясе пары на каждое срабатывание (DST-корректность)."""

    __tablename__ = "important_date"

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couple.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256))
    local_date: Mapped[date] = mapped_column(Date)  # месяц/день значимы, год — год первого события
    notify_local_time: Mapped[time] = mapped_column(Time, default=time(9, 0))
    yearly: Mapped[bool] = mapped_column(Boolean, default=True)


class GiftWish(Base):
    """Личное желание-подарок: владелец редактирует, партнёр видит read-only."""

    __tablename__ = "gift_wish"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_tg_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.tg_id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(256))


class ReminderStatus(enum.StrEnum):
    pending = "pending"
    sent = "sent"
    cancelled = "cancelled"


class Audience(enum.StrEnum):
    both = "both"
    assignee = "assignee"


class Reminder(Base):
    """Единственный источник истины «когда сработать». Nullable FK с каскадом
    вместо полиморфной ссылки: удаление цели удаляет напоминание."""

    __tablename__ = "reminder"

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couple.id", ondelete="CASCADE"), index=True)
    fire_at_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[ReminderStatus] = mapped_column(Enum(ReminderStatus), default=ReminderStatus.pending, index=True)
    audience: Mapped[Audience] = mapped_column(Enum(Audience), default=Audience.both)
    text: Mapped[str] = mapped_column(String(512))

    event_id: Mapped[int | None] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))
    important_date_id: Mapped[int | None] = mapped_column(ForeignKey("important_date.id", ondelete="CASCADE"))
    # эскалация просрочки поручения: одноразовый повтор обоим
    is_escalation: Mapped[bool] = mapped_column(Boolean, default=False)
    # для yearly-дат: после отправки планируется следующий год с тем же сдвигом
    reschedule_yearly: Mapped[bool] = mapped_column(Boolean, default=False)
    yearly_offset_days: Mapped[int] = mapped_column(default=0)
