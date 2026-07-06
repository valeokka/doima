import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import texts
from bot.callbacks import Cal, DateCb, GiftCb, IdeaCb, Invite, Menu, PairCb, ShopCb, TaskCb, Tz, Wizard

POPULAR_TZS = [
    "Europe/Kaliningrad", "Europe/Moscow", "Europe/Samara", "Asia/Yekaterinburg",
    "Asia/Omsk", "Asia/Novosibirsk", "Asia/Krasnoyarsk", "Asia/Irkutsk",
    "Asia/Yakutsk", "Asia/Vladivostok", "Europe/Minsk", "Asia/Almaty",
]

RU_MONTHS = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
RU_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def invite_start() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.INVITE_BTN, callback_data=PairCb(action="invite"))
    return b.as_markup()


def invite_confirm(code: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.INVITE_ACCEPT_BTN, callback_data=Invite(action="accept", code=code))
    b.button(text=texts.INVITE_DECLINE_BTN, callback_data=Invite(action="decline", code=code))
    return b.as_markup()


def tz_choice() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, tz in enumerate(POPULAR_TZS):
        b.button(text=tz.split("/")[-1].replace("_", " "), callback_data=Tz(idx=i))
    b.adjust(3)
    return b.as_markup()


def main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.BTN_CALENDAR, callback_data=Menu(section="cal"))
    b.button(text=texts.BTN_IDEAS, callback_data=Menu(section="ideas"))
    b.button(text=texts.BTN_TASKS, callback_data=Menu(section="tasks"))
    b.button(text=texts.BTN_SHOPPING, callback_data=Menu(section="shop"))
    b.button(text=texts.BTN_DATES, callback_data=Menu(section="dates"))
    b.button(text=texts.BTN_GIFTS, callback_data=Menu(section="gifts"))
    b.button(text=texts.BTN_PAIR, callback_data=Menu(section="pair"))
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def back_home() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.BTN_BACK, callback_data=Menu(section="home"))
    return b.as_markup()


def month_grid(year: int, month: int, event_days: set[int]) -> InlineKeyboardMarkup:
    """Сетка месяца 7×N: дни с событиями помечены точкой."""
    b = InlineKeyboardBuilder()
    b.row(*[InlineKeyboardButton(text=w, callback_data="noop") for w in RU_WEEKDAYS])
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="noop"))
            else:
                mark = "•" if day in event_days else ""
                row.append(InlineKeyboardButton(
                    text=f"{day}{mark}",
                    callback_data=Cal(action="day", year=year, month=month, day=day).pack(),
                ))
        b.row(*row)
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    b.row(
        InlineKeyboardButton(text="◀", callback_data=Cal(action="show", year=prev_y, month=prev_m).pack()),
        InlineKeyboardButton(text=texts.BTN_ADD, callback_data=Cal(action="new").pack()),
        InlineKeyboardButton(text="▶", callback_data=Cal(action="show", year=next_y, month=next_m).pack()),
    )
    b.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=Menu(section="home").pack()))
    return b.as_markup()


def month_title(year: int, month: int) -> str:
    return f"{RU_MONTHS[month]} {year}"


def day_pick(year: int, month: int, prefix_action: str = "pickday") -> InlineKeyboardMarkup:
    """Выбор дня месяца в мастерах создания."""
    b = InlineKeyboardBuilder()
    days = calendar.monthrange(year, month)[1]
    today = date.today()
    for d in range(1, days + 1):
        b.button(text=str(d), callback_data=Cal(action=prefix_action, year=year, month=month, day=d))
    b.adjust(7)
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    b.row(
        InlineKeyboardButton(text="◀", callback_data=Cal(action=f"{prefix_action}nav", year=prev_y, month=prev_m).pack()),
        InlineKeyboardButton(text=month_title(year, month), callback_data="noop"),
        InlineKeyboardButton(text="▶", callback_data=Cal(action=f"{prefix_action}nav", year=next_y, month=next_m).pack()),
    )
    return b.as_markup()


def remind_choice() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.EVENT_REMIND_DEFAULT_BTN, callback_data=Wizard(action="remind_default"))
    b.button(text=texts.EVENT_REMIND_CUSTOM_BTN, callback_data=Wizard(action="remind_custom"))
    b.adjust(1)
    return b.as_markup()


def task_incoming(task_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.TASK_ACCEPT_BTN, callback_data=TaskCb(action="accept", task_id=task_id))
    b.button(text=texts.TASK_DECLINE_BTN, callback_data=TaskCb(action="decline", task_id=task_id))
    return b.as_markup()


def task_accepted(task_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.TASK_DONE_BTN, callback_data=TaskCb(action="done", task_id=task_id))
    return b.as_markup()


def no_deadline() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.TASK_NO_DEADLINE_BTN, callback_data=Wizard(action="no_deadline"))
    return b.as_markup()


def section_list(add_cb, rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Универсальный список раздела: [(text, packed_callback)] + Добавить + Назад."""
    b = InlineKeyboardBuilder()
    for text, cb in rows:
        b.row(InlineKeyboardButton(text=text, callback_data=cb))
    b.row(InlineKeyboardButton(text=texts.BTN_ADD, callback_data=add_cb.pack()))
    b.row(InlineKeyboardButton(text=texts.BTN_BACK, callback_data=Menu(section="home").pack()))
    return b.as_markup()


def gifts_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.GIFT_MY_BTN, callback_data=GiftCb(action="my"))
    b.button(text=texts.GIFT_PARTNER_BTN, callback_data=GiftCb(action="partner"))
    b.button(text=texts.BTN_BACK, callback_data=Menu(section="home"))
    b.adjust(2, 1)
    return b.as_markup()


def pair_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.UNPAIR_BTN, callback_data=PairCb(action="unpair"))
    b.button(text=texts.BTN_BACK, callback_data=Menu(section="home"))
    b.adjust(1)
    return b.as_markup()


def unpair_confirm() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=texts.UNPAIR_YES, callback_data=PairCb(action="unpair_yes"))
    b.button(text=texts.BTN_CANCEL, callback_data=Menu(section="pair"))
    b.adjust(1)
    return b.as_markup()
