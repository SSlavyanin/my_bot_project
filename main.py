import os
import datetime
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

# 🪵 Настройка логов
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
logging.info(f"🔐 TOKEN загружен: {'Да' if BOT_TOKEN else 'Нет'}, API_KEY: {'Да' if OPENROUTER_API_KEY else 'Нет'}")

# 📍 ID Telegram-группы
GROUP_ID = -1002572659328
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

# 🤖 Бот и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# 🌐 Flask-приложение
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot is alive!"
def run_flask():
    logging.info("🚀 Flask запущен на 0.0.0.0:8080")
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

# 📡 RSS-заголовки
async def get_rss_titles():
    RSS_FEED_URL = "https://habr.com/ru/rss/"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(RSS_FEED_URL)
            logging.info(f"📥 Запрос RSS: {r.status_code}")
            if r.status_code != 200:
                return []
            root = ET.fromstring(r.text)
            titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
            logging.info(f"📚 Получено RSS-заголовков: {len(titles)}")
            return titles
    except Exception as e:
        logging.error(f"Ошибка при получении RSS: {e}")
        return []

# 🧼 HTML-фильтр
def clean_html_for_telegram(html: str) -> str:
    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "span"}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    cleaned = str(soup)
    logging.info(f"🧼 Очистка HTML: {cleaned[:80]}...")
    return cleaned

# 🧠 Генерация ответа
async def generate_reply(user_message: str) -> str:
    logging.info(f"🎯 Генерация по теме: {user_message}")
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
            logging.info(f"📡 Ответ от модели: {r.status_code}, keys: {list(data.keys())}")
            if r.status_code == 200 and 'choices' in data:
                response = data['choices'][0]['message']['content']
                response = response.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
                logging.info(f"✅ Генерация успешна, длина: {len(response)}")
                return response
            else:
                logging.error(f"Ошибка генерации: {data}")
                return "⚠️ Ошибка генерации"
    except Exception as e:
        logging.error(f"Ошибка при генерации текста: {e}")
        return "⚠️ Ошибка генерации"

# 🔎 Фильтр качества
def quality_filter(text: str) -> bool:
    if len(text.split()) < 20: return False
    if any(x in text.lower() for x in ["извин", "не могу", "как и было сказано"]): return False
    return True

# 📬 Автопостинг
async def auto_posting():
    global topic_index, rss_index, use_topic
    while True:
        topic = None
        try:
            logging.info(f"▶️ Цикл автопостинга. use_topic={use_topic}, topic_index={topic_index}, rss_index={rss_index}")
            if use_topic:
                topic = TOPICS[topic_index % len(TOPICS)]
                logging.info(f"🧠 Тема выбрана: {topic}")
                topic_index += 1
            else:
                rss_titles = await get_rss_titles()
                if rss_titles:
                    topic = rss_titles[rss_index % len(rss_titles)]
                    logging.info(f"📰 RSS тема выбрана: {topic}")
                    rss_index += 1
                else:
                    logging.warning("❌ Пустой список RSS-заголовков.")
            use_topic = not use_topic

            if topic:              
                dummy_message = types.Message(
                    message_id=0,
                    date=datetime.datetime.now(),
                    chat=types.Chat(id=0, type="private"),
                    from_user=types.User(id=0, is_bot=False, first_name="AIlex"),
                    text=topic
                )
                post = await generate_reply(topic)
                logging.info(f"📝 Пост получен: {post[:80]}...")
                if quality_filter(post):
                    await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                    logging.info("✅ Пост успешно отправлен")
                else:
                    logging.warning("⚠️ Пост не прошёл фильтр качества.")
            else:
                logging.warning("⚠️ Не выбрана тема для поста.")
        except Exception as e:
            logging.error(f"❌ Ошибка постинга: {e}")

        try:
            delay = 1800  # 30 минут
            logging.info(f"⏳ Ожидание {delay} секунд...")
            await asyncio.sleep(delay)
        except Exception as e:
            logging.error(f"❌ Ошибка в sleep: {e}")
            await asyncio.sleep(1800)

# 🔁 Self-ping
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
                logging.info("📡 Self-ping выполнен")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# /start
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        logging.info("👋 /start от пользователя")
        await msg.reply("Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. Чем могу помочь?")

# 📥 Ответ на сообщения
@dp.message_handler()
async def reply_handler(msg: types.Message):
    user_text = msg.text.strip()
    logging.info(f"📨 Сообщение от пользователя: {user_text[:50]}")
    if msg.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in msg.text:
            cleaned = msg.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            response = await generate_reply(cleaned, message=msg)
            await msg.reply(clean_html_for_telegram(response), parse_mode=ParseMode.HTML)
        return
    response = await generate_reply(msg.text, message=msg)
    await msg.reply(clean_html_for_telegram(response), parse_mode=ParseMode.HTML)

# 🚀 Запуск
async def main():
    logging.info("🚀 Бот запускается...")
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    await dp.start_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
