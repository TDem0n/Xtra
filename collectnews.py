import time, json
from datetime import datetime, timedelta, timezone

import apis, timer

services = ["ria", "e1"]
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


def step(limit_collect=timedelta(hours=48)):
    with open(basedir+"servpath.json") as f:
        servpath = json.load(f)
    for service in services:
        with open(basedir+servpath[service], encoding="utf-8") as f:
            newsstream = json.load(f)
        oldlen = len(newsstream)
        newsstream = delold(newsstream, limit_collect)
        print(f"Deleted {oldlen-len(newsstream)} old news of {service}")

        freshnews = apis.News(service=service)
        if freshnews is not None:
            for i,fnew in enumerate(freshnews):
                rnew = {}
                for key in ["content", "title", "link", "pubDate"]:
                    rnew[key] = fnew[key]
                freshnews[i] = rnew
            lenbefore = len(newsstream)
            newsstream = uniqdicts(newsstream+freshnews)
            with open(basedir+servpath[service], encoding="utf-8", mode="w") as f:
                json.dump(newsstream, f)
            print(f"Added {len(newsstream)-lenbefore} unique news of {service}")

        print(f"Now there's {len(newsstream)} unique fresh news of {service}")
        laststep = timer.timer()

waitmins = 120

"""while True:
    step()
    print(f"Waiting for {waitmins} minutes... Time: {time2str(time.localtime(), format_='%d.%m, %H:%M %S s')}")
    time.sleep(waitmins*60)
"""