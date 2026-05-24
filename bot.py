import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════
TG_TOKEN = os.getenv("TG_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB_FILE = "users.json"
BLOCK_FILE = "blocked.json"
LOG_FILE = "security.log"

last_quotes = {}
last_alerts = {}
rate_limits = {}

ASSETS = [
    {"s": "NVDA", "n": "NVIDIA"},
    {"s": "AAPL", "n": "Apple"},
    {"s": "TSLA", "n": "Tesla"},
    {"s": "META", "n": "Meta"},
    {"s": "BTC-USD", "n": "Bitcoin"},
    {"s": "ETH-USD", "n": "Ethereum"},
]

PRICES = {
    "trial": {"name": "ניסיון", "days": 3},
    "monthly": {"name": "חודשי", "days": 30},
    "yearly": {"name": "שנתי", "days": 365},
}

# ═══════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════
def security_log(action, user_id, details=""):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{t}] {action} | UID:{user_id} | {details}\n")
    except:
        pass


def load_json(file_name, default_data):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data


def save_json(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_db():
    return load_json(DB_FILE, {
        "users": {},
        "pending": {},
        "referrals": {}
    })


def save_db(db):
    save_json(DB_FILE, db)


def load_blocked():
    return load_json(BLOCK_FILE, {
        "blocked": []
    })


def is_blocked(user_id):
    data = load_blocked()
    return str(user_id) in data["blocked"]


def block_user(user_id):
    data = load_blocked()
    uid = str(user_id)

    if uid not in data["blocked"]:
        data["blocked"].append(uid)
        save_json(BLOCK_FILE, data)


# ═══════════════════════════════════════
# USERS
# ═══════════════════════════════════════
def get_user(user_id):
    db = load_db()
    return db["users"].get(str(user_id))


def is_admin(user_id):
    return int(user_id) == ADMIN_ID


def is_subscribed(user_id):
    if is_admin(user_id):
        return True

    user = get_user(user_id)

    if not user:
        return False

    expiry = user.get("expiry")

    if not expiry:
        return False

    try:
        return datetime.fromisoformat(expiry) > datetime.now()
    except:
        return False


def add_subscription(user_id, username, plan_key, days):
    db = load_db()

    now = datetime.now()
    expiry = now + timedelta(days=days)

    db["users"][str(user_id)] = {
        "user_id": user_id,
        "username": username,
        "plan": plan_key,
        "expiry": expiry.isoformat(),
        "joined": now.isoformat(),
    }

    save_db(db)


# ═══════════════════════════════════════
# RATE LIMIT
# ═══════════════════════════════════════
def check_rate_limit(user_id):
    now = datetime.now()

    if user_id not in rate_limits:
        rate_limits[user_id] = []

    rate_limits[user_id] = [
        t for t in rate_limits[user_id]
        if (now - t).seconds < 60
    ]

    rate_limits[user_id].append(now)

    if len(rate_limits[user_id]) > 10:
        return False

    return True


# ═══════════════════════════════════════
# FINANCE
# ═══════════════════════════════════════
async def fetch_quote(session, symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

    try:
        async with session.get(
            url,
            params={"interval": "1d", "range": "5d"},
            timeout=aiohttp.ClientTimeout(
                total=15,
                connect=5,
                sock_read=10,
            ),
        ) as response:

            data = await response.json()

            result = data["chart"]["result"][0]
            meta = result["meta"]

            price = float(meta.get("regularMarketPrice", 0))
            prev = float(meta.get("chartPreviousClose", price))

            change = round(((price - prev) / prev) * 100, 2) if prev else 0

            return {
                "price": price,
                "change": change,
            }

    except Exception as e:
        security_log("YAHOO_ERROR", symbol, str(e))
        return None


async def scan_market():
    results = []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_quote(session, asset["s"]) for asset in ASSETS]

        quotes = await asyncio.gather(*tasks)

        for asset, quote in zip(ASSETS, quotes):
            if not quote:
                continue

            signal = generate_signal(quote)

            results.append({
                "asset": asset,
                "quote": quote,
                "signal": signal,
            })

    return results


# ═══════════════════════════════════════
# SIGNALS
# ═══════════════════════════════════════
def generate_signal(q):
    chg = q["change"]
    price = q["price"]

    if chg > 4:
        return {
            "action": "BUY",
            "emoji": "🚀",
            "confidence": 88,
            "entry": round(price * 0.99, 2),
            "target": round(price * 1.08, 2),
            "stop": round(price * 0.96, 2),
            "level": "HIGH",
        }

    if chg > 1:
        return {
            "action": "WATCH",
            "emoji": "📈",
            "confidence": 60,
            "entry": round(price * 0.98, 2),
            "target": round(price * 1.04, 2),
            "stop": round(price * 0.97, 2),
            "level": "MED",
        }

    if chg < -4:
        return {
            "action": "SELL",
            "emoji": "🔴",
            "confidence": 85,
            "entry": round(price, 2),
            "target": round(price * 0.92, 2),
            "stop": round(price * 1.04, 2),
            "level": "HIGH",
        }

    return {
        "action": "NEUTRAL",
        "emoji": "⬜",
        "confidence": 40,
        "entry": round(price, 2),
        "target": round(price * 1.01, 2),
        "stop": round(price * 0.99, 2),
        "level": "LOW",
    }


# ═══════════════════════════════════════
# UI
# ═══════════════════════════════════════
def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Watchlist", callback_data="watchlist"),
            InlineKeyboardButton("💹 Signals", callback_data="signals"),
        ],
        [
            InlineKeyboardButton("🌅 Briefing", callback_data="briefing"),
            InlineKeyboardButton("🔍 Scan", callback_data="scan"),
        ],
        [
            InlineKeyboardButton("👑 Subscribe", callback_data="subscribe"),
        ],
    ])


# ═══════════════════════════════════════
# BUILDERS
# ═══════════════════════════════════════
def build_watchlist(results):
    text = "📊 <b>WATCHLIST</b>\n\n"

    for r in results:
        a = r["asset"]
        q = r["quote"]
        s = r["signal"]

        text += (
            f"{s['emoji']} <b>{a['s']}</b>\n"
            f"💰 ${q['price']}\n"
            f"📊 {q['change']}%\n"
            f"📡 {s['action']} • {s['confidence']}%\n\n"
        )

    return text


def build_alert(asset, quote, signal):
    return (
        f"{signal['emoji']} <b>INTELLIGENCE ROOM ALERT</b>\n\n"
        f"🏷 <b>{asset['s']}</b>\n"
        f"💰 Price: ${quote['price']}\n"
        f"📊 Change: {quote['change']}%\n"
        f"📥 Entry: ${signal['entry']}\n"
        f"🎯 Target: ${signal['target']}\n"
        f"🛑 Stop: ${signal['stop']}\n"
        f"📡 {signal['action']} • {signal['confidence']}%"
    )


# ═══════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_blocked(user.id):
        await update.message.reply_text("🚫 נחסמת")
        return

    if not check_rate_limit(user.id):
        await update.message.reply_text("⚠️ יותר מדי בקשות")
        return

    db = load_db()

    if str(user.id) not in db["users"]:
        db["users"][str(user.id)] = {
            "user_id": user.id,
            "username": user.username,
            "joined": datetime.now().isoformat(),
            "expiry": None,
        }

        save_db(db)

    await update.message.reply_text(
        "⬡ <b>Intelligence Room</b>\n\nברוך הבא",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_admin(uid):
        security_log("ADMIN_ACCESS_DENIED", uid)
        return

    db = load_db()

    users = len(db["users"])

    active = 0

    for u in db["users"].values():
        try:
            if u.get("expiry") and datetime.fromisoformat(u["expiry"]) > datetime.now():
                active += 1
        except:
            pass

    text = (
        f"👑 <b>ADMIN PANEL</b>\n\n"
        f"👥 Users: {users}\n"
        f"✅ Active: {active}"
    )

    await update.message.reply_text(text, parse_mode="HTML")


# ═══════════════════════════════════════
# BUTTONS
# ═══════════════════════════════════════
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    await query.answer()

    uid = query.from_user.id

    if not is_subscribed(uid) and not is_admin(uid):
        await query.edit_message_text(
            "🔒 צריך מנוי פעיל"
        )
        return

    data = query.data

    if data == "watchlist":
        await query.edit_message_text("📊 טוען...", parse_mode="HTML")

        results = await scan_market()

        await query.edit_message_text(
            build_watchlist(results),
            parse_mode="HTML",
            reply_markup=main_menu(),
        )

    elif data == "scan":
        await query.edit_message_text("🔍 סורק...", parse_mode="HTML")

        results = await scan_market()

        sent = 0

        for r in results:
            if r["signal"]["level"] != "HIGH":
                continue

            key = f"{r['asset']['s']}_{r['signal']['action']}"

            now = datetime.now()

            if key in last_alerts:
                diff = (now - last_alerts[key]).seconds

                if diff < 1800:
                    continue

            last_alerts[key] = now

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=build_alert(r["asset"], r["quote"], r["signal"]),
                parse_mode="HTML",
            )

            sent += 1

        await query.edit_message_text(
            f"✅ Scan Complete\n📡 Alerts: {sent}",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )


# ═══════════════════════════════════════
# AUTO ALERTS
# ═══════════════════════════════════════
async def auto_scan(app):
    await asyncio.sleep(30)

    while True:
        try:
            results = await scan_market()

            db = load_db()

            active_users = []

            for user in db["users"].values():
                try:
                    if user.get("expiry"):
                        exp = datetime.fromisoformat(user["expiry"])

                        if exp > datetime.now():
                            active_users.append(user["user_id"])
                except:
                    pass

            if ADMIN_ID not in active_users:
                active_users.append(ADMIN_ID)

            for r in results:
                if r["signal"]["level"] != "HIGH":
                    continue

                key = f"{r['asset']['s']}_{r['signal']['action']}"

                now = datetime.now()

                if key in last_alerts:
                    if (now - last_alerts[key]).seconds < 1800:
                        continue

                last_alerts[key] = now

                text = build_alert(
                    r["asset"],
                    r["quote"],
                    r["signal"],
                )

                for uid in active_users:
                    try:
                        await app.bot.send_message(
                            chat_id=uid,
                            text=text,
                            parse_mode="HTML",
                        )

                        await asyncio.sleep(0.3)

                    except Exception as e:
                        security_log("AUTO_ALERT_ERROR", uid, str(e))

        except Exception as e:
            security_log("AUTO_SCAN_ERROR", 0, str(e))

        await asyncio.sleep(1800)


# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════
def main():
    if not TG_TOKEN:
        print("Missing TG_TOKEN")
        return

    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(buttons))

    async def post_init(application):
        try:
            await application.bot.send_message(
                chat_id=ADMIN_ID,
                text="✅ Intelligence Room Started",
            )
        except:
            pass

        asyncio.create_task(auto_scan(application))

    app.post_init = post_init

    print("BOT STARTED")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
