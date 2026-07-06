"""Все пользовательские строки бота — в одном месте."""

WELCOME_NO_PAIR = (
    "Привет! Я «Дойма» — бот для пар: общий календарь, идеи, поручения, "
    "покупки, важные даты и списки желаний.\n\n"
    "Чтобы начать, пригласите свою пару 💌"
)
INVITE_BTN = "💌 Пригласить пару"
INVITE_LINK_TEXT = (
    "Перешлите эту ссылку вашей паре — по ней вы объединитесь:\n{link}\n\n"
    "Ссылка одноразовая."
)
INVITE_CONFIRM = "{name} приглашает вас создать пару. Принять?"
INVITE_ACCEPT_BTN = "✅ Принять"
INVITE_DECLINE_BTN = "🙅 Отказаться"
INVITE_DECLINED = "Вы отклонили приглашение."
INVITE_DECLINED_AUTHOR = "{name} отклонил(а) приглашение."
INVITE_INVALID = "Эта ссылка-приглашение недействительна или уже использована."
INVITE_SELF = "Нельзя создать пару с самим собой 🙂"
ALREADY_PAIRED = "Вы уже состоите в паре. Сначала расстаньтесь с текущей (⚙️ Пара → Разойтись)."
AUTHOR_ALREADY_PAIRED = "Автор приглашения уже состоит в паре."
CHOOSE_TZ = "Выберите часовой пояс вашей пары:"
PAIR_CREATED = "🎉 Вы теперь пара! Вот что я умею — выбирайте раздел:"
PAIR_CREATED_PARTNER = "🎉 {name} принял(а) приглашение — вы теперь пара!"

NOT_PAIRED = "Сначала нужно создать пару: нажмите «Пригласить пару» в /start."
MENU_TITLE = "{names}\n{digest}"
DIGEST_EMPTY = "На сегодня планов нет."
DIGEST_EVENT = "Сегодня: {event}"
DIGEST_TASKS = "Открытых поручений: {n}"

BTN_CALENDAR = "📅 Календарь"
BTN_IDEAS = "💡 Идеи"
BTN_TASKS = "✅ Поручения"
BTN_SHOPPING = "🛒 Покупки"
BTN_DATES = "🎂 Даты"
BTN_GIFTS = "🎁 Желания"
BTN_PAIR = "⚙️ Пара"
BTN_BACK = "◀️ Назад"
BTN_ADD = "➕ Добавить"
BTN_CANCEL = "Отмена"
CANCELLED = "Отменено."

# Календарь
EVENT_TITLE_PROMPT = "Название события?"
EVENT_DATE_PROMPT = "Выберите дату:"
EVENT_TIME_PROMPT = "Время в формате ЧЧ:ММ (например, 19:00):"
EVENT_TIME_BAD = "Не понял время. Пример: 19:00"
EVENT_REMIND_PROMPT = (
    "Напоминание по умолчанию: за день и за 2 часа.\n"
    "Оставить или задать своё время?"
)
EVENT_REMIND_DEFAULT_BTN = "Оставить по умолчанию"
EVENT_REMIND_CUSTOM_BTN = "Своё время"
EVENT_REMIND_CUSTOM_PROMPT = "Когда напомнить? Формат: ДД.ММ ЧЧ:ММ"
EVENT_CREATED = "Событие добавлено: {title} — {when}"
EVENT_CREATED_PARTNER = "📅 {name} добавил(а) событие: {title} — {when}"
EVENT_EMPTY_DAY = "На этот день событий нет."
EVENT_DELETED = "Событие удалено."
BTN_DELETE = "🗑 Удалить"

# Поручения
TASK_TEXT_PROMPT = "Что поручить? Опишите одним сообщением:"
TASK_DEADLINE_PROMPT = "Дедлайн? Формат: ДД.ММ ЧЧ:ММ, или нажмите «Без срока»."
TASK_NO_DEADLINE_BTN = "Без срока"
TASK_DT_BAD = "Не понял дату. Пример: 15.07 18:00"
TASK_SENT = "Поручение отправлено ✉️"
TASK_INCOMING = "📨 Поручение от {name}: «{text}»{deadline}"
TASK_DEADLINE_SUFFIX = " (до {dt})"
TASK_ACCEPT_BTN = "✅ Принять"
TASK_DECLINE_BTN = "🙅 Не могу"
TASK_DONE_BTN = "✔️ Готово"
TASK_ACCEPTED_AUTHOR = "✅ {name} принял(а) поручение: «{text}»"
TASK_DECLINED_AUTHOR = "🙅 {name} не может выполнить: «{text}»"
TASK_DONE_AUTHOR = "🎉 {name} выполнил(а): «{text}»"
TASK_STATE_CHANGED = "Статус обновлён."
TASK_ALREADY_CHANGED = "Уже изменено — обновите список."
TASK_LIST_EMPTY = "Открытых поручений нет."
TASK_DEADLINE_TODAY = "⏰ Сегодня дедлайн поручения: «{text}»"
TASK_OVERDUE = "⚠️ Просрочено поручение: «{text}»"

# Покупки
SHOPPING_PROMPT = "Что купить? Можно несколько через запятую:"
SHOPPING_ADDED = "Добавлено в список покупок."
SHOPPING_ADDED_PARTNER = "🛒 {name} добавил(а) в покупки: {items}"
SHOPPING_EMPTY = "Список покупок пуст."
SHOPPING_BOUGHT = "Отмечено купленным."

# Идеи
IDEA_PROMPT = "Какая идея? («тот ресторан», «выставка…»):"
IDEA_ADDED = "Идея сохранена 💡"
IDEA_ADDED_PARTNER = "💡 {name} добавил(а) идею: {text}"
IDEA_EMPTY = "Идей пока нет — добавьте первую!"
IDEA_SCHEDULE_BTN = "📅 Запланировать"
IDEA_SCHEDULED = "Идея превратилась в событие 🎉"

# Важные даты
DATE_TITLE_PROMPT = "Название даты (например, «Годовщина»):"
DATE_DATE_PROMPT = "Дата в формате ДД.ММ (год не нужен):"
DATE_BAD = "Не понял дату. Пример: 14.02"
DATE_ADDED = "Важная дата добавлена. Напомню за неделю и в сам день."
DATE_ADDED_PARTNER = "🎂 {name} добавил(а) важную дату: {title} ({date})"
DATE_EMPTY = "Важных дат пока нет."
DATE_WEEK_BEFORE = "🎂 Через неделю — {title}! Время придумать подарок 😉"
DATE_TODAY = "🎉 Сегодня — {title}!"

# Желания-подарки
GIFT_MY_TITLE = "Ваш список желаний (партнёр видит его):"
GIFT_PARTNER_TITLE = "Список желаний {name} (только просмотр):"
GIFT_PROMPT = "Какое желание добавить?"
GIFT_ADDED = "Желание добавлено 🎁"
GIFT_EMPTY = "Список пуст."
GIFT_MY_BTN = "Мой список"
GIFT_PARTNER_BTN = "Список пары"

# Пара / настройки
PAIR_INFO = "👩‍❤️‍👨 {a} и {b}\nВместе с ботом: {days} дн.\nЧасовой пояс: {tz}"
UNPAIR_BTN = "💔 Разойтись"
UNPAIR_CONFIRM = "Точно расстаться? Общие данные пары будут удалены."
UNPAIR_YES = "Да, расстаться"
UNPAIRED = "Пара распалась. Данные удалены."
UNPAIRED_PARTNER = "{name} завершил(а) вашу пару в боте."

# Напоминания
REMIND_EVENT_DAY = "📅 Завтра: {title} — {when}"
REMIND_EVENT_2H = "📅 Через 2 часа: {title}"
REMIND_CUSTOM = "🔔 Напоминание: {title} — {when}"

NOT_DELIVERED = "⚠️ Не удалось доставить сообщение партнёру (возможно, бот заблокирован)."
