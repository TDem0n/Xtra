import json
import time
from datetime import datetime, timedelta, timezone
from aiogram.types import Message
import types
import ast

import time
from time import gmtime

# Директория, в которой находится файл (например, /some/path/)
import os
fp = os.path.abspath(__file__)
basedir = os.path.dirname(fp)+("/" if not fp.endswith('/') else "")

#from datetime import *
def time2str(structtime, format_="%Y-%m-%d %H:%M"):
    return time.strftime(format_, structtime)
def str2time(stringtime, format_="%Y-%m-%d %H:%M"):
    return time.strptime(stringtime, format_)


#import my python code
import apis
from timer import timer

#usage of gpt api
#inp - input text, str.
#returns text answer of chatgpt, str
#apis.GPT("Hi, GPT")


#usage of news api
#country - target news country, str, default="ru".
#returns list of dicts of news, list[dict]
#apis.News(country="ru")
maxcache = 200

def splitlist(inplist: list, itemsinpart:int=30):
    import math
    parts = []
    for starti in range(0, len(inplist), itemsinpart):
        parts.append(inplist[starti:starti+itemsinpart])
    return parts

def difftime(reduced, subtr):
    reduced = datetime(*reduced[:6])
    new_time_datetime = reduced - subtr
    return new_time_datetime.timetuple()

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

def delold(news: list, limitfresh: timedelta):
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

def BigNews(profile):
    #get news:
    news = apis.News()
    news = splitlist(news, 30)

    #get prompt txt:
    with open(basedir+"finalpromptgpt.txt", encoding="utf-8") as f:
        promptgpt = f.read()

    answersgpt = []
    for newspart in news:
        newsstrpart = ""
        for num,new in enumerate(newspart):
            newsstrpart += f'\t{num+1}. {new["content"]}\n\n'
        newsstrpart = newsstrpart[:-2]
        inpgpt = promptgpt+"\n\n\tПрофиль пользователя:\n"+profile+"\n\tНовости:\n"+newsstrpart
        ansgpt = apis.GPT(inp=inpgpt, model="gpt-4o-mini")
        answersgpt.append(ansgpt)
    #print("news:\n"+str(news)+"\nend\n\n")
    answer = "\n\n".join(answersgpt)
    return answer

def GetNews(services = ["ria", "e1"]):
    with open(basedir+"servpath.json") as f:
        servpath = json.load(f)
    news = []
    for service in services:
        with open(basedir+servpath[service], encoding="utf-8") as f:
            news.extend(json.load(f))
    return news

async def StepwiseNews(profile:str="Нет профиля", source:str|list=["ria"], timeframe:float|int=24, newspart:int=40, 
                 message:Message|types.NoneType=None, delayinfo=5, caching=True, 
                 llm="deepseek", llm1=None, llm2=None, model="gpt-4o-mini", model1=None, model2=None):
    """
    returns llm's filtered news after 2-step analysis\n\n
    'profile' is user's profile, may include his interests and place of living\n
    'source' indecates the way of receiving news and the source/sources\n
    'timeframe' is limit of oldness of news in hours\n
    'newspart' splits all found news into parts with the number of news equal to this value\n
    'message' if is not None, function answers to this message with information about progress\n
    'delayinfo' sets delay in seconds between sending messages about progress if 'message' is not None\n
    'caching' switches execution using caching gpt and without it\n
    'llm' is the service of LLM in ProxyAPI. Now available are only 'openai' or 'deepseek'
    """
    progress = message is not None
    if progress: 
        tmr = timer()
    nn=0
    if type(source)==str: source = source.lower()
    if source=="last": news = apis.News()
    elif type(source) == list: 
        news = GetNews(services=source)
    news = delold(news, timedelta(hours=float(timeframe)))

    answers = []
    with open(basedir+"middlepromptgpt.txt", encoding="utf-8") as f:
        middlepromptgpt = f.read()
    newscont = []
    for new in news:
        newscont.append(f'\t{new["content"]}\nСсылка: {new["link"]}')
    with open(basedir+"cachednews.json", encoding="utf-8") as f:
        cache = json.load(f)
    # define the common prompt on the first step
    commonprompt = f"{middlepromptgpt}\n\n\tПрофиль пользователя:\n{profile}\n\tНовости:\n"
    if not commonprompt in cache:
        print("There isn't commonprompt:", commonprompt, sep="\n")
    if caching and commonprompt in cache:
        for cachenews in cache[commonprompt]:
            lstcachenews = ast.literal_eval(cachenews)
            # if each of cached news is included in input actual news
            if set(lstcachenews).issubset(newscont):
                print("Cool, using cache")
                # Adding cached result
                answers.append(cache[commonprompt][cachenews]["res"])
                # Deleting processed news
                newscont = [x for x in newscont if x not in lstcachenews]
                with open(basedir+"cachednews.json", encoding="utf-8") as f:
                    cache_ = json.load(f)
                # updating date & time of last use in cache to denote its relevance
                cache_[commonprompt][cachenews]["dt"] = time2str(gmtime())
                with open(basedir+"cachednews.json", "w", encoding="utf-8") as f:
                    json.dump(cache_, f)
    # if after getting cached results there are some news yet or if caching is off,
    # processing the remaining news using gpt's api
    progress_msg = None
    if len(newscont)>0:
            # split news into a few parts
            news = splitlist(newscont, newspart)
            # processing each of part
            for newspart in news:
                # getting common sting of a whole part of news
                newsstrpart = '\n'.join(newspart)
                # define input to gpt
                inpgpt = commonprompt+newsstrpart
                # getting answer from gpt

                ansgpt = await apis.LLM(inp=inpgpt, service=(llm if not llm1 else llm1), model=(model if not model1 else model1), caching=caching, pr_io=False)

                # caching news
                with open(basedir+"cachednews.json", encoding="utf-8") as f:
                    cache_ = json.load(f)
                if commonprompt not in cache_: cache_[commonprompt] = {}
                cache_[commonprompt][repr(newspart)] = {
                    "res": ansgpt,
                    "dt": time2str(gmtime())
                }
                with open(basedir+"cachednews.json", "w", encoding="utf-8") as f:
                    json.dump(cache_, f)

                # adding answer to list
                answers.append(ansgpt)
                # if showing progress is on and from last notification about progress (or from start of process) passed more than given
                if progress and tmr.passed.seconds > delayinfo:
                    # notify about progress
                    prgrs = f"Обработка других событий {nn+1}/{len(news)}"
                    if progress_msg == None: 
                        progress_msg = await message.answer(prgrs)
                    else: await progress_msg.edit_text(prgrs)
                    # starting a new timer from this notification
                    tmr = timer()
                nn += 1
    with open(basedir+"cachednews.json", encoding="utf-8") as f:
        cache = dict(json.load(f))
    if len(cache) > maxcache:
        cache_=cache.copy()
        dt_cache = {}
        for fst in cache_:
            for scd in cache_[fst]:
                dt_cache[(fst, scd)] = str2time(cache_[fst][scd]["dt"])
        sorted_keys = sorted(dt_cache.keys(), key=lambda k: str2time(dt_cache[k]))
        for keys in sorted_keys[:len(cache)-maxcache]:
            cache_[keys[0]].pop(keys[1])
        with open(basedir+"cachednews.json", "w", encoding="utf-8") as f:
            json.dump(cache_, f)
    answer = "\n\n".join(answers)
    with open(basedir+"finalpromptgpt.txt", encoding="utf-8") as f:
        finalpromptgpt = f.read()
    inpgpt = finalpromptgpt+"\n\n\tПрофиль пользователя:\n"+profile+"\n\tНовости (нумерация может быть неверной):\n"+answer
    ansgpt = await apis.LLM(inp=inpgpt, service=(llm if not llm2 else llm2), model=(model if not model2 else model2), caching=caching, pr_io=False)
    if progress and progress_msg != None: await progress_msg.delete()
    return ansgpt

def Weather(city:str, profile:str="Нет профиля", source:str="openmeteo", enquiry=None):
    with open(basedir+"weatherprompt.txt", encoding="utf-8") as f:
        wprompt = f.read()
    wthr = apis.Weather(city, service=source)
    wthr = "\n\n".join(wthr)
    inpt = f"{wprompt}\nПрофиль пользователя:\n{profile}\n\nПогода:\n{wthr}"
    if enquiry != None: inpt += f"\n\nДоп. запрос пользователя: {enquiry}"
    #print(inpt) # Excess printing
    ansgpt = apis.GPT(inpt)
    noweather = "ничего необычного"
    if noweather.lower() in ansgpt.lower():
        return None
    return ansgpt