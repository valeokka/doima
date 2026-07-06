"""CallbackData-фабрики. Правило: только раздел+действие+id (лимит 64 байта),
свободный текст — через FSM/БД."""

from aiogram.filters.callback_data import CallbackData


class Menu(CallbackData, prefix="m"):
    section: str  # cal|ideas|tasks|shop|dates|gifts|pair|home


class Cal(CallbackData, prefix="cal"):
    action: str  # show|day|prev|next|new|del
    year: int = 0
    month: int = 0
    day: int = 0
    item_id: int = 0


class Invite(CallbackData, prefix="inv"):
    action: str  # accept|decline
    code: str


class Tz(CallbackData, prefix="tz"):
    idx: int


class TaskCb(CallbackData, prefix="t"):
    action: str  # accept|decline|done|new|list
    task_id: int = 0


class ShopCb(CallbackData, prefix="s"):
    action: str  # add|buy|list
    item_id: int = 0


class IdeaCb(CallbackData, prefix="i"):
    action: str  # add|plan|del|list
    item_id: int = 0


class DateCb(CallbackData, prefix="d"):
    action: str  # add|del|list
    item_id: int = 0


class GiftCb(CallbackData, prefix="g"):
    action: str  # my|partner|add|del
    item_id: int = 0


class PairCb(CallbackData, prefix="p"):
    action: str  # invite|unpair|unpair_yes


class Wizard(CallbackData, prefix="w"):
    action: str  # remind_default|remind_custom|no_deadline|cancel
