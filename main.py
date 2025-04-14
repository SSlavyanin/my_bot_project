import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import httpx
import random

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

# 🌐 Flask-сервер для Render
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!'

# 📌 Self-ping
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
            logging.info("Self-ping sent.")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# 🤖 Настройка логгирования и бота
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

GROUP_ID = -1002572659328
SYSTEM_PROMPT = "Ты — AIlex, нейрочеловек. Пиши живо, легко, умно. Кратко, с идеями, как будто делишься своими находками. Без занудства. Стиль ближе к Telegram, допускается сленг, примеры, риторические вопросы."

# ✨ Генерация поста
async def generate_post():
    themes = [
        "Как использовать ИИ в повседневной жизни",
        "Простая автоматизация рутинных задач",
        "Идеи пассивного дохода с ИИ",
        "Боты для бизнеса: зачем и как",
        "ИИ как помощник в фрилансе",
        "5 AI-инструментов, которые сэкономят тебе время",
        "Новые тренды в AI-заработке",
        "Как сделать нейросеть своим партнёром по бизнесу",
        "Минималистичный способ заработка с ChatGPT",
        "ИИ в телеграм: каналы, боты и подписки"
    ]
    theme = random.choice(themes)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "AIlexBot"
    }
    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Напиши короткий пост в Telegram на тему: {theme}. Стиль — нейрочел, идеи, краткость, польза."}
        ]
    }
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
            data = res.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            logging.error(f"Ошибка генерации поста: {e}")
            return None

# ⏱️ Автопостинг
async def auto_poster():
    while True:
        post = await generate_post()
        if post:
            try:
                await bot.send_message(chat_id=GROUP_ID, text=post)
                logging.info("Пост отправлен.")
            except Exception as e:
                logging.error(f"Ошибка при отправке автопоста: {e}")
        await asyncio.sleep(3600 + random.randint(60, 300))  # ~1 час и небольшой разброс

# 💬 Обработка входящих сообщений
@dp.message_handler(commands=["start_posts"])
async def cmd_start(message: types.Message):
    if str(message.chat.id) == str(GROUP
