import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import httpx
import random
import time

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

# 🌐 Flask-сервер для Render
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!'

# 📌 Self-ping функция
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
            logging.info("Self-ping sent.")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)  # каждые 10 минут

# 🤖 Настройка логгирования и бота
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

SYSTEM_PROMPT = "Ты — AIlex, эксперт по AI-автоматизации и заработку. Отвечаешь кратко, по делу, с идеями."

# ✨ Генерация ответа от OpenRouter
async def generate_reply(user_message: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",  # Можно заменить на свой
        "X-Title": "ShelezyakaBot"
    }
    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
        data = response.json()
        if "choices" not in data:
            logging.error(f"OpenRouter API error: {data}")
            return "Ошибка генерации ответа. Попробуйте позже."
        return data['choices'][0]['message']['content']

# 💬 Обработка сообщений
@dp.message_handler()
async def handle_message(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in message.text:
            user_msg = message.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            reply = await generate_reply(user_msg)
            await message.reply(reply)
    else:
        reply = await generate_reply(message.text)
        await message.reply(reply)

# 📅 Автопубликация постов
async def auto_post():
    group_id = 2572659328
    topics = [
        "Как ИИ помогает оптимизировать бизнес-процессы.",
        "Автоматизация процессов с использованием нейросетей.",
        "Идеи для заработка с помощью AI: от создания приложений до консультаций.",
        "Как искусственный интеллект влияет на образование и обучение.",
        "Использование AI для предсказания трендов в бизнесе.",
        "Заработок на машинном обучении: от фриланса до стартапов.",
        "Какие навыки важны для работы с ИИ в будущем.",
        "Идеи для бизнеса с использованием чат-ботов и автоматизации.",
        "Как искусственный интеллект помогает в создании контента.",
        "Как AI помогает людям с ограниченными возможностями."
    ]
    
    while True:
        message = random.choice(topics)
        try:
            await bot.send_message(group_id, message)
            logging.info(f"Автопост: '{message}' отправлен в группу.")
            await asyncio.sleep(9000)  # Пауза 2.5 часа между постами
        except Exception as e:
            logging.error(f"Ошибка при отправке автопоста: {e}")

# 🚀 Запуск Flask и бота
if __name__ == "__main__":
    def run_flask():
        app.run(host='0.0.0.0', port=8080)

    Thread(target=run_flask).start()

    loop = asyncio.get_event_loop()
    loop.create_task(self_ping())  # запускаем self-ping
    loop.create_task(auto_post())  # запускаем автопубликацию
    executor.start_polling(dp, skip_updates=True)
