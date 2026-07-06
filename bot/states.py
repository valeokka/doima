from aiogram.fsm.state import State, StatesGroup


class NewEvent(StatesGroup):
    title = State()
    date = State()
    time = State()
    remind = State()
    custom_remind = State()


class NewTask(StatesGroup):
    text = State()
    deadline = State()


class NewShopping(StatesGroup):
    items = State()


class NewIdea(StatesGroup):
    text = State()


class PlanIdea(StatesGroup):
    date = State()
    time = State()


class NewDate(StatesGroup):
    title = State()
    date = State()


class NewGift(StatesGroup):
    text = State()


class ChooseTz(StatesGroup):
    manual = State()
