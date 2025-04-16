import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import httpx
import random
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import ParseMode

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

# 🌐 Flask-сервер
app = Flask(__name__)
@app.route('/')
def home():
    return 'Bot is alive!'

# 📡 Self-ping
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# 🤖 Настройка бота
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# 🧠 SYSTEM PROMPT c HTML-разметкой
SYSTEM_PROMPT = (
    "Ты — AIlex, нейрочеловек, Telegram-эксперт по ИИ и автоматизации. "
    "Пиши пост как для Telegram-канала: ярко, живо, с юмором, кратко и по делу. "
    "Используй HTML-разметку: <b>жирный</b> текст, <i>курсив</i>, эмодзи, списки. "
    "Не используй Markdown. Не объясняй, что ты ИИ. Просто сделай крутой пост!"
)

# 🎯 Темы постов
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

GROUP_ID = -1002572659328

# 🧠 Генерация поста
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
        response = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
        data = response.json()
        if "choices" not in data:
            logging.error(f"OpenRouter API error: {data}")
            return "Ошибка генерации. Попробуй позже."
        return data['choices'][0]['message']['content']

# ✅ Фильтр качества
def quality_filter(text: str) -> bool:
    if len(text.split()) < 20:
        return False
    if any(w in text.lower() for w in ["извин", "не могу", "как и было сказано"]):
        return False
    if text.count("\n") < 1 and len(text) > 400:
        return False
    return True

# 📎 Кнопка "Обсудить с ботом"
def create_post_keyboard():
    chat_link = "https://t.me/ShilizyakaBot?start=from_post"  # Заменить на @username бота
    button = InlineKeyboardButton(text="🤖 Обсудить с AIlex", url=chat_link)
    keyboard = InlineKeyboardMarkup(row_width=1).add(button)
    return keyboard

# 📢 Отправка поста
async def post_with_button(post_text: str):
    keyboard = create_post_keyboard()
    try:
        await bot.send_message(chat_id=GROUP_ID, text=post_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Ошибка отправки поста: {e}")

# 🔁 Автопостинг
async def auto_posting():
    while True:
        topic = random.choice(TOPICS)
        try:
            post = await generate_reply(topic)
            if quality_filter(post):
                await post_with_button(post)
                logging.info("Пост отправлен.")
            else:
                logging.info("Пост не прошёл фильтр.")
        except Exception as e:
            logging.error(f"Ошибка при автопостинге: {e}")
        await asyncio.sleep(60 * 60 * 2.5)

# 🚀 Запуск автопостинга сразу
@dp.message_handler(commands=["start_posts"])
async def start_posts(message: types.Message):
    asyncio.create_task(auto_posting())
    await message.reply("🚀 Автопостинг запущен.")

# 💬 Ответы в личке и группах
@dp.message_handler()
async def handle_message(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in message.text:
            user_msg = message.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            reply = await generate_reply(user_msg)
            await message.reply(reply, parse_mode=ParseMode.HTML)
    else:
        reply = await generate_reply(message.text)
        await message.reply(reply, parse_mode=ParseMode.HTML)

# 🔁 Запуск Flask и бота
if __name__ == "__main__":
    def run_flask():
        app.run(host='0.0.0.0', port=8080)
    Thread(target=run_flask).start()
    loop = asyncio.get_event_loop()
    loop.create_task(self_ping())
    loop.create_task(auto_posting())  # ← автоматический старт
    executor.start_polling(dp, skip_updates=True)
