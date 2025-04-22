import os
import traceback
import logging
import asyncio
import random
from flask import Flask
from threading import Thread
from bs4 import BeautifulSoup
import httpx
import xml.etree.ElementTree as ET
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TOOLS_URL = os.getenv("TOOLS_URL")
AILEX_SHARED_SECRET = os.getenv("AILEX_SHARED_SECRET")

# 📍 ID Telegram-группы для автопостинга
GROUP_ID = -1002572659328
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"

# 🧠 Базовая настройка aiogram и логгирования
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# 🌐 Flask-приложение для Render
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot is alive!"
def run_flask():
    app.run(host="0.0.0.0", port=8080)

# 📚 Темы для генерации контента
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

# 📌 Системный промпт
# SYSTEM_PROMPT = (
#     "Ты — AIlex, нейрочеловек, Telegram-эксперт по ИИ и автоматизации. "
#     "Пиши пост как для Telegram-канала: ярко, живо, с юмором, кратко и по делу. "
#     "Используй HTML-разметку: <b>жирный</b> текст, <i>курсив</i>, эмодзи, списки. "
#     "Не используй Markdown. Не объясняй, что ты ИИ. Просто сделай крутой пост!"
# )

# 🔘 Кнопка под постами
def create_keyboard():
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("🤖 Обсудить с AIlex", url="https://t.me/ShilizyakaBot?start=from_post")
    )

# 📡 Получение заголовков из RSS
async def get_rss_titles():
    RSS_FEED_URL = "https://habr.com/ru/rss/"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(RSS_FEED_URL, follow_redirects=True)
            if r.status_code != 200:
                return []
            root = ET.fromstring(r.text)
            return [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
    except Exception as e:
        logging.error(f"Ошибка при получении RSS: {e}")
        return []


# 🛠️ Делегирование задачи тулс-боту
user_tool_states = {}

from bs4 import BeautifulSoup

# 🔎 Фильтр Telegram-friendly HTML
def clean_html_for_telegram(html: str) -> str:
    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "span"}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    return str(soup)

# 🛠️ Делегирование задачи тулс-боту
from bs4 import BeautifulSoup

# 🔎 Фильтр Telegram-friendly HTML
def clean_html_for_telegram(html: str) -> str:
    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "span"}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    return str(soup)

# 🔎 Фильтр Telegram-friendly HTML
def clean_html_for_telegram(html: str) -> str:
    allowed_tags = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "span"}
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    return str(soup)

# 🛠️ Делегирование задачи тулс-боту
async def handle_tool_request(message: types.Message):
    user_id = str(message.from_user.id)
    headers = {
        "Content-Type": "application/json",
        "Ailex-Shared-Secret": AILEX_SHARED_SECRET
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TOOLS_URL}/generate_tool",
                json={"user_id": user_id, "message": message.text},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            status = data.get("status")
            raw_msg = data.get("message", "⚠️ Нет ответа от тулс-бота.")
            msg = clean_html_for_telegram(raw_msg)

            if status == "need_more_info":
                user_tool_states[user_id] = "in_progress"
            elif status in ["ready", "error"]:
                user_tool_states.pop(user_id, None)

            await message.answer(f"<b>📦 Ответ от тулс-бота:</b>\n{msg}", parse_mode="HTML")

    except Exception as e:
        logging.error("Ошибка при обращении к тулс-боту:")
        logging.error(traceback.format_exc())
        await message.answer("⚠️ Ошибка при обращении к тулс-боту.")


    except Exception as e:
        logging.error("Ошибка при обращении к тулс-боту:")
        logging.error(traceback.format_exc())
        await message.answer("⚠️ Ошибка при обращении к тулс-боту.")


# 🤖 Генерация ответа через OpenRouter
async def generate_reply(user_message: str, message: types.Message) -> str:
    user_id = str(message.from_user.id)

    # Если тулс-бот уже в процессе общения — просто перекидываем сообщение
    if user_tool_states.get(user_id) == "in_progress":
        await handle_tool_request(message)
        return "🔄 Сообщение передано тулс-боту."

    chat_type = message.chat.type

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/YOUR_CHANNEL_NAME",
        "X-Title": "AIlexBot"
    }

    if chat_type == "private":
        SYSTEM_PROMPT = "Ты — AIlex, нейроэксперт по ИИ и автоматизации. Отвечай как человек: дружелюбно, ясно, по делу. Помогай, уточняй детали, предлагай решения."
    else:
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
                if "передаю вас тулс-боту" in response.lower():
                    await handle_tool_request(message)
                    return "🔄 Запрос передан тулс-боту."
                return response
            else:
                logging.error(f"Ошибка генерации: {data}")
                return "⚠️ Ошибка генерации"
    except Exception as e:
        logging.error(f"Ошибка при генерации текста: {e}")
        return "⚠️ Ошибка генерации"


# ✅ Проверка качества текста
def quality_filter(text: str) -> bool:
    if len(text.split()) < 20: return False
    if any(x in text.lower() for x in ["извин", "не могу", "как и было сказано"]): return False
    return True

# 📬 Постинг в группу каждые 30 минут
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
                post = await generate_reply(topic, message=types.Message(from_user=types.User(id=0, is_bot=False)))
                if quality_filter(post):
                    await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                    logging.info(f"✅ Пост отправлен: {topic}")
            except Exception as e:
                logging.error(f"Ошибка постинга: {e}")
        await asyncio.sleep(60 * 30)

# 🔁 Self-ping для Render
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# 🧾 /start
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        await msg.reply("Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. Чем могу помочь?")

# 📥 Обработка всех входящих сообщений
@dp.message_handler()
async def reply_handler(msg: types.Message):
    user_id = str(msg.from_user.id)
    user_text = msg.text.strip()
    user_text_lower = user_text.lower()

    if msg.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in msg.text:
            cleaned = msg.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            response = await generate_reply(cleaned, message=msg)
            await msg.reply(response, parse_mode=ParseMode.HTML)
        return

    # 🔁 Если юзер уже в диалоге с тулс-ботом — просто пересылаем
    if user_tool_states.get(user_id) == "in_progress":
        await handle_tool_request(msg)
        return

    # 🧠 Если триггер на запуск инструмента — стартуем сессии
    if any(x in user_text_lower for x in ["сделай", "инструмент", "генератор", "бот", "утилита"]):
        await handle_tool_request(msg)
        return

    # 🤖 Иначе обычный ответ AIlex
    response = await generate_reply(msg.text, message=msg)
    await msg.reply(response, parse_mode=ParseMode.HTML)


# 🚀 Главная точка входа
async def main():
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    await dp.start_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
