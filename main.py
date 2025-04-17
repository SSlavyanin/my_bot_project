import os
import logging
import asyncio
import random
import feedparser
from flask import Flask
from threading import Thread
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram.dispatcher.filters import CommandStart

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 🔧 Настройка
GROUP_ID = -1002572659328
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
RSS_FEED_URL = "https://thereisno.ai/feed"
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

# 📰 Получение заголовков из RSS
def get_titles_from_rss():
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        titles = [entry.title for entry in feed.entries if entry.title]
        if not titles:
            logging.warning("⚠️ Нет заголовков из RSS")
        return titles
    except Exception as e:
        logging.error(f"Ошибка чтения RSS: {e}")
        return []

# 📎 Кнопка под постом
def create_keyboard():
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("🤖 Обсудить с AIlex", url="https://t.me/ShilizyakaBot?start=from_post")
    )

# 📤 Генерация поста
SYSTEM_PROMPT = (
    "Ты — AIlex, нейрочеловек, Telegram-эксперт по ИИ и автоматизации. "
    "Пиши пост как для Telegram-канала: ярко, живо, с юмором, кратко и по делу. "
    "Используй HTML-разметку: <b>жирный</b> текст, <i>курсив</i>, эмодзи, списки. "
    "Не используй Markdown. Не объясняй, что ты ИИ. Просто сделай крутой пост!"
)

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
        if "choices" not in data:
            logging.error(f"Ошибка генерации: {data}")
            return "⚠️ Ошибка генерации"
        return data['choices'][0]['message']['content']

# ✅ Фильтр качества
def quality_filter(text: str) -> bool:
    if len(text.split()) < 20: return False
    if any(x in text.lower() for x in ["извин", "не могу", "как и было сказано"]): return False
    return True

# 🤖 Автопостинг
async def auto_posting():
    while True:
        titles = get_titles_from_rss()
        if not titles:
            await asyncio.sleep(300)
            continue
        topic = random.choice(titles)
        try:
            post = await generate_reply(topic)
            post = post.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
            if quality_filter(post):
                await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                logging.info("✅ Пост отправлен")
            else:
                logging.info("❌ Пост не прошёл фильтр")
        except Exception as e:
            logging.error(f"Ошибка постинга: {e}")
        await asyncio.sleep(60 * 60 * 2.5)

# 🔁 Self-ping
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# 💬 Обработка сообщений
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        await msg.reply(
            "Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. "
            "Чем могу помочь? Задай вопрос — и я сразу отвечу!"
        )

@dp.message_handler()
async def reply_handler(msg: types.Message):
    if msg.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in msg.text:
            cleaned = msg.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            response = await generate_reply(cleaned)
            await msg.reply(response, parse_mode=ParseMode.HTML)
    else:
        response = await generate_reply(msg.text)
        await msg.reply(response, parse_mode=ParseMode.HTML)

# ▶️ Запуск
async def main():
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    await dp.start_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
