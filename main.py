import os
import time
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
from collections import defaultdict, deque

# 🧠 Память сессий (храним до 10 сообщений на пользователя)
user_sessions = defaultdict(lambda: deque(maxlen=10))
last_interaction = {}  # Время последнего взаимодействия

# 🪵 Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SELF_URL = os.getenv("SELF_URL", "https://my-bot-project-8wit.onrender.com/")

# ❗ Проверка обязательных переменных
if not BOT_TOKEN or not OPENROUTER_API_KEY:
    logging.critical("❌ Отсутствуют переменные BOT_TOKEN или OPENROUTER_API_KEY!")
    exit(1)

logging.info(f"🔐 TOKEN загружен: {'Да' if BOT_TOKEN else 'Нет'}, API_KEY: {'Да' if OPENROUTER_API_KEY else 'Нет'}")

# 📍 ID Telegram-группы
GROUP_ID = -1002572659328
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

# 🤖 Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# 🌐 Flask-приложение для self-ping
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot is alive!"

def run_flask():
    logging.info("🚀 Flask запущен на 0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
    

# 📚 Темы для автопостинга
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

# 🕒 Обновляем время последнего взаимодействия
def update_user_session(user_id):
    last_interaction[user_id] = time.time()
    logging.info(f"✅ Обновлено время взаимодействия с пользователем {user_id}")

# 🧹 Очистка неактивных сессий
async def clean_inactive_sessions():
    while True:
        current_time = time.time()
        for user_id, last_time in list(last_interaction.items()):
            if current_time - last_time > 1800:  # 30 мин
                del last_interaction[user_id]
                del user_sessions[user_id]
                logging.info(f"❌ Сессия пользователя {user_id} удалена из-за неактивности.")
        await asyncio.sleep(60)

# 🔘 Кнопка под постами
def create_keyboard():
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("🤖 Обсудить с AIlex", url="https://t.me/ShilizyakaBot?start=from_post")
    )

# 📡 Получение заголовков из RSS
async def get_rss_titles():
    RSS_FEED_URL = "https://vc.ru/rss"
    try:
        async with httpx.AsyncClient() as client:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = await client.get(RSS_FEED_URL, headers=headers)
            logging.info(f"📥 Запрос RSS: {r.status_code}")
            if r.status_code != 200:
                logging.warning(f"⚠️ Ответ Habr: {r.status_code}, текст: {r.text[:300]}")
                return []
   
            logging.debug(f"Кодировка ответа RSS: {r.encoding}") # Логирование кодировки ответа
            logging.debug(f"🔍 Ответ RSS: {r.text[:500]}")  # Лог первых 500 символов
            root = ET.fromstring(r.text)
            titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
            logging.info(f"📚 Получено RSS-заголовков: {len(titles)}")
            return titles
    except Exception as e:
        logging.error(f"❌ Ошибка при получении RSS: {e}", exc_info=True)
        return []

# 🧼 Очистка HTML-текста
def clean_html_for_telegram(html: str) -> str:
    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a"}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    cleaned = str(soup)
    logging.info(f"🧼 Очищенный HTML: {cleaned[:100]}...")
    return cleaned

# 🧠 Генерация ответа с OpenRouter
async def generate_reply(user_message: list) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/ShilizyakaBot",  # корректная ссылка
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
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + user_message
    }

    logging.info(f"📤 Отправка на OpenRouter: {[m['role'] + ': ' + m['content'][:60] for m in payload['messages']]}")

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
            data = r.json()
            if r.status_code == 200 and 'choices' in data:
                response = data['choices'][0]['message']['content']
                response = response.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
                logging.info("✅ Успешная генерация ответа")
                return response
            else:
                logging.error(f"⚠️ Ошибка генерации: {data}")
                return "⚠️ Ошибка генерации"
    except Exception as e:
        logging.error(f"❌ Ошибка при генерации текста: {e}")
        return "⚠️ Ошибка генерации"

# 📏 Фильтр качества поста
def quality_filter(text: str) -> bool:
    if len(text.split()) < 20:
        logging.warning("⚠️ Пост слишком короткий")
        return False
    if any(x in text.lower() for x in ["извин", "не могу", "как и было сказано"]):
        logging.warning("⚠️ Пост содержит запрещённые фразы")
        return False
    return True

# 📬 Автопостинг в Telegram-группу
async def auto_posting():
    global topic_index, rss_index, use_topic
    while True:
        topic = None
        try:
            logging.info(f"▶️ Цикл автопостинга. use_topic={use_topic}, topic_index={topic_index}, rss_index={rss_index}")
            if use_topic:
                topic = TOPICS[topic_index % len(TOPICS)]
                topic_index += 1
                logging.info(f"🧠 Выбрана тема из списка: {topic}")
            else:
                rss_titles = await get_rss_titles()
                if rss_titles:
                    topic = rss_titles[rss_index % len(rss_titles)]
                    logging.info(f"📚 Заголовки RSS для постинга: {rss_titles}")
                    rss_index += 1
                    logging.info(f"📰 Выбрана тема из RSS: {topic}")
                else:
                    logging.warning("❌ Не удалось получить темы из RSS")
            use_topic = not use_topic

            if topic:
                post = await generate_reply([{"role": "user", "content": topic}])
                logging.info(f"📄 Сгенерирован пост: {post[:100]}...")
                if quality_filter(post):
                    await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                    logging.info("✅ Пост успешно отправлен в группу")
                else:
                    logging.warning("🚫 Пост не прошёл фильтр качества")
            else:
                logging.warning("⚠️ Не выбрана тема для генерации поста")

        except Exception as e:
            logging.error(f"❌ Ошибка автопостинга: {e}")

        delay = 1800
        logging.info(f"⏳ Ожидание {delay} сек до следующего поста...")
        await asyncio.sleep(delay)

# 🔁 Self-ping для Render
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(SELF_URL)
                logging.info(f"📡 Self-ping: {r.status_code}")
        except Exception as e:
            logging.error(f"❌ Self-ping error: {e}")
        await asyncio.sleep(600)

# /start обработчик
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        logging.info(f"👋 /start от {msg.from_user.id}")
        await msg.reply("Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. Чем могу помочь?")

# 💬 Ответ на входящие сообщения
@dp.message_handler()
async def reply_handler(msg: types.Message):
    user_id = msg.from_user.id
    update_user_session(user_id)

    user_text = msg.text.strip()
    bot_me = await bot.get_me()
    logging.info(f"📨 Сообщение от {user_id}: {user_text[:100]}")

    cleaned = user_text.replace(f"@{bot_me.username}", "").strip()

    if msg.chat.type in ["group", "supergroup"]:
        if f"@{bot_me.username}" in msg.text:
            user_sessions[user_id].append({"role": "user", "content": cleaned})
            messages = list(user_sessions[user_id])
            response = await generate_reply(messages)
            user_sessions[user_id].append({"role": "assistant", "content": response})
            await msg.reply(clean_html_for_telegram(response), parse_mode=ParseMode.HTML)
        return

    user_sessions[user_id].append({"role": "user", "content": cleaned})
    messages = list(user_sessions[user_id])
    response = await generate_reply(messages)
    user_sessions[user_id].append({"role": "assistant", "content": response})
    await msg.reply(clean_html_for_telegram(response), parse_mode=ParseMode.HTML)

# 🚀 Главная точка запуска
async def main():
    logging.info("🚀 Инициализация бота...")
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    asyncio.create_task(clean_inactive_sessions())
    await dp.start_polling()

# 🔧 Запуск Flask и бота
if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
