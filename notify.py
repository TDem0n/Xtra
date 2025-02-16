from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import asyncio

import json
import datetime, time
import technical, bot as bot_py

# Директория, в которой находится файл (например, /some/path/)
import os
fp = os.path.abspath(__file__)
basedir = os.path.dirname(fp)+("/" if not fp.endswith('/') else "")

scheduler = BackgroundScheduler()

def send_news(userid, bot):
    prof_path = basedir+"profiles.json"
    with open(prof_path) as f:
        profile = json.load(f)[userid]
    print("Отправляю сообщение...")
    asyncio.run(bot.send_message(userid, asyncio.run(technical.StepwiseNews(profile=profile))))
    print("Отправлено!")
userid = "5324202988"
hour, minute = 00, 14
scheduler.add_job(
            send_news,
            CronTrigger(hour=hour, minute=minute),
            args=[userid, bot_py.bot],
            id=f"{userid}_{hour}_{minute}"
        )
scheduler.start()

try:
    while True:
        pass
except Exception as e:
    print(e)