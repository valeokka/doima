import secrets
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import (
    Couple,
    Event,
    ImportantDate,
    Invitation,
    InvitationStatus,
    Reminder,
    ShoppingItem,
    Task,
    User,
    WishItem,
)
from bot.services.timeutil import now_utc


@dataclass
class PairResult:
    ok: bool
    error: str | None = None  # invalid | self | already_paired | author_paired
    couple: Couple | None = None
    author: User | None = None


async def get_or_create_user(session: AsyncSession, tg_id: int, name: str) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(tg_id=tg_id, name=name)
        session.add(user)
        await session.flush()
    elif user.name != name:
        user.name = name
    return user


async def partner_of(session: AsyncSession, user: User) -> User | None:
    if user.couple_id is None:
        return None
    result = await session.execute(
        select(User).where(User.couple_id == user.couple_id, User.tg_id != user.tg_id)
    )
    return result.scalar_one_or_none()


async def create_invitation(session: AsyncSession, author: User) -> Invitation:
    # старые неиспользованные приглашения автора гасим
    await session.execute(
        update(Invitation)
        .where(Invitation.author_tg_id == author.tg_id, Invitation.status == InvitationStatus.pending)
        .values(status=InvitationStatus.cancelled)
    )
    inv = Invitation(code=secrets.token_urlsafe(12), author_tg_id=author.tg_id, created_at=now_utc())
    session.add(inv)
    await session.flush()
    return inv


async def accept_invitation(session: AsyncSession, code: str, acceptor: User, tz: str) -> PairResult:
    result = await session.execute(select(Invitation).where(Invitation.code == code))
    inv = result.scalar_one_or_none()
    if inv is None or inv.status != InvitationStatus.pending:
        return PairResult(ok=False, error="invalid")
    if inv.author_tg_id == acceptor.tg_id:
        return PairResult(ok=False, error="self")
    if acceptor.couple_id is not None:
        return PairResult(ok=False, error="already_paired")
    author = await session.get(User, inv.author_tg_id)
    if author is None:
        return PairResult(ok=False, error="invalid")
    if author.couple_id is not None:
        return PairResult(ok=False, error="author_paired")

    # одноразовость: гасим код атомарно — второй параллельный accept промахнётся
    res = await session.execute(
        update(Invitation)
        .where(Invitation.id == inv.id, Invitation.status == InvitationStatus.pending)
        .values(status=InvitationStatus.used)
    )
    if res.rowcount != 1:
        return PairResult(ok=False, error="invalid")

    couple = Couple(timezone=tz, created_at=now_utc())
    session.add(couple)
    await session.flush()
    author.couple_id = couple.id
    acceptor.couple_id = couple.id
    return PairResult(ok=True, couple=couple, author=author)


async def check_invitation(session: AsyncSession, code: str, acceptor_tg_id: int) -> PairResult:
    """Предварительная проверка кода до выбора часового пояса."""
    result = await session.execute(select(Invitation).where(Invitation.code == code))
    inv = result.scalar_one_or_none()
    if inv is None or inv.status != InvitationStatus.pending:
        return PairResult(ok=False, error="invalid")
    if inv.author_tg_id == acceptor_tg_id:
        return PairResult(ok=False, error="self")
    author = await session.get(User, inv.author_tg_id)
    if author is None:
        return PairResult(ok=False, error="invalid")
    if author.couple_id is not None:
        return PairResult(ok=False, error="author_paired")
    return PairResult(ok=True, author=author)


async def unpair(session: AsyncSession, couple_id: int) -> None:
    """Распад пары: общие данные удаляются, личные GiftWish остаются у владельцев."""
    for model in (Reminder, Event, WishItem, Task, ShoppingItem, ImportantDate):
        await session.execute(delete(model).where(model.couple_id == couple_id))
    await session.execute(update(User).where(User.couple_id == couple_id).values(couple_id=None))
    couple = await session.get(Couple, couple_id)
    if couple is not None:
        await session.delete(couple)
