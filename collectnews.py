import time, json
from datetime import datetime, timedelta, timezone, date
from typing import Literal

import apis, timer, data, afisha

services = ["ria", "e1", "ixbt"]
afisha_cities = ['ekaterinburg', 'msk']
# Директория, в которой находится файл (например, /some/path/)
import os
fp = os.path.abspath(__file__)
basedir = os.path.dirname(fp)+("/" if not fp.endswith('/') else "")

laststep = timer.timer()

def convert_lists_to_tuples(obj):
    """
    Recursively converts all lists in a nested iterable to tuples.
    Handles lists, tuples, and dictionaries. Other iterables (e.g., sets) are not modified.
    """
    if isinstance(obj, list):
        return tuple(convert_lists_to_tuples(item) for item in obj)
    elif isinstance(obj, dict):
        return {convert_lists_to_tuples(k): convert_lists_to_tuples(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        return tuple(convert_lists_to_tuples(item) for item in obj)
    else:
        return obj
    
to_hashable = convert_lists_to_tuples

def uniqdicts(l):
    l = to_hashable(l)
    return [dict(t) for t in {tuple(d.items()) for d in l}]

def difftime(reduced, subtr):
    reduced = datetime(*reduced[:6])
    new_time_datetime = reduced - subtr
    return new_time_datetime.timetuple()

def time2str(structtime, format_="%Y-%m-%d %H:%M"):
    return time.strftime(format_, structtime)
def str2time(stringtime, format_="%Y-%m-%d %H:%M"):
    return time.strptime(stringtime, format_)
def riadate2time(stringtime):
    # Формат времени в RSS RIA news
    date_format = "%a, %d %b %Y %H:%M:%S %z"

    # Преобразование строки в datetime с учетом временной зоны
    dt_local = datetime.strptime(stringtime, date_format)

    # Преобразование в UTC
    dt_utc = dt_local.astimezone(timezone.utc)

    # Преобразование в struct_time
    time_struct = dt_utc.timetuple()

    return time_struct

def noupdates() -> timedelta:
    global laststep
    return laststep.passed

def delold(news: list, limitfresh):
    lim = limitfresh
    gmt = time.gmtime()
    limit = difftime(gmt, lim)
    for iend in range(len(news), 0, -1):
        ind = len(news) - iend
        new = news[ind]
        timeofnew = riadate2time(new["pubDate"])
        if limit > timeofnew:
            news.pop(ind)
    return news

def delexpired(afisha_: list):
    gmt = time.gmtime()
    for iend in range(len(afisha_), 0 -1):
        ind = len(afisha_) - iend
        afsh = afisha_[ind]
        if gmt > get_max_date(afsh['dates']).timetuple():
            afisha_.pop(ind)
    return afisha_


def get_max_date(date_strings) -> datetime:
    # Словарь месяцев (родительный падеж)
    months = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    
    parsed_dates = []
    today = date.today()
    
    for date_str in date_strings:
        try:
            day_str, month_ru = date_str.split()
            day = int(day_str)
            month = months[month_ru.lower()]  # Для регистронезависимости
        except (ValueError, KeyError):
            continue  # Пропустить некорректные даты
            
        current_year = today.year
        # Создаём дату в текущем году
        try:
            current_date = date(current_year, month, day)
        except ValueError:
            continue  # Некорректная дата (например, 30 февраля)
        
        # Проверяем, прошла ли дата в текущем году
        if current_date >= today - timedelta(days=30): 
            parsed_dates.append(current_date)
        else:
            # Используем следующий год
            parsed_dates.append(date(current_year + 1, month, day))
    
    return max(parsed_dates) if parsed_dates else None


async def step(limit_collect=timedelta(hours=48), af_cities:list[Literal['ekaterinburg', 'msk']]=[]):
    global laststep
    with open(basedir+"servpath.json") as f:
        servpath = json.load(f)
    for service in services:
        with open(basedir+servpath[service], encoding="utf-8") as f:
            newsstream = json.load(f)
        newsstream2 = await data.getnews(service)
        oldlen, oldlen2 = len(newsstream), len(newsstream2)
        newsstream = delold(newsstream, limit_collect)
        newsstream2 = delold(newsstream2, limit_collect)
        print(f"Deleted {oldlen-len(newsstream)} old news of {service}")
        print(f"Deleted {oldlen2-len(newsstream2)} old news of {service} in MongoDB")

        freshnews = apis.News(service=service)
        if freshnews is not None:
            for i,fnew in enumerate(freshnews):
                rnew = {}
                for key in ["content", "title", "link", "pubDate"]:
                    rnew[key] = fnew[key]
                freshnews[i] = rnew
            lenbefore = len(newsstream)
            lenbefore2 = len(newsstream2)
            newsstream = uniqdicts(newsstream+freshnews)
            newsstream2 = uniqdicts(newsstream2+freshnews)
            with open(basedir+servpath[service], encoding="utf-8", mode="w") as f:
                json.dump(newsstream, f)
            await data.setnews(service, newsstream2)
            print(f"Added {len(newsstream)-lenbefore} unique news to {servpath[service]}")
            print(f"Added {len(newsstream2)-lenbefore2} unique news to {service} in MongoDB")

        print(f"Now there's {len(newsstream)} unique fresh news in {servpath[service]}")
        print(f"Now there's {len(newsstream2)} unique fresh news in {service} in MongoDB")
    laststep = timer.timer()
    for ct in af_cities:
        doc_name = "afisha: "+ct
        try:
            af = await data.getnews(doc_name)
        except:
            af = None
        if af == None:
            af = []
            # create document if it does not exist
            await data.setnews(doc_name, af)
        oldlen = len(af)
        af = delexpired(af)
        print(f"Deleted {oldlen-len(af)} afisha from city '{ct}'")
        fresh_af = await afisha.getall(ct, limits={'all': 3})
        print('end afisha')
        fresh_af_ = []
        from tqdm import tqdm
        for categ in tqdm(list(fresh_af)): 
            fresh_af_.append({'categoria': categ})
            for d in fresh_af[categ]: 
                for key_ in ['Name', 'url', 'description', 'dates']:
                    fresh_af_[-1][key_] = d[key_]
        print(len(fresh_af_))
        fresh_af = []
        for i,fraf in tqdm(enumerate(fresh_af_)):
            raf={}
            if type(fraf.get('dates', None)) != list: continue
            for key in ["url", "Name", "dates"]:
                raf[key] = fraf[key]
                if type(raf[key]) == list: raf[key]=tuple(raf[key])
            fresh_af.append(raf)
        lenbefore = len(af)
        af = uniqdicts(af+fresh_af)
        await data.setnews(doc_name, fresh_af)
        print(f"Added {len(af)-lenbefore} unique afisha to {ct} in MongoDB")