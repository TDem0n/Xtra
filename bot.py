import asyncio
import logging
import sys
import json
import os
import datetime
import traceback


from datetime import timedelta
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram import F, types
from aiogram.types import Message, ReplyKeyboardRemove
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram_handler import TelegramHandler
from dotenv import load_dotenv

import technical
import collectnews
import interaction as intr
import data

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
basedir = os.path.dirname(fp)#+("/" if not fp.endswith('/') else "")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
devid = 5324202988

# Инициализация бота
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
scheduler = AsyncIOScheduler()


basenews = ["ria", "ixbt"]


def ekb(message: Message = None, userid: int = None) -> bool:
    # Реализуйте вашу логику определения региона
    return True

async def get_profile(userid: int) -> str:
    profile_file = os.path.join(basedir, "profiles.json")
    try:
        with open(profile_file, "r", encoding="utf-8") as f:
            profiles = json.load(f)
        prf = await data.getprofile(userid) # using DB only for making sure it works and for next updates
        prf = profiles.get(str(userid), "Нет профиля")
        await data.setprofile(userid, prf)
        return prf
    except Exception as e:
        logging.error(f"Error reading profiles: {e}")
        return None

async def save_profile(userid: int, text: str) -> None:
    profile_file = os.path.join(basedir, "profiles.json")
    try:
        await data.setprofile(userid, text) # DB usage
        with open(profile_file, "r+", encoding="utf-8") as f:
            profiles = json.load(f)
            profiles[str(userid)] = text
            f.seek(0)
            json.dump(profiles, f, ensure_ascii=False)
            f.truncate()  # Обрезаем остаток файла после новой записи
    except Exception as e:
        logging.error(f"Error saving profile: {e}")

async def get_city(userid: int):
    city_file = os.path.join(basedir, "cities.json")
    try:
        ct = await data.getcity(userid)
        with open(city_file, "r", encoding="utf-8") as f:
            cities = json.load(f)
        ct = cities.get(str(userid), None)
        await data.setcity(userid, ct) # DB usage
        return ct
    except Exception as e:
        logging.error(f"Error reading cities: {e}")
        return None
    
async def save_city(userid: int, city: str):
    city_file = os.path.join(basedir, "cities.json")
    try:
        await data.setcity(userid, city) # DB usage
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

async def get_tz(userid: int):
    city = await get_city(userid)
    tz = await data.gettz(userid) # DB usage
    tz = get_timezone_by_city(city)
    await data.settz(userid, tz)
    return tz

async def get_current_action(userid: int) -> str:
    action_file = os.path.join(basedir, "currentacts.json")
    try:
        act = await data.getact(userid) # DB usage
        with open(action_file, "r", encoding="utf-8") as f:
            actions = json.load(f)
        act = actions.get(str(userid))
        await data.setact(userid, act)
        return act
    except Exception as e:
        logging.error(f"Error reading actions: {e}")
        return None

async def set_current_action(userid: int, action: str) -> None:
    action_file = os.path.join(basedir, "currentacts.json")
    try:
        await data.setact(userid, action) # DB usage
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
            await message.answer("⏰ Неверный формат времени. Используйте 24-часовой формат часы:минуты")
            await set_current_action(user_id, 'notify')
            return "repeat"

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

        await data.setnotify(user_id, hours, mins) # DB usage
        with open(notify_file, "w", encoding="utf-8") as f:
            json.dump(notify_users, f, indent=2, ensure_ascii=False)

        await message.answer(f"✅ Ежедневные уведомления установлены на {hours:02}:{mins:02} "+ (str(tz) if tz!=None else "UTC"), reply_markup=intr.free)

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
    await bot.send_message(userid, "В каком городе Вы живёте? Напишите название Вашего города", reply_markup=intr.city)
    await set_current_action(userid, "city profile")
    
@dp.message(Command('help'))
async def help_handler(message: Message):
    help_msg_file = os.path.join(basedir, "helpmsg.txt")
    try:
        with open(help_msg_file, "r", encoding="utf-8") as f:
            help_msg = f.read()
    except Exception as e:
        logging.error(f"Error reading help message: {e}")

    await message.answer(help_msg, reply_markup=intr.free)
    await set_current_action(message.from_user.id, None)

async def send_important_news(message: Message, progress: bool = True):
    if progress:
        await message.answer("Анализирую новости...")
    
    if collectnews.noupdates().total_seconds() > 90:
        await collectnews.step()
    
    sources = basenews.copy()
    if ekb(message):
        sources.extend(["e1", "afisha: ekaterinburg"])
    
    try:
        news = await technical.StepwiseNews(
            profile=f"Город: {await get_city(message.from_user.id)}\n"+await get_profile(message.from_user.id),
            newspart=100,
            message=message if progress else None,
            source=sources,
            llm1="openai",
            model1="gpt-4o-mini",
            llm2="deepseek",
            model2="deepseek-chat"
        )
        await message.answer(news, reply_markup=intr.free)
    except Exception as e:
        logging.error(f"News error: {e}\n{traceback.format_exc()}")
        await message.answer("Ошибка при получении новостей", reply_markup=intr.free)

async def send_weather(message: Message, progress: bool = True, enquiry: str = None, always_return=False):
    if progress:
        await message.answer("Проверяю погоду...")
    try:
        wthr = await technical.Weather(city="екб", profile=await get_profile(message.from_user.id), source='openmeteo', enquiry=enquiry, always_return=True)
        await message.answer(wthr if wthr else "Ничего особенного в прогнозе погоды", reply_markup=intr.free)
        if not wthr: logging.info("Ничего особенного")
    except Exception as e:
        logging.error(f"Weather error: {e}\n{traceback.format_exc()}")
        await message.answer("Ошибка при проверке погоды", reply_markup=intr.free)

@dp.message(Command("profile", "профиль"))
async def profile_handler(message: Message):
    profile_help = open("profile_help.txt").read()
    await message.answer(profile_help)
    await message.answer(f"Ваш профиль:\n<code>{await get_profile(message.from_user.id)}</code>")
    await message.answer("Отправьте новый профиль для обновления", reply_markup=intr.setprof)
    await set_current_action(message.from_user.id, "profile")

@dp.message(Command("bignews", "important", "важное"))
async def news_handler(message: Message):
    await set_current_action(message.from_user.id, None)
    asyncio.create_task(send_important_news(message))

@dp.message(Command("weather"))
async def weather_handler(message: Message):
    await set_current_action(message.from_user.id, None)
    enquiry = message.text[8:].strip() or None
    await send_weather(message, enquiry=enquiry, always_return=True)

@dp.message(Command("xtra", "sense"))
async def xtra_handler(message: Message):
    await set_current_action(message.from_user.id, None)
    await asyncio.gather(
        send_important_news(message, progress=True),
        send_weather(message, progress=True)
    )

@dp.message(Command("city"))
async def city_handler(message: Message):
    await message.answer(f"Установлен город: {await get_city(message.from_user.id)}")
    await message.answer("Напишите название Вашего города", reply_markup=intr.city)
    curact = await get_current_action(message.from_user.id)
    if curact != None and curact.split(maxsplit=1)[0]!="city": await set_current_action(message.from_user.id, "city "+curact)
    elif curact in (None, ""): await set_current_action(message.from_user.id, "city")


@dp.message(Command("notify"))
async def notify_handler(message: Message, try_to_get_time=True):
    # Получаем аргументы команды правильно
    args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
    user_id = message.from_user.id
    notify_file = os.path.join(basedir, "notifyusers.json")
    job_id = f"{user_id}_evrd"
    tz = await get_tz(user_id)
    time_data = await data.getnotify(user_id) # DB usage

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
        if (not args) or (not try_to_get_time):
            if str(user_id) in notify_users: 
            # if time_data:
                time_data = notify_users[str(user_id)] # Del
                response = f"🔔 Уведомления установлены на {time_data['hrs']:02}:{time_data['mns']:02} "+(str(tz) if tz!=None else "UTC")
            else:
                response = "🔕 Уведомления не настроены"
            await message.answer(response)

            await message.answer("Выберите время уведомлений:", reply_markup=intr.time)
            await set_current_action(user_id, "notify")
            return

        # Обработка отключения уведомлений
        if args.lower() in ("never", "stop", "off"):
            removed = False
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                removed = True
            
            if str(user_id) in notify_users:
            # if time_data:
                del notify_users[str(user_id)]
                await data.setnotify(user_id, hrs=0, mns=0, off=True)
                with open(notify_file, "w", encoding="utf-8") as f:
                    json.dump(notify_users, f, indent=2)
                removed = True
            
            await message.answer("🔕 Уведомления отключены" if removed else "⚠ Нет активных уведомлений",
                                 reply_markup=intr.free)
            return

        await set_notifytime(user_id, args, message, job_id, tz, notify_users, notify_file)

    except Exception as e:
        logging.error(f"Notify Error [User {user_id}]: {str(e)}\n{traceback.format_exc()}", exc_info=True)
        await message.answer("❌ Произошла ошибка при обработке запроса", reply_markup=intr.free)
        
@dp.message()
async def default_handler(message: Message):
    mt = message.text
    userid = message.from_user.id
    if mt==intr.notify_text: return await notify_handler(message, try_to_get_time=False)
    elif mt==intr.xtra_text: return await xtra_handler(message)
    elif mt==intr.profile_text: return await profile_handler(message)
    elif mt==intr.city_text: return await city_handler(message)
    elif mt==intr.help_text: return await help_handler(message)
    elif mt==intr.cancel_text: 
        await message.answer("Вы вернулись на главную", reply_markup=intr.free)
        await set_current_action(userid, None)
        return

    userid = message.from_user.id
    act = await get_current_action(userid)
    if message.text and act==None: 
        await message.answer("Не понимаю команду. Используйте /help", reply_markup=intr.free)
        return
    chain = act.split() if act!=None else None
    next_msg = None
    repeat = False
    kb = intr.free

    if chain[0] == "profile":
        await save_profile(userid, message.text)
        await message.answer("Профиль успешно обновлен!", reply_markup=intr.free)
    if chain[0] == "city":
        if city_exists(message.text):
            await save_city(userid, message.text)
            await message.answer(f"Город успешно обновлён! Ваш часовой пояс - {await get_tz(userid)}. Если это не так, отправьте /city чтобы попробовать снова", 
                                 reply_markup=intr.free)
        else:
            await message.answer("Город не найден, проверьте правильность написания и отправьте снова",
                                 reply_markup=intr.free)
            repeat = True
    if chain[0] == "notify":
        args = message.text
        user_id = message.from_user.id
        notify_file = os.path.join(basedir, "notifyusers.json")
        job_id = f"{user_id}_evrd"
        tz = await get_tz(user_id)
        
        notify_users = {}
        if os.path.exists(notify_file):
            try:
                with open(notify_file, "r", encoding="utf-8") as f:
                    notify_users = json.load(f)
            except json.JSONDecodeError:
                pass
        res = await set_notifytime(user_id, args, message, job_id, tz, notify_users, notify_file)
        if res == "repeat": repeat = True

    if len(chain) > 1 and not repeat:
        if chain[1] == "profile":
            next_msg=open("profile_help.txt").read()
            kb = intr.setprof
        if chain[1] == "city":
            next_msg=("Отправьте название Вашего города")
        await set_current_action(userid, " ".join(chain[1:]))
    else: await set_current_action(userid, None)
    if next_msg: await message.answer(next_msg, reply_markup=kb)
    
    if repeat: await set_current_action(userid, act)
# Изменения в send_scheduled_xtra
async def send_scheduled_xtra(userid: int):
    try:
        if collectnews.noupdates().total_seconds() > 90:
            await collectnews.step()

        sources = basenews.copy()
        if ekb(userid=userid):
            sources.extend(["e1", "afisha: ekaterinburg"])
        
        # Добавляем логирование для отладки
        city = await get_city(userid)
        profile = await get_profile(userid)
        logging.info(f"User {userid} - City: {city}, Profile: {profile}")
        
        # Параллельное выполнение новостей и погоды
        try:
            news_coro = technical.StepwiseNews(
                profile=f"Город: {city}\n{profile}",
                source=sources,
                message=None,
                llm1="openai",
                model1="gpt-4o-mini",
                llm2="deepseek",
                model2="deepseek-chat",
                newspart=100
            )
        except Exception as e:
            logging.error(f"Error in StepwiseNews: {e}")
            raise

        try:
            weather_coro = technical.Weather(city="екб", profile=profile, source='openmeteo')
        except Exception as e:
            logging.error(f"Error in Weather: {e}")
            raise
        
        news, wthr = await asyncio.gather(news_coro, weather_coro)
        await bot.send_message(userid, news)
        if wthr:
            await bot.send_message(userid, wthr)
    except asyncio.TimeoutError:
        logging.error(f"Timeout error in scheduled xtra for {userid}. \n{traceback.format_exc()}")
        await bot.send_message(userid, "⚠ Произошла ошибка при подготовке уведомления")
    except Exception as e:
        logging.error(f"Scheduled xtra error for {userid}: {str(e)}\nTraceback: {traceback.format_exc()}")
        await bot.send_message(userid, "⚠ Произошла ошибка при подготовке уведомления")
        
async def collectnews_update_job(af_cities=[]):
    await asyncio.to_thread(lambda: collectnews.step(af_cities=af_cities))

async def main():
    # Восстанавливаем расписания
    notify_file = os.path.join(basedir, "notifyusers.json")
    try:
        with open(notify_file, "r", encoding="utf-8") as f:
            notify_users = json.load(f)
            for uid, time in notify_users.items():
                tz = await get_tz(int(uid))
                scheduler.add_job(
                    send_scheduled_xtra,
                    CronTrigger(hour=time["hrs"], minute=time["mns"], timezone=tz if tz!=None else "UTC"),
                    args=[int(uid)],
                    id=f"{uid}_evrd",
                    misfire_grace_time=misfgtime
                )
    except Exception as e:
        logging.error(f"Error loading notifications: {e}")

    # Задача для регулярного обновления новостей
    scheduler.add_job(
        collectnews.step,
        'interval',
        minutes=120,
        kwargs={'af_cities': ['ekaterinburg', 'msk']},
        executor='default',
        next_run_time=datetime.now() + timedelta(minutes=0)
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