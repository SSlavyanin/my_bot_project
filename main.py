import os
import logging
import asyncio
import random
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import httpx

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
        await asyncio.sleep(600)

# 🤖 Настройка логгирования и бота
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

SYSTEM_PROMPT = "Ты — AIlex, эксперт по AI-автоматизации и заработку. Пиши посты по делу, с идеями, кратко и понятно, без воды. Пост должен быть на 3-5 предложений."

# ✨ Генерация текста поста
async def generate_post(topic: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "ShelezyakaBot"
    }
    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Напиши Telegram-пост на тему: {topic}"}
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
        data = response.json()
        if "choices" not in data:
            logging.error(f"OpenRouter API error: {data}")
            return f"⚠️ Не удалось сгенерировать пост на тему: {topic}"
        return data['choices'][0]['message']['content']

# 💬 Команда для получения chat ID
@dp.message_handler(commands=["id"])
async def send_chat_id(message: types.Message):
    await message.reply(f"Chat ID: {message.chat.id}")

@dp.message_handler(commands=["start_posts"])
async def start_posts(message: types.Message):
    await message.reply("AIlex запускает автопостинг с генерацией контента!")
    asyncio.create_task(auto_post())

# 🔁 Автопостинг
GROUP_ID = -1002572659328
POST_INTERVAL = 2.5 * 60 * 60  # 2.5 часа

POST_TOPICS = [
    "ИИ в повседневной жизни",
    "Автоматизация бизнес-процессов",
    "Идеи заработка с помощью ИИ",
    "AI в контент-маркетинге",
    "Чат-боты для продаж",
    "AI в обучении и самообразовании",
    "Промпт-инжиниринг",
    "AI-инструменты для фриланса",
    "AI и удалённая работа",
    "Как зарабатывать с нейросетями"
]

async def auto_post():
    for topic in POST_TOPICS:
        try:
            post_text = await generate_post(topic)
            await bot.send_message(GROUP_ID, post_text)
            logging.info(f"Отправлен пост по теме: {topic}")
        except Exception as e:
            logging.error(f"Ошибка при отправке автопоста: {e}")
        await asyncio.sleep(random.randint(10, 20))  # задержка между постами

# 💬 Обработка сообщений
@dp.message_handler()
async def handle_message(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in message.text:
            user_msg = message.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            reply = await generate_post(user_msg)
            await message.reply(reply)
    else:
        reply = await generate_post(message.text)
        await message.reply(reply)

# 🚀 Запуск Flask и бота
if __name__ == "__main__":
    def run_flask():
        app.run(host='0.0.0.0', port=8080)

    Thread(target=run_flask).start()

    loop = asyncio.get_event_loop()
    loop.create_task(self_ping())
    executor.start_polling(dp, skip_updates=True)
