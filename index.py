import os
import json
import asyncio
import feedparser
import requests

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

DATA_FILE = "monitor.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)


# ================= STORAGE =================
def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ================= PROFILE CHECK (SCRAPE HTML) =================
def check_profile(username):
    url = f"https://nitter.net/{username}"
    r = requests.get(url, timeout=10)

    if r.status_code != 200:
        return None

    html = r.text

    if "User not found" in html:
        return None

    return True


# ================= RSS FETCH =================
def get_latest_entries(username):
    rss_url = f"https://nitter.net/{username}/rss"
    feed = feedparser.parse(rss_url)
    return feed.entries


# ================= TELEGRAM COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 X Monitor Bot (FREE MODE)\n\n"
        "/add username\n"
        "/remove username"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Masukkan username.")

    username = context.args[0].replace("@", "")

    if not check_profile(username):
        return await update.message.reply_text("❌ Username tidak ditemukan.")

    keyboard = [
        [InlineKeyboardButton("Tweet", callback_data=f"tweet|{username}")],
        [InlineKeyboardButton("Retweet", callback_data=f"retweet|{username}")],
        [InlineKeyboardButton("Reply", callback_data=f"reply|{username}")],
        [InlineKeyboardButton("Done", callback_data=f"done|{username}")],
    ]

    await update.message.reply_text(
        f"Profile ditemukan @{username}\n\nPilih notifikasi:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, username = query.data.split("|")
    chat_id = str(query.message.chat.id)

    data = load_data()

    if chat_id not in data:
        data[chat_id] = {}

    if username not in data[chat_id]:
        data[chat_id][username] = {
            "notif": [],
            "last": None
        }

    if action == "done":
        save_data(data)
        return await query.edit_message_text("✅ Monitoring aktif.")

    if action not in data[chat_id][username]["notif"]:
        data[chat_id][username]["notif"].append(action)

    save_data(data)
    await query.answer("Dipilih!")


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    username = context.args[0]
    chat_id = str(update.message.chat.id)

    data = load_data()

    if chat_id in data and username in data[chat_id]:
        del data[chat_id][username]
        save_data(data)
        await update.message.reply_text("❌ Monitoring removed.")


# ================= MONITOR LOOP =================
async def monitor(app):
    while True:
        data = load_data()

        for chat_id in data:
            for username in data[chat_id]:
                entries = get_latest_entries(username)

                if not entries:
                    continue

                latest = entries[0]
                link = latest.link

                if data[chat_id][username]["last"] != link:
                    data[chat_id][username]["last"] = link

                    await app.bot.send_message(
                        chat_id,
                        f"🔥 Aktivitas baru @{username}\n{link}"
                    )

        save_data(data)
        await asyncio.sleep(15)


# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CallbackQueryHandler(button))

    asyncio.create_task(monitor(app))

    print("Bot running (FREE MODE)...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
