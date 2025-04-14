import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import httpx
import random
from datetime import datetime

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
TARGET_CHAT_ID = -1002572659328

# 🌐 Flask-сервер
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!'

# 🔁 Self-ping
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
            logging.info("Self-ping sent.")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# 🤖 Логгирование и инициализация
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

SYSTEM_PROMPT = "Ты — AIlex, нейрочеловек. Пиши живо, легко, умно. Кратко, с идеями, как будто делишься своими находками. Без занудства. Стиль ближе к Telegram, допускается сленг, примеры, риторические вопросы."

TOPICS = [
    "Как использовать ИИ в повседневной жизни?",
    "Как автоматизировать работу с помощью нейросетей?",
    "Как зарабатывать с помощью ИИ?",
    "Идеи для пассивного дохода с ИИ",
    "Как ИИ помогает бизнесу расти?",
    "Нейросети в фрилансе: что умеют и как применить?",
    "ИИ и автоматизация в социальных сетях",
    "Как сделать ИИ-ассистента для себя?",
    "10 идей заработка с ChatGPT",
    "Что можно делегировать ИИ прямо сейчас?"
]

# ✨ Генерация текста через OpenRouter
async def generate_reply(user_message: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "AIlexBot"
    }
    payload = {
        "model": "openchat/openchat-3.5:free",
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

# 💬 Ответы в чате
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

# 📣 Автопостинг
async def autopost_loop():
    while True:
        try:
            topic = random.choice(TOPICS)
            post = await generate_reply(topic)
            timestamp = datetime.now().strftime("%H:%M")
            await bot.send_message(TARGET_CHAT_ID, f"{post}\n\n🕒 {timestamp}")
            logging.info("Пост отправлен.")
        except Exception as e:
            logging.error(f"Ошибка при отправке автопоста: {e}")
        await asyncio.sleep(60 * 60 * 2.5)  # каждые 2.5 часа

@dp.message_handler(commands=['start_posts'])
async def start_posts(message: types.Message):
    asyncio.create_task(autopost_loop())
    await message.reply("Автопостинг запущен.")

# 🚀 Старт
if __name__ == "__main__":
    def run_flask():
        app.run(host='0.0.0.0', port=8080)

    Thread(target=run_flask).start()

    loop = asyncio.get_event_loop()
    loop.create_task(self_ping())
    executor.start_polling(dp, skip_updates=True)
