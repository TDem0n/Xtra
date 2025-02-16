import asyncio
import logging
import sys
import json
import os
import datetime

from datetime import timedelta
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram_handler import TelegramHandler
from dotenv import load_dotenv

import technical
import collectnews

from geopy.geocoders import Nominatim
from tzwhere import tzwhere
import pytz
from datetime import datetime

load_dotenv()

# Конфигурация
misfgtime = 1 * 60 * 60 * 10  # 10 часов
TOKEN = os.getenv("BOT_TOKEN")
# Директория, в которой находится файл (например, /some/path/)
import os
fp = os.path.abspath(__file__)
basedir = os.path.dirname(fp)+("/" if not fp.endswith('/') else "")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
devid = 5324202988
startchain = ["city", "profile"]

# Инициализация бота
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
scheduler = AsyncIOScheduler()


def ekb(message: Message = None, userid: int = None) -> bool:
    # Реализуйте вашу логику определения региона
    return True

def get_profile(userid: int) -> str:
    profile_file = os.path.join(basedir, "profiles.json")
    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            profiles = json.load(f)
        return profiles.get(str(userid), "Нет профиля")
    except Exception as e:
        logging.error(f"Error reading profiles: {e}")
        return None

def save_profile(userid: int, text: str) -> None:
    profile_file = os.path.join(basedir, "profiles.json")
    try:
        with open(profile_file, "r+", encoding="utf-8") as f:
            profiles = json.load(f)
            profiles[str(userid)] = text
            f.seek(0)
            json.dump(profiles, f, ensure_ascii=False)
            f.truncate()  # Обрезаем остаток файла после новой записи
    except Exception as e:
        logging.error(f"Error saving profile: {e}")

def get_city(userid: int):
    city_file = os.path.join(basedir, "cities.json")
    try:
        with open(city_file, "r", encoding="utf-8") as f:
            cities = json.load(f)
        return cities.get(str(userid), None)
    except Exception as e:
        logging.error(f"Error reading cities: {e}")
        return None
    
def save_city(userid: int, city: str):
    city_file = os.path.join(basedir, "cities.json")
    try:
        with open(city_file, "r+", encoding="utf-8") as f:
            cities = json.load(f)
            cities[str(userid)] = city
            f.seek(0)
            json.dump(cities, f, ensure_ascii=False)
            f.truncate()  # Обрезаем остаток файла после новой записи
    except Exception as e:
        logging.error(f"Error saving profile: {e}")

from timezonefinder import TimezoneFinder

def city_exists(city_name:str, language:str="ru") -> bool:
    geolocator = Nominatim(user_agent="timezone_app", timeout=3)
    location = geolocator.geocode(city_name, language=language)
    if not location: return False
    return True

def get_timezone_by_city(city_name: str, language: str = 'ru') -> str:
    geolocator = Nominatim(user_agent="timezone_app", timeout=3)
    location = geolocator.geocode(city_name, language=language)
    if not location:
        raise ValueError(f"Город '{city_name}' не найден")
    
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=location.latitude, lng=location.longitude)
    return timezone_str

def get_tz(userid: int):
    city = get_city(userid)
    return get_timezone_by_city(city)

def get_current_action(userid: int) -> str:
    action_file = os.path.join(basedir, "currentacts.json")
    try:
        with open(action_file, "r", encoding="utf-8") as f:
            actions = json.load(f)
        return actions.get(str(userid))
    except Exception as e:
        logging.error(f"Error reading actions: {e}")
        return None

def set_current_action(userid: int, action: str) -> None:
    action_file = os.path.join(basedir, "currentacts.json")
    try:
        # Попытка открыть файл в режиме чтения/записи
        with open(action_file, "r+", encoding="utf-8") as f:
            actions = json.load(f)
            actions[str(userid)] = action
            f.seek(0)
            json.dump(actions, f, ensure_ascii=False)
            f.truncate()  # Обрезаем остаток файла
    except FileNotFoundError:
        # Если файла нет — создаём новый
        try:
            with open(action_file, "w", encoding="utf-8") as f:
                json.dump({str(userid): action}, f, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error creating action file: {e}")
    except Exception as e:
        logging.error(f"Error saving action: {e}")

async def set_notifytime(user_id, args, message, job_id, tz, notify_users, notify_file):
    # Парсинг и валидация времени
        try:
            if ":" not in args:
                raise ValueError
            hours, mins = map(int, args.split(":", 1))
            if not (0 <= hours < 24 and 0 <= mins < 60):
                raise ValueError
        except ValueError:
            await message.answer("⏰ Неверный формат времени. Используйте HH:MM (24-часовой формат)")
            return

        # Обновление расписания
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        scheduler.add_job(
            send_scheduled_xtra,
            CronTrigger(hour=hours, minute=mins, timezone=tz if tz!=None else "UTC"),
            args=[user_id],
            id=job_id,
            misfire_grace_time=misfgtime
        )

        # Сохранение настроек
        notify_users[str(user_id)] = {"hrs": hours, "mns": mins}
        with open(notify_file, "w", encoding="utf-8") as f:
            json.dump(notify_users, f, indent=2, ensure_ascii=False)

        await message.answer(f"✅ Ежедневные уведомления установлены на {hours:02}:{mins:02} "+ (str(tz) if tz!=None else "UTC"))

@dp.message(CommandStart())
async def start_handler(message: Message):
    start_msg_file = os.path.join(basedir, "startmsg.txt")
    try:
        with open(start_msg_file, "r", encoding="utf-8") as f:
            start_msg = f.read()
    except Exception as e:
        start_msg = "Добро пожаловать!"
        logging.error(f"Error reading start message: {e}")

    await message.answer(f"Здравствуйте, {html.bold(message.from_user.full_name)}!")
    await message.answer(start_msg)
    userid = message.from_user.id
    await bot.send_message(userid, "В каком городе Вы живёте? Напишите название Вашего города")
    set_current_action(userid, "city profile")
    
@dp.message(Command('help'))
async def help_handler(message: Message):
    start_msg_file = os.path.join(basedir, "helpmsg.txt")
    try:
        with open(start_msg_file, "r", encoding="utf-8") as f:
            help_msg = f.read()
    except Exception as e:
        logging.error(f"Error reading help message: {e}")

    await message.answer(help_msg)
    set_current_action(message.from_user.id, None)

async def send_important_news(message: Message, progress: bool = True):
    if progress:
        await message.answer("Анализирую новости...")
    
    if collectnews.noupdates().total_seconds() > 90:
        await asyncio.to_thread(collectnews.step)
    
    sources = ["ria"]
    if ekb(message):
        sources.append("e1")
    
    try:
        news = await technical.StepwiseNews(
            profile=f"Город: {get_city(message.from_user.id)}\n"+get_profile(message.from_user.id),
            newspart=100,
            message=message if progress else None,
            source=sources,
            llm="openai",
            model="gpt-4o-mini"
        )
        await message.answer(news)
    except Exception as e:
        logging.error(f"News error: {e}")
        await message.answer("Ошибка при получении новостей")

async def send_weather(message: Message, progress: bool = True, enquiry: str = None):
    if progress:
        await message.answer("Проверяю погоду...")
    try:
        wthr = await asyncio.to_thread(
            technical.Weather,
            city="екб",
            profile=get_profile(message.from_user.id),
            source='openmeteo',
            enquiry=enquiry
        )
        await message.answer(wthr if wthr else "Ничего особенного в прогнозе")
        if not wthr: logging.info("Ничего особенного")
    except Exception as e:
        logging.error(f"Weather error: {e}")
        await message.answer("Ошибка при проверке погоды")

@dp.message(Command("profile", "профиль"))
async def profile_handler(message: Message):
    await message.answer(f"Ваш профиль:\n<code>{get_profile(message.from_user.id)}</code>")
    await message.answer("Отправьте новый профиль для обновления")
    set_current_action(message.from_user.id, "profile")

@dp.message(Command("bignews", "important", "важное"))
async def news_handler(message: Message):
    set_current_action(message.from_user.id, None)
    asyncio.create_task(send_important_news(message))

@dp.message(Command("weather"))
async def weather_handler(message: Message):
    set_current_action(message.from_user.id, None)
    enquiry = message.text[8:].strip() or None
    await send_weather(message, enquiry=enquiry)

@dp.message(Command("xtra"))
async def xtra_handler(message: Message):
    set_current_action(message.from_user.id, None)
    await asyncio.gather(
        send_important_news(message, progress=True),
        send_weather(message, progress=True)
    )

@dp.message(Command("city"))
async def city_handler(message: Message):
    await message.answer("Напишите название Вашего города")
    curact = get_current_action(message.from_user.id)
    if curact != None and curact.split(maxsplit=1)[0]!="city": set_current_action(message.from_user.id, "city "+curact)
    elif curact in (None, ""): set_current_action(message.from_user.id, "city")

@dp.message(Command("notify"))
async def notify_handler(message: Message):
    # Получаем аргументы команды правильно
    args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
    user_id = message.from_user.id
    notify_file = os.path.join(basedir, "notifyusers.json")
    job_id = f"{user_id}_evrd"
    tz = get_tz(user_id)

    try:
        # Загрузка данных уведомлений (с обработкой пустого файла)
        notify_users = {}
        if os.path.exists(notify_file):
            try:
                with open(notify_file, "r", encoding="utf-8") as f:
                    notify_users = json.load(f)
            except json.JSONDecodeError:
                pass

        # Проверка текущих настроек
        if not args:
            if str(user_id) in notify_users:
                time_data = notify_users[str(user_id)]
                response = f"🔔 Уведомления установлены на {time_data['hrs']:02}:{time_data['mns']:02} "+(str(tz) if tz!=None else "UTC")
            else:
                response = "🔕 Уведомления не настроены"
            await message.answer(response)
            await message.answer("Напишите время, в которое Вы хотите получать новости ежедневно по местному времени (часы и минуты через двоеточие, например, 12:56)")
            set_current_action(user_id, "notify")
            return

        # Обработка отключения уведомлений
        if args.lower() in ("never", "stop", "off"):
            removed = False
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                removed = True
            
            if str(user_id) in notify_users:
                del notify_users[str(user_id)]
                with open(notify_file, "w", encoding="utf-8") as f:
                    json.dump(notify_users, f, indent=2)
                removed = True
            
            await message.answer("🔕 Уведомления отключены" if removed else "⚠ Нет активных уведомлений")
            return

        await set_notifytime(user_id, args, message, job_id, tz, notify_users, notify_file)

    except Exception as e:
        logging.error(f"Notify Error [User {user_id}]: {str(e)}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке запроса")
        
@dp.message()
async def default_handler(message: Message):
    userid = message.from_user.id
    act = get_current_action(userid)
    if message.text and act==None: 
        await message.answer("Не понимаю команду. Используйте /help")
        return
    chain = act.split() if act!=None else None
    next_msg = None
    repeat = False
    if chain[0] == "profile":
        save_profile(userid, message.text)
        await message.answer("Профиль успешно обновлен!")
    if chain[0] == "city":
        if city_exists(message.text):
            save_city(userid, message.text)
            await message.answer(f"Город успешно обновлён! Ваш часовой пояс - {get_tz(userid)}. Если это не так, отправьте /city чтобы попробовать снова")
        else:
            await message.answer("Город не найден, проверьте правильность написания и отправьте снова")
            repeat = True
    if chain[0] == "notify":
        args = message.text
        user_id = message.from_user.id
        notify_file = os.path.join(basedir, "notifyusers.json")
        job_id = f"{user_id}_evrd"
        tz = get_tz(user_id)
        
        notify_users = {}
        if os.path.exists(notify_file):
            try:
                with open(notify_file, "r", encoding="utf-8") as f:
                    notify_users = json.load(f)
            except json.JSONDecodeError:
                pass
        await set_notifytime(user_id, args, message, job_id, tz, notify_users, notify_file)

    if len(chain) > 1 and not repeat:
        if chain[1] == "profile":
            next_msg=("Теперь напишите описание Вашего профиля")
        if chain[1] == "city":
            next_msg=("Отправьте название Вашего города")
        set_current_action(userid, " ".join(chain[1:]))
    else: set_current_action(userid, None)
    if next_msg: await message.answer(next_msg)
    
    if repeat: set_current_action(userid, act)
# Изменения в send_scheduled_xtra
async def send_scheduled_xtra(userid: int):
    try:
        # Обновляем новости асинхронно
        if collectnews.noupdates().total_seconds() > 90:
            await asyncio.to_thread(collectnews.step)

        sources = ["ria"]
        if ekb(userid=userid):
            sources.append("e1")
        
        # Параллельное выполнение новостей и погоды
        news_coro = technical.StepwiseNews(
            profile=f"Город: {get_city(userid)}"+get_profile(userid),
            source=sources,
            message=None,
            llm="openai",
            model="gpt-4o-mini",
            newspart=100
        )
        weather_coro = asyncio.to_thread(
            technical.Weather,
            city="екб",
            profile=get_profile(userid),
            source='openmeteo'
        )
        
        # Запускаем обе задачи параллельно
        news, wthr = await asyncio.gather(news_coro, weather_coro)
        
        # Отправляем результаты
        await bot.send_message(userid, news)
        if wthr:
            await bot.send_message(userid, wthr)

    except Exception as e:
        logging.error(f"Scheduled xtra error for {userid}: {e}")
        await bot.send_message(userid, "⚠ Произошла ошибка при подготовке уведомления")
        
async def collectnews_update_job():
    await asyncio.to_thread(collectnews.step)

async def main():
    # Восстанавливаем расписания
    notify_file = os.path.join(basedir, "notifyusers.json")
    try:
        with open(notify_file, "r", encoding="utf-8") as f:
            notify_users = json.load(f)
            for uid, time in notify_users.items():
                scheduler.add_job(
                    send_scheduled_xtra,
                    CronTrigger(hour=time["hrs"], minute=time["mns"], timezone="UTC"),
                    args=[int(uid)],
                    id=f"{uid}_evrd",
                    misfire_grace_time=misfgtime
                )
    except Exception as e:
        logging.error(f"Error loading notifications: {e}")

    # Задача для регулярного обновления новостей
    scheduler.add_job(
        collectnews_update_job,
        'interval',
        minutes=120,
        next_run_time=datetime.now() + timedelta(minutes=1)
    )
    scheduler.start()
    
    handler = TelegramHandler(
        token=TOKEN,
        chat_id=devid
    )
    handler.setLevel(logging.WARNING)
    logging.getLogger().addHandler(handler)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown()