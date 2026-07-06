from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot import keyboards, texts
from bot.callbacks import Menu, TaskCb, Wizard
from bot.models import Couple, Reminder, ReminderStatus, Task, TaskStatus, User
from bot.services.notify import send_to
from bot.services.reminders import schedule_task_reminders
from bot.services.timeutil import fmt_local, now_utc, parse_ddmm_hhmm
from bot.states import NewTask

router = Router()


def _fmt_task_row(task: Task, tz: str, me: int) -> str:
    arrow = "→" if task.author_tg_id == me else "←"
    dl = f" ⏰{fmt_local(task.deadline_utc, tz)}" if task.deadline_utc else ""
    status = {TaskStatus.sent: "✉️", TaskStatus.accepted: "🔄", TaskStatus.done: "✔️", TaskStatus.declined: "🙅"}[task.status]
    return f"{status}{arrow} {task.text}{dl}"


@router.callback_query(Menu.filter(F.section == "tasks"))
async def tasks_list(query: CallbackQuery, session: AsyncSession, user: User, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    result = await session.execute(
        select(Task).where(
            Task.couple_id == couple.id,
            Task.status.in_([TaskStatus.sent, TaskStatus.accepted]),
        ).order_by(Task.created_at)
    )
    tasks = list(result.scalars())
    rows = []
    for t in tasks:
        if t.assignee_tg_id == user.tg_id and t.status == TaskStatus.sent:
            rows.append((_fmt_task_row(t, couple.timezone, user.tg_id), TaskCb(action="accept", task_id=t.id).pack()))
        elif t.assignee_tg_id == user.tg_id and t.status == TaskStatus.accepted:
            rows.append((_fmt_task_row(t, couple.timezone, user.tg_id), TaskCb(action="done", task_id=t.id).pack()))
        else:
            rows.append((_fmt_task_row(t, couple.timezone, user.tg_id), "noop"))
    text = texts.BTN_TASKS if tasks else texts.TASK_LIST_EMPTY
    await query.message.edit_text(text, reply_markup=keyboards.section_list(TaskCb(action="new"), rows))
    await query.answer()


@router.callback_query(TaskCb.filter(F.action == "new"))
async def task_new(query: CallbackQuery, state: FSMContext, couple: Couple | None):
    if couple is None:
        await query.answer(texts.NOT_PAIRED, show_alert=True)
        return
    await state.set_state(NewTask.text)
    await query.message.answer(texts.TASK_TEXT_PROMPT)
    await query.answer()


@router.message(NewTask.text, F.text)
async def task_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text.strip()[:512])
    await state.set_state(NewTask.deadline)
    await message.answer(texts.TASK_DEADLINE_PROMPT, reply_markup=keyboards.no_deadline())


async def _create_task(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple, partner: User | None, bot: Bot, deadline_utc,
):
    data = await state.get_data()
    task = Task(
        couple_id=couple.id, author_tg_id=user.tg_id,
        assignee_tg_id=partner.tg_id if partner else user.tg_id,
        text=data["text"], deadline_utc=deadline_utc, created_at=now_utc(),
    )
    session.add(task)
    await session.flush()
    await schedule_task_reminders(session, task, couple.timezone)
    await state.clear()
    await message.answer(texts.TASK_SENT)
    if partner is not None:
        dl = texts.TASK_DEADLINE_SUFFIX.format(dt=fmt_local(deadline_utc, couple.timezone)) if deadline_utc else ""
        delivered = await send_to(
            bot, partner.tg_id,
            texts.TASK_INCOMING.format(name=user.name, text=task.text, deadline=dl),
            keyboards.task_incoming(task.id),
        )
        if not delivered:
            await message.answer(texts.NOT_DELIVERED)


@router.message(NewTask.deadline, F.text)
async def task_deadline_text(
    message: Message, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple | None, partner: User | None, bot: Bot,
):
    deadline = parse_ddmm_hhmm(message.text, couple.timezone)
    if deadline is None:
        await message.answer(texts.TASK_DT_BAD, reply_markup=keyboards.no_deadline())
        return
    await _create_task(message, state, session, user, couple, partner, bot, deadline)


@router.callback_query(NewTask.deadline, Wizard.filter(F.action == "no_deadline"))
async def task_no_deadline(
    query: CallbackQuery, state: FSMContext, session: AsyncSession,
    user: User, couple: Couple | None, partner: User | None, bot: Bot,
):
    await _create_task(query.message, state, session, user, couple, partner, bot, None)
    await query.answer()


async def _transition(
    session: AsyncSession, task_id: int, from_statuses: list[TaskStatus], to_status: TaskStatus
) -> Task | None:
    """Optimistic-переход статуса; None = уже изменено параллельно."""
    res = await session.execute(
        update(Task)
        .where(Task.id == task_id, Task.status.in_(from_statuses))
        .values(status=to_status)
    )
    if res.rowcount != 1:
        return None
    return await session.get(Task, task_id)


@router.callback_query(TaskCb.filter(F.action.in_(["accept", "decline", "done"])))
async def task_action(
    query: CallbackQuery, callback_data: TaskCb, session: AsyncSession,
    user: User, couple: Couple | None, bot: Bot,
):
    action = callback_data.action
    transitions = {
        "accept": ([TaskStatus.sent], TaskStatus.accepted, texts.TASK_ACCEPTED_AUTHOR),
        "decline": ([TaskStatus.sent, TaskStatus.accepted], TaskStatus.declined, texts.TASK_DECLINED_AUTHOR),
        "done": ([TaskStatus.sent, TaskStatus.accepted], TaskStatus.done, texts.TASK_DONE_AUTHOR),
    }
    from_statuses, to_status, author_text = transitions[action]
    task = await _transition(session, callback_data.task_id, from_statuses, to_status)
    if task is None:
        await query.answer(texts.TASK_ALREADY_CHANGED, show_alert=True)
        return
    if to_status in (TaskStatus.done, TaskStatus.declined):
        # эскалация и дедлайн-напоминания больше не нужны
        await session.execute(
            update(Reminder)
            .where(Reminder.task_id == task.id, Reminder.status == ReminderStatus.pending)
            .values(status=ReminderStatus.cancelled)
        )
    kb = keyboards.task_accepted(task.id) if to_status == TaskStatus.accepted else None
    await query.message.edit_text(f"{query.message.text}\n\n{texts.TASK_STATE_CHANGED}", reply_markup=kb)
    if task.author_tg_id != user.tg_id:
        await send_to(bot, task.author_tg_id, author_text.format(name=user.name, text=task.text))
    await query.answer()
