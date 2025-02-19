from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Создаём клавиатуру с кнопками-ответами
time = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,  # Клавиатура скроется после выбора
    keyboard=[
        [KeyboardButton(text="0:00"), KeyboardButton(text="4:00")],
        [KeyboardButton(text="7:00"), KeyboardButton(text="12:00")],
        [KeyboardButton(text="16:00"), KeyboardButton(text="20:00")]
    ]
)

city = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,  # Клавиатура скроется после выбора
    keyboard=[
        [KeyboardButton(text="Москва"), KeyboardButton(text="Екатеринбург")]
    ]
)

notify_text = "Установить ежедневные уведомления"
xtra_text = "Получить важные новости и проверить погоду"
profile_text = "Изменить Ваше описание профиля"
city_text = "Изменить город"
help_text = "Помощь"

free_text = (notify_text, xtra_text, profile_text, city_text, help_text)
free = ReplyKeyboardMarkup(
    resize_keyboard=True,
    one_time_keyboard=True,  # Клавиатура скроется после выбора
    keyboard=[
        [KeyboardButton(text=ft)] for ft in free_text
    ]
)