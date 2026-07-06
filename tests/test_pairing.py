from bot.models import User
from bot.services import pairing


async def test_full_pairing_flow(session):
    author = await pairing.get_or_create_user(session, 1, "A")
    acceptor = await pairing.get_or_create_user(session, 2, "B")
    inv = await pairing.create_invitation(session, author)

    result = await pairing.accept_invitation(session, inv.code, acceptor, "Europe/Moscow")

    assert result.ok
    assert author.couple_id == acceptor.couple_id == result.couple.id
    assert result.couple.timezone == "Europe/Moscow"


async def test_code_is_single_use(session):
    author = await pairing.get_or_create_user(session, 1, "A")
    b = await pairing.get_or_create_user(session, 2, "B")
    c = await pairing.get_or_create_user(session, 3, "C")
    inv = await pairing.create_invitation(session, author)

    assert (await pairing.accept_invitation(session, inv.code, b, "Europe/Moscow")).ok
    second = await pairing.accept_invitation(session, inv.code, c, "Europe/Moscow")

    assert not second.ok
    assert second.error == "invalid"


async def test_cannot_pair_with_self(session):
    author = await pairing.get_or_create_user(session, 1, "A")
    inv = await pairing.create_invitation(session, author)

    result = await pairing.accept_invitation(session, inv.code, author, "Europe/Moscow")

    assert not result.ok and result.error == "self"


async def test_third_person_cannot_join_existing_pair(session):
    """Уже состоящий в паре не может принять новое приглашение."""
    a = await pairing.get_or_create_user(session, 1, "A")
    b = await pairing.get_or_create_user(session, 2, "B")
    c = await pairing.get_or_create_user(session, 3, "C")
    inv_ab = await pairing.create_invitation(session, a)
    assert (await pairing.accept_invitation(session, inv_ab.code, b, "Europe/Moscow")).ok

    inv_c = await pairing.create_invitation(session, c)
    result = await pairing.accept_invitation(session, inv_c.code, b, "Europe/Moscow")
    assert not result.ok and result.error == "already_paired"

    # и наоборот: автор уже в паре
    inv_a2 = await pairing.create_invitation(session, a)
    result2 = await pairing.accept_invitation(session, inv_a2.code, c, "Europe/Moscow")
    assert not result2.ok and result2.error == "author_paired"


async def test_new_invitation_cancels_previous(session):
    author = await pairing.get_or_create_user(session, 1, "A")
    b = await pairing.get_or_create_user(session, 2, "B")
    inv1 = await pairing.create_invitation(session, author)
    inv2 = await pairing.create_invitation(session, author)

    assert not (await pairing.accept_invitation(session, inv1.code, b, "Europe/Moscow")).ok
    assert (await pairing.accept_invitation(session, inv2.code, b, "Europe/Moscow")).ok


async def test_unpair_clears_couple(session, couple):
    await pairing.unpair(session, couple.id)
    await session.commit()

    users = [await session.get(User, 101), await session.get(User, 202)]
    assert all(u.couple_id is None for u in users)
