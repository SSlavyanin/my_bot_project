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

# 🧠 Память сессий
# Используется defaultdict с deque для хранения последних 10 сообщений каждого пользователя
user_sessions = defaultdict(lambda: deque(maxlen=10))  # Для истории сообщений
last_interaction = {}  # Для времени последнего взаимодействия

# 🪵 Настройка логов
# Максимальное логирование для отладки
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен бота из переменных окружения
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # API-ключ для OpenRouter
logging.info(f"🔐 TOKEN загружен: {'Да' if BOT_TOKEN else 'Нет'}, API_KEY: {'Да' if OPENROUTER_API_KEY else 'Нет'}")

# 📍 ID Telegram-группы
GROUP_ID = -1002572659328  # ID группы для автопостинга
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"  # URL для API OpenRouter

# 🤖 Создание экземпляров бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# 🌐 Flask-приложение для проверки статуса
app = Flask(__name__)

@app.route('/')
def index():
    logging.debug("📡 Запрос к Flask: Проверка статуса")
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

# 🔄 Функция для обновления времени последнего взаимодействия с пользователем
def update_user_session(user_id):
    last_interaction[user_id] = time.time()  # Обновляем время последнего взаимодействия
    logging.debug(f"✅ Время взаимодействия с пользователем {user_id} обновлено: {last_interaction[user_id]}")

# 🧹 Функция для очистки неактивных сессий
async def clean_inactive_sessions():
    while True:
        current_time = time.time()
        for user_id, last_time in list(last_interaction.items()):
            if current_time - last_time > 1800:  # 30 минут
                del last_interaction[user_id]
                del user_sessions[user_id]
                logging.info(f"🗑️ Сессия пользователя {user_id} удалена из-за 30 минут неактивности.")
        await asyncio.sleep(60)  # Проверка каждые 60 секунд

# 🔘 Создание клавиатуры для сообщений
def create_keyboard():
    logging.debug("📋 Создание клавиатуры для сообщений")
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("🤖 Обсудить с AIlex", url="https://t.me/ShilizyakaBot?start=from_post")
    )

# 📡 Получение RSS-заголовков
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
        logging.error(f"❌ Ошибка при получении RSS: {e}")
        return []

# 🧼 Очистка HTML для Telegram
def clean_html_for_telegram(html: str) -> str:
    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "span"}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    cleaned = str(soup)
    logging.debug(f"🧼 HTML очищен для Telegram: {cleaned[:80]}...")
    return cleaned

# 🧠 Генерация ответа от OpenRouter
async def generate_reply(user_message: list) -> str:
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
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + user_message
    }
    logging.debug(f"📦 Payload для OpenRouter: {payload}")

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
            data = r.json()
            if r.status_code == 200 and 'choices' in data:
                response = data['choices'][0]['message']['content']
                response = response.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
                logging.debug(f"🧠 Ответ от OpenRouter: {response[:80]}...")
                return response
            else:
                logging.error(f"❌ Ошибка генерации текста: {data}")
                return "⚠️ Ошибка генерации"
    except Exception as e:
        logging.error(f"❌ Ошибка при генерации текста: {e}")
        return "⚠️ Ошибка генерации"

# 📥 Обработчик команды /start
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        logging.info(f"👋 Команда /start от пользователя {msg.from_user.id}")
        await msg.reply("Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. Чем могу помочь?")

# 📥 Обработчик сообщений
@dp.message_handler()
async def reply_handler(msg: types.Message):
    user_id = msg.from_user.id
    update_user_session(user_id)
    user_text = msg.text.strip()
    logging.info(f"📨 Новое сообщение от пользователя {user_id}: {user_text}")

    user_sessions[user_id].append({"role": "user", "content": user_text})
    messages = list(user_sessions[user_id])
    logging.debug(f"💬 История сообщений для пользователя {user_id}: {messages}")

    response = await generate_reply(messages)
    user_sessions[user_id].append({"role": "assistant", "content": response})
    logging.info(f"📤 Ответ пользователю {user_id}: {response[:80]}")

    await msg.reply(clean_html_for_telegram(response), parse_mode=ParseMode.HTML)

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
                post = await generate_reply([{"role": "user", "content": topic}])
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
            logging.error(f"❌ Self-ping error: {e}")
        await asyncio.sleep(600)

# 🚀 Основная функция запуска
async def main():
    logging.info("🚀 Бот запускается...")
    asyncio.create_task(clean_inactive_sessions())
    asyncio.create_task(auto_posting())
    asyncio.create_task(self_ping())
    await dp.start_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
