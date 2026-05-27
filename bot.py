"""
Intelligence Room Bot — Production Ready + Dashboard
Railway + python-telegram-bot v20+ + Flask
"""

import os
import asyncio
import aiohttp
import json
import secrets
import logging
from datetime import datetime, timedelta
from threading import Thread

from flask import Flask, render_template

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ═══════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════
# ENV
# ═══════════════════════════════════════
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or 0)

# ═══════════════════════════════════════
# FLASK DASHBOARD
# ═══════════════════════════════════════
web_app = Flask(__name__)

DB_FILE = "users.json"
BLOCKED_FILE = "blocked.json"

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def load_db():
    return _load(DB_FILE, {"users": {}, "pending": {}})

def load_blocked():
    return _load(BLOCKED_FILE, {"blocked": []})

@web_app.route("/")
def dashboard():
    db = load_db()
    blocked = load_blocked()
    users = list(db.get("users", {}).values())

    return render_template(
        "dashboard.html",
        total_users=len(users),
        active_users=len([u for u in users if u.get("expiry")]),
        pending_users=len(db.get("pending", {})),
        blocked_users=len(blocked.get("blocked", [])),
        users=users[-20:]
    )

def run_web():
    web_app.run(host="0.0.0.0", port=8080)

# ═══════════════════════════════════════
# START BOT
# ═══════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⬡ Intelligence Room Bot פעיל")

def main():
    if not TG_TOKEN:
        print("Missing TG_TOKEN")
        return

    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # הפעלת Flask במקביל
    Thread(target=run_web).start()

    log.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
