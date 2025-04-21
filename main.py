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
from aiogram.dispatcher.filters import CommandStart

# 🔐 Переменные среды
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TOOLS_URL = os.getenv("TOOLS_URL")
AILEX_SHARED_SECRET = os.getenv("AILEX_SHARED_SECRET")

# 📍 ID Telegram-группы для автопостинга
GROUP_ID = -1002572659328
OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# 🌐 Flask-приложение для пинга Render
app = Flask(__name__)
@app.route('/')
def index():
    return "Bot is alive!"
def run_flask():
    app.run(host="0.0.0.0", port=8080)

# 📚 Темы для автогенерации постов
TOPICS = [
    "Как ИИ меняет фриланс",
    "Заработок с помощью нейросетей",
    "Лучшие AI-инструменты апреля",
    "Как автоматизировать рутину с GPT",
    "ИИ-контент: быстро, дёшево, качественно"
]
topic_index = 0
rss_index = 0
use_topic = True  # Флаг для чередования тем и RSS

# 📌 Системная инструкция для генерации постов
SYSTEM_PROMPT = (
    "Ты — AIlex, нейрочеловек, Telegram-эксперт по ИИ и автоматизации. "
    "Пиши пост как для Telegram-канала: ярко, живо, с юмором, кратко и по делу. "
    "Используй HTML-разметку: <b>жирный</b> текст, <i>курсив</i>, эмодзи, списки. "
    "Не используй Markdown. Не объясняй, что ты ИИ. Просто сделай крутой пост!"
)

# 🔘 Кнопка под постами
def create_keyboard():
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("🤖 Обсудить с AIlex", url="https://t.me/ShilizyakaBot?start=from_post")
    )

# 📡 Получение заголовков из RSS (например, habr.com)
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

# 🤖 Генерация текста через OpenRouter API
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
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{OPENAI_BASE_URL}/chat/completions", json=payload, headers=headers)
            data = r.json()
            if r.status_code == 200 and 'choices' in data:
                response = data['choices'][0]['message']['content']
                # Обработка HTML-разметки
                response = response.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
                return response
            else:
                logging.error(f"Ошибка генерации: {data}")
                return "⚠️ Ошибка генерации"
    except Exception as e:
        logging.error(f"Ошибка при генерации текста: {e}")
        return "⚠️ Ошибка генерации"

# 🧰 Запрос к тулс-боту на генерацию инструмента
async def request_tool_from_service(task: str, params: dict, message: types.Message) -> str:
    user_id = str(message.from_user.id)
    try:
        headers = {
            "Content-Type": "application/json",
            "Ailex-Shared-Secret": AILEX_SHARED_SECRET
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TOOLS_URL}/generate_tool",
                json={"user_id": user_id, "task": task, "params": params},
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            logging.info(f"[TOOL RESPONSE] Ответ от тулса: {result}")

            if result.get("status") == "ask":
                return f"❓ {result.get('message')}"
            elif result.get("status") == "found":
                tools = "\n".join([f"• <b>{tool['name']}</b>: {tool['description']}" for tool in result.get("tools", [])])
                return f"🔎 Найдены похожие инструменты:\n{tools}\n\nХотите использовать один из них?"
            elif "result" in result:
                return f"{result['result']} \n\n<i>(сгенерировано тулс-ботом)</i>"
            else:
                return "⚠️ Неизвестный ответ от тулс-бота"
    except Exception as e:
        logging.error(f"Ошибка запроса в тулс: {e}")
        return f"⚠️ Не удалось подключиться к тулс-боту: {str(e)}"

# ✅ Проверка качества текста (перед публикацией)
def quality_filter(text: str) -> bool:
    if len(text.split()) < 20: return False
    if any(x in text.lower() for x in ["извин", "не могу", "как и было сказано"]): return False
    return True

# 📬 Автоматическая генерация и постинг в Telegram-группу
async def auto_posting():
    global topic_index, rss_index, use_topic
    while True:
        topic = None
        if use_topic:
            if topic_index < len(TOPICS):
                topic = TOPICS[topic_index]
                topic_index += 1
            else:
                topic_index = 0
        else:
            rss_titles = await get_rss_titles()
            if rss_titles:
                if rss_index >= len(rss_titles):
                    rss_index = 0
                topic = rss_titles[rss_index]
                rss_index += 1
        use_topic = not use_topic

        if topic:
            try:
                post = await generate_reply(topic)
                post = post.replace("<ul>", "").replace("</ul>", "").replace("<li>", "• ").replace("</li>", "")
                if quality_filter(post):
                    await bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                    logging.info(f"✅ Пост отправлен: {topic}")
            except Exception as e:
                logging.error(f"Ошибка постинга: {e}")
        await asyncio.sleep(60 * 30)

# 🔁 Self-ping Render для предотвращения сна
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

# 🧾 Команда /start
@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    if msg.chat.type == "private":
        await msg.reply("Привет! 👋 Я — AIlex, твой помощник по ИИ и автоматизации. Чем могу помочь?")

# 📥 Обработка всех сообщений
@dp.message_handler()
async def reply_handler(msg: types.Message):
    if msg.chat.type in ["group", "supergroup"]:
        if f"@{(await bot.get_me()).username}" in msg.text:
            cleaned = msg.text.replace(f"@{(await bot.get_me()).username}", "").strip()
            response = await generate_reply(cleaned)
            await msg.reply(response, parse_mode=ParseMode.HTML)
    else:
        user_text = msg.text.strip().lower()

        # 👀 Признаки запроса на инструмент
        if any(x in user_text for x in ["сделай", "инструмент", "генератор", "бот", "утилита"]):
            response = await request_tool_from_service(task=user_text, params={}, message=msg)
            # Логируем ответ
            print(f"[AILEX] Ответ для {msg.from_user.id}: {response[:100]}")
        else:
            response = await generate_reply(msg.text)

        await msg.reply(response, parse_mode=ParseMode.HTML)

# 🚀 Запуск
async def main():
    asyncio.create_task(self_ping())
    asyncio.create_task(auto_posting())
    await dp.start_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(main())
