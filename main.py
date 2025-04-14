import os
import logging
import asyncio
import random
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROUP_ID = -1002572659328  # ID Telegram-группы
POST_INTERVAL = 9000  # 2.5 часа

OPENROUTER_API_URL = "https://openrouter.ai/api/v1"

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is alive!'

async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
            logging.info("Self-ping sent.")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

SYSTEM_PROMPT = (
    "Ты — AIlex, нейрочеловек. Пиши живо, легко, умно. "
    "Кратко, с идеями, как будто делишься своими находками. "
    "Без занудства. Стиль ближе к Telegram, допускается сленг, примеры, риторические вопросы."
)

TOPICS = [
    "Как использовать ИИ в повседневной жизни?",
    "Примеры автоматизации с помощью нейросетей",
    "Идеи пассивного дохода с AI-инструментами",
    "Топ-3 сервиса для заработка на ИИ без навыков",
    "Как сэкономить 10 часов в неделю с помощью ChatGPT?",
    "Новая профессия — AI-оператор. Что это?",
    "Автоматизация рутинных задач через Telegram-ботов",
    "Как бизнесу заработать больше с помощью нейросетей?",
    "Почему не поздно входить в AI в 2025?",
    "Как собрать автоворонку на базе ИИ за 1 вечер"
]

async def generate_post(topic: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "ShelezyakaBot"
    }
    payload = {
        "model": "nousresearch/nous-capybara-7b",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Напиши короткий, умный Telegram-пост на тему: {topic}"}
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(OPENROUTER_API_URL + "/chat/completions", json=payload, headers=headers)
        data = response.json()
        if "choices" not in data:
            logging.error(f"Ошибка генерации поста: {data}")
            return "⚠️ Не удалось сгенерировать пост."
        return data["choices"][0]["message"]["content"]

async def auto_posting():
    while True:
        topic = random.choice(TOPICS)
        post = await generate_post(topic)
        try:
            await bot.send_message(GROUP_ID, post)
            logging.info("Пост отправлен.")
        except Exception as e:
            logging.error(f"Ошибка при отправке автопоста: {e}")
        await asyncio.sleep(POST_INTERVAL)

@dp.message_handler(commands=["start_posts"])
async def start_posts(message: types.Message):
    await message.reply("🚀 Автопостинг запущен.")
    asyncio.create_task(auto_posting())

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

if __name__ == "__main__":
    def run_flask():
        app.run(host='0.0.0.0', port=8080)

    Thread(target=run_flask).start()
    loop = asyncio.get_event_loop()
    loop.create_task(self_ping())
    executor.start_polling(dp, skip_updates=True)
