import os
import logging
import asyncio
import random
from flask import Flask
from threading import Thread
import httpx
import xml.etree.ElementTree as ET
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram.dispatcher.filters import CommandStart

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TOOLS_URL = os.getenv("TOOLS_URL")
AILEX_SHARED_SECRET = os.getenv("AILEX_SHARED_SECRET")

# 🔧 Настройка
GROUP_ID = -1002572659328
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# 🌐 Flask (пинг Render)
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is alive!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# 🔁 Темы
TOPICS = [
    "Как ИИ меняет фриланс",
    "Заработок с помощью нейросетей",
    "Лучшие AI-инструменты апреля",
    "Как автоматизировать рутину с GPT",
    "ИИ-контент: быстро, дёшево, качественно"
]
topic_index = 0
rss_index = 0
use_topic = True

# 💡 Постинг
SYSTEM_PROMPT = (
    "Ты — AIlex, нейрочеловек, Telegram-эксперт по ИИ и автоматизации. "
    "Пиши пост как для Telegram-канала: ярко, живо, с юмором, кратко и по делу. "
    "Используй HTML-разметку: <b>жирный</b> текст, <i>курсив</i>, эмодзи, списки. "
    "Не используй Markdown. Не объясняй, что ты ИИ. Просто сделай крутой пост!"
)

def create_keyboard():
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("🤖 Обсудить с AIlex", url="https://t.me/ShilizyakaBot?start=from_post")
    )

# RSS
async def get_rss_titles():
    RSS_FEED_URL = "https://habr.com/ru/rss/"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(RSS_FEED_URL)
            if r.status_code != 200:
                logging.warning(f"⚠️ Не удалось получить RSS. Статус: {r.status_code}")
                return []
            root = ET.fromstring(r.text)
            return [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
    except Exception as e:
        logging.error(f"Ошибка RSS: {e}")
        return []

# Генерация поста
async def generate_reply(user_message: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "AIlexBot"
    }
    payload = {
        "model": "meta-llama/llama-4-maverick",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
        data = r.json()
        return data['choices'][0]['message']['content'] if 'choices' in data else "⚠️ Ошибка генерации"

def quality_filter(text: str) -> bool:
    if len(text.split()) < 20: return False
    if any(x in text.lower() for x in ["извин", "не могу", "как и было сказано"]): return False
    return True

# Автопостинг
async def auto_posting():
    global topic_index, rss_index, use_topic
    while True:
        topic = None
        if use_topic and topic_index < len(TOPICS):
            topic = TOPICS[topic_index]
            topic_index += 1
        else:
            rss_titles = await get_rss_titles()
            if rss_titles:
                topic = rss_titles[rss_index % len(rss_titles)]
                rss_index += 1
        use_topic = not use_topic

        if topic:
            try:
                post = await generate_reply(topic)
                post = post.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
                if quality_filter(post):
                    await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                    logging.info(f"✅ Пост отправлен: {topic}")
            except Exception as e:
                logging.error(f"Ошибка постинга: {e}")
        await asyncio.sleep(60 * 30)

# Self-ping
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# 🎯 Генерация инструмента
async def generate_tool_via_api(task: str, params: dict) -> str:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                TOOLS_URL,
                headers={"Ailex-Shared-Secret": AILEX_SHARED_SECRET},
                json={"task": task, "params": params}
            )
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", str(data))
    except Exception as e:
        logging.error(f"Ошибка запроса к тулс-боту: {e}")
        return "⚠️ Не удалось связаться с тулс-ботом."

# 📩 Личка + чат
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        await msg.reply("Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. Напиши, что хочешь — и я сделаю инструмент или дам идею!")

@dp.message_handler()
async def reply_handler(msg: types.Message):
    if msg.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in msg.text:
            cleaned = msg.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            response = await generate_reply(cleaned)
            await msg.reply(response, parse_mode=ParseMode.HTML)
    else:
        # Личка: определяем, это инструмент или просто вопрос
        lines = msg.text.strip().splitlines()
        task = lines[0]
        params = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                params[k.strip()] = v.strip()
        if len(params) >= 1:
            result = await generate_tool_via_api(task, params)
            await msg.reply(result, parse_mode=ParseMode.HTML)
        else:
            response = await generate_reply(msg.text)
            await msg.reply(response, parse_mode=ParseMode.HTML)

# 🔄 Запуск
async def main():
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    await dp.start_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
