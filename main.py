import os
import logging
import asyncio
import random
from flask import Flask
from threading import Thread
import httpx
import xml.etree.ElementTree as ET
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from bs4 import BeautifulSoup

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 📍 ID Telegram-группы для автопостинга
GROUP_ID = -1002572659328
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

# 🧠 Настройка aiogram и логгирования
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# 🌐 Flask-приложение
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot is alive!"
def run_flask():
    app.run(host="0.0.0.0", port=8080)

# 📚 Темы
TOPICS = [
    "Как ИИ меняет фриланс",
    "Заработок с помощью нейросетей",
    "Лучшие AI-инструменты апреля",
    "Как автоматизировать рутину с GPT",
    "ИИ-контент: быстро, дёшево, качественно"
]
topic_index = 0
rss_index = 0
use_topic = True

# 🔘 Кнопка под постами
def create_keyboard():
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("🤖 Обсудить с AIlex", url="https://t.me/ShilizyakaBot?start=from_post")
    )

# 📡 RSS
async def get_rss_titles():
    RSS_FEED_URL = "https://habr.com/ru/rss/"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(RSS_FEED_URL)
            if r.status_code != 200:
                return []
            root = ET.fromstring(r.text)
            return [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
    except Exception as e:
        logging.error(f"Ошибка при получении RSS: {e}")
        return []

# 🔎 HTML фильтр
def clean_html_for_telegram(html: str) -> str:
    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "span"}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    return str(soup)

# 🤖 Генерация
async def generate_reply(user_message: str, message: types.Message) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "AIlexBot"
    }

    SYSTEM_PROMPT = (
        "Ты — AIlex, нейрочеловек, Telegram-эксперт по ИИ и автоматизации. "
        "Пиши пост как для Telegram-канала: ярко, живо, с юмором, кратко и по делу. "
        "Используй HTML-разметку: <b>жирный</b> текст, <i>курсив</i>, эмодзи, списки. "
        "Не используй Markdown. Не объясняй, что ты ИИ. Просто сделай крутой пост!"
    )

    payload = {
        "model": "meta-llama/llama-4-maverick",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
            data = r.json()
            if r.status_code == 200 and 'choices' in data:
                response = data['choices'][0]['message']['content']
                response = response.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
                return response
            else:
                logging.error(f"Ошибка генерации: {data}")
                return "⚠️ Ошибка генерации"
    except Exception as e:
        logging.error(f"Ошибка при генерации текста: {e}")
        return "⚠️ Ошибка генерации"

# ✅ Фильтр качества
def quality_filter(text: str) -> bool:
    if len(text.split()) < 20: return False
    if any(x in text.lower() for x in ["извин", "не могу", "как и было сказано"]): return False
    return True

# 📬 Автопостинг
async def auto_posting():
    global topic_index, rss_index, use_topic
    while True:
        topic = None
        if use_topic:
            topic = TOPICS[topic_index % len(TOPICS)]
            topic_index += 1
        else:
            rss_titles = await get_rss_titles()
            if rss_titles:
                topic = rss_titles[rss_index % len(rss_titles)]
                rss_index += 1
        use_topic = not use_topic

        if topic:
            try:
                dummy_message = types.Message(message_id=0, date=None,
                    chat=types.Chat(id=0, type="private"),
                    from_user=types.User(id=0, is_bot=False, first_name="AIlex"),
                    text=topic)
                post = await generate_reply(topic, message=dummy_message)
                if quality_filter(post):
                    await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                    logging.info(f"✅ Пост отправлен: {topic}")
            except Exception as e:
                logging.error(f"Ошибка постинга: {e}")
        await asyncio.sleep(60 * 30)

# 🔁 Self-ping
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# /start
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        await msg.reply("Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. Чем могу помочь?")

# 📥 Обработка сообщений
@dp.message_handler()
async def reply_handler(msg: types.Message):
    user_text = msg.text.strip()
    if msg.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in msg.text:
            cleaned = msg.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            response = await generate_reply(cleaned, message=msg)
            await msg.reply(clean_html_for_telegram(response), parse_mode=ParseMode.HTML)
        return

    response = await generate_reply(msg.text, message=msg)
    await msg.reply(clean_html_for_telegram(response), parse_mode=ParseMode.HTML)

# 🚀 Главный запуск
async def main():
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    await dp.start_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
