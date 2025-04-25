import time
import afisha_head2
import requests
import os
from bs4 import BeautifulSoup as BS
import math, asyncio
from typing import Literal

# +req-s: bs4, lxml
CATEGORIES = ['cinema', 'concert', 'theatre', 'standup', 'exhibition', 'kids', 'sport', 'party', 'excursion']

sp ={}
def parser_dates(url, session):
    res = session.get(url)
    soup = BS(res.text, 'lxml')
    try:
        #Кино
        dates_all = soup.find('div', class_='EYJyG MAmPU').find_all('button', class_='pdT6c')
        dates=[i['aria-label'] for i in dates_all if i['data-test'] != "DAY DISABLED"]
        return dates
    except:
        None
    try:
        #Театры
        a = soup.find('div',class_='B2EJj').find_all(class_='nW9Tc')
        dates = [i.find('time')['datetime'] for i in a]
        dates.append(soup.find('span', class_='TSyWq kiWzk').text)
        return dates
    except:
        None
    try:
        a = soup.find('span', class_='TSyWq kiWzk').text
        return a
    except:
        None
    return None


def parsing_page(url, session, cat):
    res = session.get(url)
    soup = BS(res.text, 'lxml')
    try:
        name = soup.find('title').text.rsplit('-',1)[0]
    except:
        name = 'Не найдено'
    try:
        description_2 = soup.find('div', class_='aEVDY t1V2l').text.strip()
    except:
        description_2 = ''
    dates = parser_dates(url, session)
    tabl = {
        "Name": name,
        'url': url,
        'description': f'{description_2}',
        'dates': dates
    }
    sp[cat].append(tabl)
    # with open(f"elem/{cat}.txt", 'a', encoding='utf-8') as file:
    #     file.write(str(tabl))
    return tabl

async def parsing_pages(session, categoria, city:str, limitpages=math.inf):
    sp[categoria] = []
    result = []

    # Создаем директорию 'src', если её нет
    #os.makedirs('src', exist_ok=True)

    page = 1
    while True:
        await asyncio.sleep(0)
        if page-1 >= limitpages: break
        try:
            if categoria in 'standupparty':
                url = f"https://www.afisha.ru/{city}/{categoria}/page{page}"
            else:
                url = f"https://www.afisha.ru/{city}/schedule_{categoria}/page{page}"
            print(f'{categoria}: {page}')


            res = session.get(url)
            #with open(f"src/{categoria}{page}.html", 'w', encoding='utf-8') as file:
            #    file.write(res.text)
            soup = BS(res.text, 'lxml')
            urls = soup.find_all("a", class_="CjnHd y8A5E nbCNS yknrM")
            if not urls:
                break
            for i in urls:
                i = i["href"]
                i = "https://www.afisha.ru" + i
                result.append(parsing_page(i,session,categoria))
                #time.sleep(0.4)
            page += 1
        except KeyboardInterrupt:
            break
    return result

async def getall(city:str = 'msk', limits:dict[Literal['cinema', 'concert', 'theatre', 'standup', 'exhibition', 'kids', 'sport', 'party', 'excursion']: int|Literal[math.inf]]={'all': math.inf}):
    res = {}
    categ = CATEGORIES.copy()
    session = requests.session()
    session.headers.update(afisha_head2.headers)
    limall = limits.get('all', math.inf)
    for categoria in categ:
        await asyncio.sleep(0)
        limit = limits.get(categoria, limall)
        try:
            res[categoria] = await parsing_pages(categoria=categoria ,session=session, city=city, limitpages=limit)
            print("parsing pages end")
            await asyncio.sleep(0)
        except KeyboardInterrupt:
            pass
    return res

import json, pickle, datetime

if __name__ == '__main__':
    print(datetime.datetime.now())
    afish = getall(city="ekaterinburg")
    #print(afish)
    """try:
        with open("afishmsk.json", "w") as f:
            json.dump(afish, f)
    except: pass"""

    """
    with open("afish.pkl", "wb") as f:
        pickle.dump(afish, f)
    """
    print(datetime.datetime.now())