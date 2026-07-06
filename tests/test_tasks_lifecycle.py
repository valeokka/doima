from datetime import timedelta

from sqlalchemy import select, update

from bot.models import Reminder, ReminderStatus, Task, TaskStatus
from bot.services.reminders import schedule_task_reminders
from bot.services.timeutil import now_utc


async def _make_task(session, couple, deadline=None) -> Task:
    task = Task(
        couple_id=couple.id, author_tg_id=101, assignee_tg_id=202,
        text="купи цветы", deadline_utc=deadline, created_at=now_utc(),
    )
    session.add(task)
    await session.flush()
    return task


async def _transition(session, task_id, from_statuses, to_status) -> bool:
    res = await session.execute(
        update(Task).where(Task.id == task_id, Task.status.in_(from_statuses)).values(status=to_status)
    )
    return res.rowcount == 1


async def test_full_lifecycle_sent_accepted_done(session, couple):
    task = await _make_task(session, couple)
    assert task.status == TaskStatus.sent
    assert await _transition(session, task.id, [TaskStatus.sent], TaskStatus.accepted)
    assert await _transition(session, task.id, [TaskStatus.sent, TaskStatus.accepted], TaskStatus.done)
    await session.refresh(task)
    assert task.status == TaskStatus.done


async def test_decline_from_sent(session, couple):
    task = await _make_task(session, couple)
    assert await _transition(session, task.id, [TaskStatus.sent, TaskStatus.accepted], TaskStatus.declined)


async def test_concurrent_transition_loses(session, couple):
    """Optimistic UPDATE: второй параллельный переход промахивается."""
    task = await _make_task(session, couple)
    assert await _transition(session, task.id, [TaskStatus.sent], TaskStatus.accepted)
    # партнёр в тот же момент жмёт «Не могу» по устаревшей кнопке sent-состояния
    assert not await _transition(session, task.id, [TaskStatus.sent], TaskStatus.declined)


async def test_deadline_schedules_reminders(session, couple):
    deadline = now_utc() + timedelta(days=2)
    task = await _make_task(session, couple, deadline)
    await schedule_task_reminders(session, task, couple.timezone)
    await session.commit()

    reminders = (await session.execute(select(Reminder))).scalars().all()
    kinds = {r.is_escalation for r in reminders}
    assert len(reminders) == 2 and kinds == {True, False}
    escalation = next(r for r in reminders if r.is_escalation)
    assert escalation.fire_at_utc == deadline + timedelta(hours=1)


async def test_done_cancels_pending_reminders(session, couple):
    """Как в хендлере: done → pending-напоминания поручения отменяются."""
    deadline = now_utc() + timedelta(days=2)
    task = await _make_task(session, couple, deadline)
    await schedule_task_reminders(session, task, couple.timezone)
    await session.flush()

    await _transition(session, task.id, [TaskStatus.sent, TaskStatus.accepted], TaskStatus.done)
    await session.execute(
        update(Reminder)
        .where(Reminder.task_id == task.id, Reminder.status == ReminderStatus.pending)
        .values(status=ReminderStatus.cancelled)
    )
    await session.commit()

    pending = (await session.execute(
        select(Reminder).where(Reminder.status == ReminderStatus.pending)
    )).scalars().all()
    assert pending == []
