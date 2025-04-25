from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os
from motor.motor_asyncio import AsyncIOMotorClient
import random

from pymongo import ReturnDocument
from asyncio import Lock
from collections import defaultdict
import asyncio

# URI для подключения:
# - С VM:       "mongodb://localhost:27017"
# - С ПК:       "mongodb://IP_VM:27017"

# Общие настройки по умолчанию для нового пользователя
DEFAULT_USER = {
}

# Here's structure of my future database:
"""structure_db = {
    # database level
    "users":[
        {"id":157, "city":"Екатеринбург", "notifytime":{"hrs":13, "mns":56}, "profile":"some descr. (str)", "act":"some action (str)", "tz":"some timezone (str)"}, # ...
        {"id":314, "city":"Москва", "notifytime":{"hrs":23, "mns":0}, "profile":"some descr. (str)", "act":"some action (str|None)", "tz":"some timezone (str)"}, # ...
        # ...
    ],
    "caches":{
        {"type":"llm", "cache": "(dict)"},
        {"type":"news", "cache": "(dict)"},
    },
    "news": {
        {"service":"ria", "news":"(list)"}, # ...
        {"service":"ixbt", "news":"(list)"}, # ...
        {"service":"e1", "news":"(list)"} # ...
    }
}"""
# So, in my database must be 3 collections: "users", "caches", "news"


load_dotenv()
psw = os.getenv("MONGO_PSW")

# Connecting to my locally installed database on VM
uri = f"mongodb://admin:{psw}@45.86.181.63:27017/?authSource=admin"
client = AsyncIOMotorClient(uri)
db = client["xtra"]

# Глобальные настройки
USER_LOCKS = defaultdict(Lock)
DEFAULT_USER = {}

async def _atomic_user_update(user_id: int, update_data: dict):
    max_attempts = 5  # Увеличим количество попыток
    base_delay = 0.3  # Увеличим базовую задержку
    
    for attempt in range(1, max_attempts + 1):
        try:
            user = await db.users.find_one({"id": user_id})
            
            # Инициализация версии для старых документов
            if user and "_version" not in user:
                await db.users.update_one(
                    {"id": user_id},
                    {"$set": {"_version": 1}}
                )
                user["_version"] = 1

            if not user:
                new_user = {**DEFAULT_USER, "id": user_id, **update_data}
                await db.users.insert_one(new_user)
                return new_user

            current_version = user.get("_version", 1)
            result = await db.users.find_one_and_update(
                {"id": user_id, "_version": current_version},
                {"$set": {**update_data, "_version": current_version + 1}},
                return_document=ReturnDocument.AFTER
            )
            
            if result:
                return result
                
        except Exception as e:
            print(f"Attempt {attempt} failed: {str(e)}")
        
        await asyncio.sleep(base_delay * attempt)
    
    # Последняя попытка без проверки версии
    print("Last attempt without checking the version")
    return await db.users.find_one_and_update(
        {"id": user_id},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )

# Функции для пользователей
async def getcity(user_id: int) -> str:
    user = await db.users.find_one({"id": user_id})
    return user.get("city") if user else None

async def setcity(user_id: int, city: str):
    async with USER_LOCKS[user_id]:
        return await _atomic_user_update(user_id, {"city": city})

async def getnotify(user_id: int) -> dict:
    user = await db.users.find_one({"id": user_id})
    return user.get("notifytime") if user else None

async def setnotify(user_id: int, hrs: int, mns: int, off=False):
    async with USER_LOCKS[user_id]:
        return await _atomic_user_update(user_id, {"notifytime": ({"hrs": hrs, "mns": mns} if not off else None)})

async def getprofile(user_id: int) -> str:
    user = await db.users.find_one({"id": user_id})
    return user.get("profile") if user else None

async def setprofile(user_id: int, profile: str):
    async with USER_LOCKS[user_id]:
        return await _atomic_user_update(user_id, {"profile": profile})

async def getact(user_id: int):
    user = await db.users.find_one({"id": user_id})
    return user.get("act") if user else None

async def setact(user_id: int, action: str):
    async with USER_LOCKS[user_id]:
        return await _atomic_user_update(user_id, {"act": action})

async def gettz(user_id: int) -> str:
    user = await db.users.find_one({"id": user_id})
    return user.get("tz") if user else None

async def settz(user_id: int, timezone: str):
    async with USER_LOCKS[user_id]:
        return await _atomic_user_update(user_id, {"tz": timezone})

# Функции для кешей
async def getllmcache() -> dict:
    cache = await db.caches.find_one({"type": "llm"})
    return cache.get("cache") if cache else None

async def setllmcache(data: dict):
    await db.caches.replace_one(
    {"type": "llm"},  # Фильтр для поиска документа
    {"type": "llm", "cache": data},  # Полностью новый документ
    upsert=True  # Создать документ, если не найден
)

async def getnewscache() -> dict:
    cache = await db.caches.find_one({"type": "news"})
    return cache.get("cache") if cache else None

async def setnewscache(data: dict):
    await db.caches.replace_one(
    {"type": "news"},  # Фильтр для поиска документа
    {"type": "news", "cache": data},  # Полностью новый документ
    upsert=True  # Создать документ, если не найден
)

# Функции для новостей
async def getnews(service: str) -> list:
    news = await db.news.find_one({"service": service})
    return news.get("news") if news else None

async def setnews(service: str, news_list: list):
    await db.news.replace_one(
    {"service": service},  # Фильтр для поиска документа
    {"service": service, "news": news_list},  # Полностью новый документ
    upsert=True  # Создать документ, если не найден
)