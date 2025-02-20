from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

cancel_text = "Отмена"

time_text = [
    ["0:00", "4:00"],
    ["7:00", "12:00"],
    ["16:00", "20:00"],
    [cancel_text]
]

# Создаём клавиатуру с кнопками-ответами
time = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,  # Клавиатура скроется после выбора
    keyboard=[
        [KeyboardButton(text=tt) for tt in timetext] for timetext in time_text
    ],
    input_field_placeholder="Время"
)

city_text = [
    ["Москва", "Екатеринбург"],
    [cancel_text]
]

city = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,  # Клавиатура скроется после выбора
    keyboard=[
        [KeyboardButton(text=ct) for ct in citytext] for citytext in city_text
    ],
    input_field_placeholder="Город"
)

notify_text = "Уведомления"
xtra_text = "Запустить проверку"
profile_text = "Мой профиль"
city_text = "Мой город"
help_text = "Помощь"

free_text = [
    [xtra_text], 
    [profile_text, city_text], 
    [notify_text, help_text]
]

free = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,  # Клавиатура скроется после выбора
    keyboard=[
        [KeyboardButton(text=ft) for ft in freetext] for freetext in free_text
    ]
)

setprof_text = [[cancel_text]]
setprof = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,  # Клавиатура скроется после выбора
    keyboard=[
        [KeyboardButton(text=st) for st in setproftext] for setproftext in setprof_text
    ],
    input_field_placeholder="Цели и др.",
    is_persistent=True,
    selective=True
)