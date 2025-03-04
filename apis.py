from openai import OpenAI
import requests
import xmltodict
import json
from typing import Literal
import aiohttp, aiofiles, asyncio
from datetime import datetime
import os
from dotenv import load_dotenv
from datetime import timezone

import data as db

load_dotenv()

import sys
sys.stdout.reconfigure(encoding='utf-8')

api_url = "https://api.proxyapi.ru/openai/v1/chat/completions"
api_key = os.getenv("PROXYAPI_KEY")
# URL RSS-архива РИА Новости
riaurl = "https://ria.ru/export/rss2/archive/index.xml"
e1url = "https://www.e1.ru/rss-feeds/rss.xml"
weatherurl = "https://meteoinfo.ru/rss/forecasts/index.php?"
weather_s = {"Екатеринбург": "28440", "екб": "28440", "Yekaterinburg": "28440"}
# Директория, в которой находится файл (например, /some/path/)
import os
fp = os.path.abspath(__file__)
basedir = os.path.dirname(fp)+("/" if not fp.endswith('/') else "")

import time
from time import gmtime
#from datetime import *
def time2str(structtime, format_="%Y-%m-%d %H:%M"):
    return time.strftime(format_, structtime)
def str2time(stringtime, format_="%Y-%m-%d %H:%M"):
    return time.strptime(stringtime, format_)

max_cachelen = 200
max_cache_KiB = 1000.0

proxyapi_url = "https://api.proxyapi.ru"

serv_urls = {"openai": "openai/v1/chat/completions",
            "deepseek": "deepseek/chat/completions"}


async def LLM(
    inp: str,
    service: Literal['openai','deepseek'] = "deepseek",
    model: str = "gpt-3.5-turbo",
    caching: bool = True,
    pr_io: bool = False,
    pr_c: bool = True,
    timeout: int|float = 6000,
    attempt_time: int|float = 3000,
    max_retries: int = 3
) -> str:
    
    if pr_io: 
        print("LLM's input:", inp)

    # Асинхронная работа с кэшем
    cache = {}
    try:
        cache = await db.getllmcache() # DB usage
        async with aiofiles.open("cachellm.json", mode="r", encoding="utf-8") as f:
            cache = json.loads(await f.read())  # Del
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    txtcache = f"{service} {model}\n\n{inp}"
    
    # Проверка кэша
    if caching and txtcache in cache:
        if pr_c: 
            print("using cached result")
        cache[txtcache]["dt"] = datetime.now(timezone.utc).isoformat()
        await db.setllmcache(cache)
        async with aiofiles.open("cachellm.json", mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(cache, ensure_ascii=False))
        if pr_io: 
            print("LLM's answer:", cache[txtcache]["res"])
        return cache[txtcache]["res"]

    if caching and pr_c: 
        print("using real api LLM")

    # Подготовка запроса
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": inp}],
        "max_tokens": 2048
    }

    # Асинхронный запрос с повторными попытками
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        for attempt in range(max_retries):
            try:
                async with session.post(
                    f"{proxyapi_url}/{serv_urls[service]}",
                    json=payload,
                    headers=headers,
                    timeout=attempt_time
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        restext = data["choices"][0]["message"]["content"]
                        break
                    else:
                        restext = f"{response.status}: {await response.text()}"
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1.5 ** attempt)
                            continue
            except Exception as e:
                restext = f"Connection error: {str(e)}"
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.5 ** attempt)
                    continue
                raise

    # Обработка результата
    if "<think>" in restext and "</think>" in restext:
        restext = restext.split("</think>")[1].strip()

    # Обновление кэша
    if caching and not restext.startswith("Error"):
        cache[txtcache] = {
            "res": restext,
            "dt": datetime.now(timezone.utc).isoformat()
        }
        from pympler.asizeof import asizeof
        # Асинхронное сохранение кэша с очисткой
        i = 0
        while asizeof(cache)/1024 > max_cache_KiB:
            if i == 0: sorted_keys = sorted(cache.keys(), key=lambda k: cache[k]["dt"])
            del cache[sorted_keys[i]]
            i+=1
        
        await db.setllmcache(cache) # DB usage
        async with aiofiles.open("cachellm.json", mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(cache, ensure_ascii=False))    # Del

    if pr_io: 
        print(f"LLM's {'answer' if not restext.startswith('Error') else 'error'}:", restext)

    return restext
    
#GPT API using caching
async def GPT(inp, model='gpt-3.5-turbo', caching=True, pr_io=False, pr_c=True):
    return await LLM(inp, service='openai', model=model, caching=caching, pr_io=pr_io, pr_c=pr_c)
    
def NewsdataNews(country="ru"):
    got = requests.get(f"https://newsdata.io/api/1/latest?country={country}&language={country}&apikey=pub_64712c3faa88a3b936d740c91d69ab4508fee")
    results = dict(got.json())["results"]
    for r in range(len(results)):
        results[r]["content"] = results[r]["description"]
    return results

def RIANews() -> list:
    try:
        # Загрузка XML-файла
        response = requests.get(riaurl)
        response.raise_for_status()  # Проверка на ошибки HTTP

        # Преобразование содержимого XML в словарь
        xml_content = response.content.decode("utf-8")

        dict_content = xmltodict.parse(xml_content, encoding="utf-8")
        return extract_news(dict_content)
    except Exception as e:
        print("RIA error:", e)
        return None

def E1News():
    try:
        # Загрузка XML-файла
        response = requests.get(e1url)
        response.raise_for_status()  # Проверка на ошибки HTTP

        # Преобразование содержимого XML в словарь
        xml_content = response.content.decode("utf-8")

        dict_content = xmltodict.parse(xml_content, encoding="utf-8")
        return extract_news(dict_content)
    except Exception as e:
        print("news E1 error:", e)
        return None
    
import feedparser

def ixbtNews():
    """
    Получает данные из RSS-фида iXBT и возвращает их в виде списка словарей.
    """
    url = 'https://www.ixbt.com/export/news.rss'
    news_list = []
    
    try:
        # Получаем данные через requests для контроля ошибок
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Парсим RSS с помощью feedparser
        feed = feedparser.parse(response.content)
        
        # Формируем список новостей
        for entry in feed.entries:
            news_item = {
                'title': entry.get('title', 'Без заголовка'),
                'link': entry.get('link', 'Без ссылки'),
                'pubDate': entry.get('published', 'Без даты'),
                'content': entry.get('description', 'Нет содержания')
            }
            news_list.append(news_item)
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении RSS-фида iXBT: {e}")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка при парсинге iXBT: {e}")
    
    return news_list

def raise_():
    raise ValueError("Hi")
    
def News(country="ru", service="ria") -> list:
    """
    returns list of dicts of news
    """
    servfunc = {"ria": RIANews, "newsdata": NewsdataNews, "e1": E1News, "ixbt": ixbtNews}
    act = servfunc.get(service.lower(), None)
    if act == None: 
        raise ValueError(f"Wrong name of service {service}")
        return
    return act()

# Функция для создания списка новостей
def extract_news(data: dict):
    # Проверяем наличие данных о новостях
    items = data.get('rss', {}).get('channel', {}).get('item', [])
    # Формируем список новостей
    news_list = [
        {
            'title': item.get('title', 'Без заголовка'),
            'link': item.get('link', 'Без ссылки'),
            'pubDate': item.get('pubDate', 'Без даты'),
            'content': item.get('title', 'Нет содержания')
        }
        for item in items
    ]
    return news_list


def Meteoinfo(city="екб"):
    url = weatherurl+"s="+weather_s[city]
    response = requests.get(url)
    response.raise_for_status()  # Проверка на ошибки HTTP
    xml_content = response.content.decode()
    dict_content = xmltodict.parse(xml_content, encoding="utf-8")
    items = dict_content["rss"]["channel"]["item"]
    res = []
    for item in items:
        res.append(f'{item["title"]}:\n{item["description"]}')
    return res

from typing import Dict
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

def get_coordinates(city: str) -> tuple:
    geolocator = Nominatim(user_agent="weather_app")
    try:
        location = geolocator.geocode(city + ", Russia")
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except (GeocoderTimedOut, GeocoderServiceError):
        return None, None

def forecast_openmeteo(city: str) -> Dict:
    lat, lon = get_coordinates(city)
    
    if not lat or not lon:
        return {"error": "City not found or geocoding service is unavailable"}

    base_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,pressure_msl_mean,weathercode,windspeed_10m_max&timezone=auto&forecast_days=14"

    try:
        response = requests.get(base_url)
        response.raise_for_status()
        data = response.json()

        forecast = {}
        for i, date in enumerate(data['daily']['time']):
            temperature = {
                'max': data['daily']['temperature_2m_max'][i],
                'min': data['daily']['temperature_2m_min'][i]
            }
            pressure = data['daily']['pressure_msl_mean'][i]
            precipitation = data['daily']['precipitation_sum'][i]
            description = get_weather_description(data['daily']['weathercode'][i])
            windspeed = data['daily']['windspeed_10m_max'][i]  

            
            full_description = [
                f"Температура: от {temperature['min']}°C до {temperature['max']}°C",
                f"Давление: {pressure} гПа",
                f"Осадки: {precipitation} мм",
                f"Максимальная скорость ветра: {windspeed} км/ч",
                f"Описание: {description}"
            ]
            
            forecast[date] = {
                'temperature': temperature,
                'pressure': pressure,
                'precipitation': precipitation,
                'windspeed': windspeed,
                'description': description,
                'full_description': "\n".join(full_description)
            }

        return forecast
    except requests.RequestException as e:
        return {"error": f"Failed to retrieve weather data: {e}"}

def get_weather_description(weathercode: int) -> str:
    descriptions = {
        
        0: "Ясно",
        
        
        1: "В основном ясно",
        
        
        2: "Частично облачно",
        
        
        3: "Облачно",
        
        
        45: "Туман",
        
        
        51: "Легкая морось",
        53: "Умеренная морось",
        55: "Сильная морось",
        
        
        56: "Легкая морось с ледяной коркой",
        57: "Сильная морось с ледяной коркой",
        
        
        61: "Легкий дождь",
        63: "Умеренный дождь",
        65: "Сильный дождь",
        
        
        66: "Легкий дождь с ледяной коркой",
        67: "Сильный дождь с ледяной коркой",
        
        
        71: "Легкий снег",
        73: "Умеренный снег",
        75: "Сильный снег",
        
        
        77: "Снег с ледяной коркой",
        
        
        80: "Легкий ливень",
        81: "Умеренный ливень",
        82: "Сильный ливень",
        
        
        85: "Легкий снегопад",
        86: "Сильный снегопад",
        
        
        95: "Гроза",
        96: "Гроза с градом",
        99: "Гроза с сильным градом"
    }
    
    
    if weathercode not in descriptions:
        return f"Неизвестное погодное условие (код {weathercode})"
    
    return descriptions[weathercode]

def OpenMeteo(city: str):
    forecast = forecast_openmeteo(city)
    res = []
    for date, wthr in forecast.items():
        res.append(f"{date}\n{wthr['full_description']}")
    return res

def Weather(city:str, service:str="openmeteo"):
    if service.lower() == "meteoinfo":
        return Meteoinfo(city)
    elif service.lower() in ("openmeteo", "open-meteo"):
        return OpenMeteo(city)
    raise ValueError(f"Unknown service for weather API: {service}")