import logging
import asyncio
import random
import httpx
import feedparser
from telegram import Bot, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CallbackContext, MessageHandler, Filters
from flask import Flask
from threading import Thread
import os

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROUP_ID = -1002572659328

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "AIlex is alive"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Self-ping Render
async def self_ping():
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get("https://my-bot-project-8wit.onrender.com/")
        except Exception as e:
            logging.error(f"Self-ping error: {e}")
        await asyncio.sleep(600)

def create_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Комментарии", url="https://t.me/c/2572659328")]
    ])

def quality_filter(post: str) -> bool:
    return len(post) > 100 and "ИИ" in post

topics = []

async def fetch_topics_from_rss():
    global topics
    topics = []
    urls = [
        "https://neurohype.tech/rss",
        "https://ain.ua/feed/",
        "https://thereisno.ai/feed"
    ]
    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.get("title", "")
            if any(word in title for word in ["ИИ", "AI", "нейросеть", "автоматизация", "инструмент"]):
                topics.append(title)

async def generate_reply(topic: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "meta-llama/llama-4-maverick:free",
        "messages": [
            {"role": "system", "content": "Ты нейрочел AIlex — говоришь чётко, по делу, с идеями. Пишешь посты про ИИ, автоматизацию, заработок. Напоминай, что ты можешь создать такой инструмент под задачу."},
            {"role": "user", "content": f"{topic}"}
        ]
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            data = response.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            else:
                logging.error(f"Ошибка OpenRouter: {data}")
                return ""
    except Exception as e:
        logging.error(f"Ошибка генерации: {e}")
        return ""

async def auto_posting():
    await fetch_topics_from_rss()
    while True:
        if topics:
            topic = random.choice(topics)
            post = await generate_reply(f"{topic}. Напиши пост от имени AIlex. Упомяни, что он может создать такой инструмент.")
            if quality_filter(post):
                bot.send_message(GROUP_ID, post, reply_markup=create_keyboard(), parse_mode=ParseMode.HTML)
                logging.info("✅ Пост отправлен")
            else:
                logging.info("❌ Пост не прошёл фильтр")
        else:
            logging.warning("⚠️ Нет тем для постинга.")
        await asyncio.sleep(60 * 60 * 2.5)

def handle_message(update: Update, context: CallbackContext):
    if update.message and update.message.reply_to_message and update.message.chat.id == GROUP_ID:
        user_comment = update.message.text
        prompt = f"Комментарий: {user_comment}\nОтветь от имени AIlex — чётко, по делу, как нейрочел."

        async def process_reply():
            reply = await generate_reply(prompt)
            if reply:
                context.bot.send_message(chat_id=update.message.chat_id, text=reply, reply_to_message_id=update.message.message_id)

        asyncio.create_task(process_reply())

def main():
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    Thread(target=run_flask).start()
    loop = asyncio.get_event_loop()
    loop.create_task(self_ping())
    loop.create_task(auto_posting())
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
