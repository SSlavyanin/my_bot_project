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

# ✨ Генерация ответа от OpenRouter
async def generate_reply(user_message: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",  # можно заменить
        "X-Title": "ShelezyakaBot"
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

# 🔍 Фильтр качества поста
def is_post_quality_ok(text: str) -> bool:
    if len(text) < 200:
        return False
    if any(word in text.lower() for word in ["извините", "я всего лишь", "как модель", "не могу помочь"]):
        return False
    if not any(p in text for p in ["?", "!", "—", "-", "…"]):
        return False
    return True

# 📢 Автопостинг с фильтрацией
GROUP_ID = -1002572659328

async def auto_posting():
    while True:
        topic = random.choice(TOPICS)
        try:
            for _ in range(3):  # до 3 попыток
                post = await generate_reply(topic)
                if is_post_quality_ok(post):
                    break
                logging.info("Пост не прошёл фильтр.")
            else:
                post = "⚠ Не удалось сгенерировать достойный пост. Пропускаем."

            await bot.send_message(chat_id=GROUP_ID, text=post)
            logging.info("Пост отправлен.")
        except Exception as e:
            logging.error(f"Ошибка при отправке автопоста: {e}")
        await asyncio.sleep(60 * 60 * 2.5)  # 2.5 часа

# 🚦 Запуск автопостинга
@dp.message_handler(commands=["start_posts"])
async def start_posts(message: types.Message):
    async def safe_auto_posting():
        try:
            await auto_posting()
        except Exception as e:
            logging.error(f"Autoposting task crashed: {e}")
    asyncio.create_task(safe_auto_posting())
    await message.reply("🚀 Автопостинг запущен.")

# 💬 Ответы на сообщения
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

# 🌐 Запуск Flask и бота
if __name__ == "__main__":
    def run_flask():
        app.run(host='0.0.0.0', port=8080)

    Thread(target=run_flask).start()
    loop = asyncio.get_event_loop()
    loop.create_task(self_ping())
    executor.start_polling(dp, skip_updates=True)
