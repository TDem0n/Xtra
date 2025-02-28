import time, json
from datetime import datetime, timedelta, timezone

import apis, timer, data

services = ["ria", "e1", "ixbt"]
# Директория, в которой находится файл (например, /some/path/)
import os
fp = os.path.abspath(__file__)
basedir = os.path.dirname(fp)+("/" if not fp.endswith('/') else "")

laststep = timer.timer()

def uniqdicts(l):
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


async def step(limit_collect=timedelta(hours=48)):
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

waitmins = 120