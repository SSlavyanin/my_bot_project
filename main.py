from flask import Flask
import logging
import openai
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!'

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logging.info("Starting bot...")

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

SYSTEM_PROMPT = "Ты — AIlex, эксперт по AI-автоматизации и заработку. Отвечаешь кратко, по делу, с идеями."

# Обновлённая функция генерации ответа
async def generate_reply(user_message: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "ShelezyakaBot",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistralai/mistral-7b-instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)

        if response.status_code != 200:
            logging.error(f"OpenRouter API Error {response.status_code}: {response.text}")
            return "❌ Ошибка при обращении к OpenRouter. Попробуйте позже."

        data = response.json()

        if 'choices' not in data:
            logging.error(f"Неверный ответ от OpenRouter: {data}")
            return "❌ Неверный ответ от OpenRouter. Попробуйте позже."

        return data['choices'][0]['message']['content']

    except Exception as e:
        logging.exception("❌ Ошибка при генерации ответа:")
        return "⚠️ Произошла непредвиденная ошибка. Попробуйте позже."

# Обработка сообщений
@dp.message_handler()
async def handle_message(message: Message):
    if message.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in message.text:
            user_msg = message.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            reply = await generate_reply(user_msg)
            await message.reply(reply)
    else:
        reply = await generate_reply(message.text)
        await message.reply(reply)

if __name__ == "__main__":
    from threading import Thread
    def run():
        app.run(host='0.0.0.0', port=8080)
    Thread(target=run).start()

    executor.start_polling(dp, skip_updates=True)
