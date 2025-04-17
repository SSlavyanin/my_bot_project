import logging
import asyncio
import random
import httpx
import feedparser
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from flask import Flask
from threading import Thread
import os

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROUP_ID = -1002572659328

# Инициализация бота (используется только aiogram)
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")  # Aiogram bot
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

# Flask-приложение для Render self-ping
app = Flask(__name__)

@app.route('/')
def home():
    return "AIlex is alive"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Self-ping Render
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# Кнопка комментариев
def create_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Комментарии", url="https://t.me/c/2572659328")]
    ])
    return keyboard

# Фильтр качества (примитивный)
def quality_filter(post: str) -> bool:
    return len(post) > 100 and "ИИ" in post

# Глобальный список тем из RSS
topics = []

# Получение тем из RSS
async def fetch_topics_from_rss():
    global topics
    topics = []
    feed_urls = [
        "https://neurohype.tech/rss",
        "https://ain.ua/feed/",
        "https://thereisno.ai/feed"
    ]
    for url in feed_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get("title", "")
            if any(word in title for word in ["ИИ", "AI", "нейросеть", "автоматизация", "инструмент"]):
                topics.append(title)

# Генерация поста
async def generate_reply(topic: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [
            {"role": "system", "content": "Ты нейрочел AIlex — говоришь чётко, по делу, с идеями. Пишешь посты про ИИ, автоматизацию, заработок. Напоминай, что ты можешь создать такой инструмент под задачу."},
            {"role": "user", "content": f"{topic}"}
        ]
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            data = response.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            else:
                logging.error(f"Ошибка генерации: {data}")
                return ""
    except Exception as e:
        logging.error(f"Ошибка генерации (исключение): {e}")
        return ""

# Автопостинг
async def auto_posting():
    global topics
    await fetch_topics_from_rss()
    while True:
        if topics:
            topic = random.choice(topics)
            try:
                post = await generate_reply(f"{topic}. Напиши пост от имени AIlex. Упомяни, что он может создать такой инструмент.")
                if quality_filter(post):
                    await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard())
                    logging.info("✅ Пост отправлен")
                else:
                    logging.info("❌ Пост не прошёл фильтр")
            except Exception as e:
                logging.error(f"Ошибка постинга: {e}")
        else:
            logging.warning("⚠️ Нет тем для постинга.")
        await asyncio.sleep(60 * 60 * 2.5)

# Ответы на комментарии
@dp.message_handler()
async def handle_message(message: types.Message):
    if message.chat.id == GROUP_ID and message.reply_to_message:
        prompt = f"Комментарий: {message.text}\nОтветь от имени AIlex — чётко, по делу, как нейрочел."
        reply = await generate_reply(prompt)
        if reply:
            await message.reply(reply)

# Запуск
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    Thread(target=run_flask).start()
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
