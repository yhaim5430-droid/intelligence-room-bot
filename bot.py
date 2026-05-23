import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ====================== הגדרות ======================
TG_TOKEN = os.environ.get("TG_TOKEN")
ALPHA_KEY = os.environ.get("ALPHA_KEY")
CHAT_ID = os.environ.get("CHAT_ID")

ASSETS = [
    {"s": "NVDA", "n": "NVIDIA",    "t": "stock"},
    {"s": "AAPL", "n": "Apple",     "t": "stock"},
    {"s": "TSLA", "n": "Tesla",     "t": "stock"},
    {"s": "META", "n": "Meta",      "t": "stock"},
    {"s": "AMD",  "n": "AMD",       "t": "stock"},
    {"s": "MSFT", "n": "Microsoft", "t": "stock"},
    {"s": "BTC",  "n": "Bitcoin",   "t": "crypto"},
    {"s": "ETH",  "n": "Ethereum",  "t": "crypto"},
    {"s": "SOL",  "n": "Solana",    "t": "crypto"},
]

# ====================== שליפת נתונים ======================
async def fetch_stock(session, symbol):
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_KEY}"
    async with session.get(url) as r:
        d = await r.json()
        q = d.get("Global Quote", {})
        if not q.get("05. price"): return None
        return {
            "price": float(q["05. price"]),
            "changePct": float(q["10. change percent"].replace("%", "")),
            "volume": int(q["06. volume"]),
        }

async def fetch_crypto(session, symbol):
    url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={symbol}&to_currency=USD&apikey={ALPHA_KEY}"
    async with session.get(url) as r:
        d = await r.json()
        x = d.get("Realtime Currency Exchange Rate", {})
        if not x: return None
        return {"price": float(x["5. Exchange Rate"]), "changePct": 0.0}

# ====================== לוגיקה ======================
def get_signal(chg):
    if chg > 5:   return ("🚀 BREAKOUT", "HIGH", True)
    if chg > 3:   return ("📈 MOMENTUM", "HIGH", True)
    if chg > 1:   return ("✅ חיובי", "MED", True)
    if chg < -5:  return ("🔴 CRASH", "HIGH", False)
    if chg < -3:  return ("⚠️ SELL", "HIGH", False)
    if chg < -1:  return ("🟡 CAUTION", "MED", False)
    return ("⬜ NEUTRAL", "LOW", None)

def fmt_price(asset, q):
    if asset["t"] == "crypto":
        return f"${q['price']:,.2f}"
    return f"${q['price']:.2f}"

def fmt_chg(q):
    c = q["changePct"]
    if c == 0: return "live"
    return f"{'+' if c > 0 else ''}{c:.2f}%"

# ====================== סריקה ======================
async def scan_all():
    results = []
    async with aiohttp.ClientSession() as session:
        for asset in ASSETS:
            try:
                if asset["t"] == "stock":
                    q = await fetch_stock(session, asset["s"])
                else:
                    q = await fetch_crypto(session, asset["s"])
                if q:
                    sig, level, up = get_signal(q["changePct"])
                    results.append({"asset": asset, "quote": q, "signal": sig, "level": level, "up": up})
                await asyncio.sleep(12)
            except Exception as e:
                print(f"Error {asset['s']}: {e}")
    return results

# ====================== הודעות ======================
def build_alert(asset, q, sig):
    time_str = datetime.now().strftime("%H:%M")
    return f"{sig.split()[0]} <b>INTELLIGENCE ROOM</b>\n\n🏷 <b>{asset['s']}</b> — {asset['n']}\n💰 מחיר: <b>{fmt_price(asset, q)}</b>\n📊 שינוי: <b>{fmt_chg(q)}</b>\n📡 סיגנל: <b>{sig}</b>\n🕐 {time_str}"

def build_watchlist(results):
    if not results:
        return "❌ אין נתונים — נסה שוב מאוחר יותר"
    lines = ["📊 <b>WATCHLIST — Intelligence Room</b>\n"]
    for r in results:
        a, q = r["asset"], r["quote"]
        arrow = "🟢" if r["up"] else ("🔴" if r["up"] is False else "⚪")
        lines.append(f"{arrow} <b>{a['s']}</b> {fmt_price(a,q)} {fmt_chg(q)} · {r['signal']}")
    lines.append(f"\n<i>עודכן: {datetime.now().strftime('%H:%M:%S')}</i>")
    return "\n".join(lines)

def build_briefing(results):
    date_str = datetime.now().strftime("%A, %d/%m/%Y")
    ups = [r for r in results if r["quote"]["changePct"] > 1]
    downs = [r for r in results if r["quote"]["changePct"] < -1]
    high = [r for r in results if r["level"] == "HIGH"]
    
    msg = f"🌅 <b>תדריך בוקר — Intelligence Room</b>\n{date_str}\n\n"
    if ups:
        msg += "🚀 <b>מובילי עליות:</b>\n" + "\n".join([f"• {r['asset']['s']}: {fmt_price(r['asset'],r['quote'])} ({fmt_chg(r['quote'])})" for r in ups]) + "\n\n"
    if downs:
        msg += "⚠️ <b>מובילי ירידות:</b>\n" + "\n".join([f"• {r['asset']['s']}: {fmt_price(r['asset'],r['quote'])} ({fmt_chg(r['quote'])})" for r in downs]) + "\n\n"
    msg += f"📊 <b>סיכום:</b> {len(results)} נכסים · {len(ups)} עולים · {len(downs)} יורדים"
    return msg

# ====================== פקודות ======================
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Watchlist", callback_data="watchlist"),
         InlineKeyboardButton("🌅 תדריך בוקר", callback_data="briefing")],
        [InlineKeyboardButton("🔍 סריקה מלאה", callback_data="scan"),
         InlineKeyboardButton("ℹ️ עזרה", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⬡ <b>Intelligence Room</b>\n\n"
        "ברוך הבא למערכת הבינה המלאכותית למסחר!\n\n"
        "בחר פעולה:",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 מתחיל סריקה...", parse_mode="HTML")
    results = await scan_all()
    wl = build_watchlist(results)
    await ctx.bot.send_message(chat_id=update.effective_chat.id, text=wl, parse_mode="HTML")
    await msg.delete()

async def cmd_briefing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📋 מכין תדריך...", parse_mode="HTML")
    results = await scan_all()
    briefing = build_briefing(results)
    await ctx.bot.send_message(chat_id=update.effective_chat.id, text=briefing, parse_mode="HTML")
    await msg.delete()

async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📊 טוען נתונים...", parse_mode="HTML")
    results = await scan_all()
    wl = build_watchlist(results)
    await msg.edit_text(wl, parse_mode="HTML")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = "⬡ <b>פקודות:</b>\n/start - תפריט ראשי\n/watchlist - מחירים חיים\n/briefing - תדריך\n/scan - סריקה מלאה"
    await update.message.reply_text(text, parse_mode="HTML")

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "watchlist":
        await cmd_watchlist(update, ctx)
    elif query.data == "briefing":
        await cmd_briefing(update, ctx)
    elif query.data == "scan":
        await cmd_scan(update, ctx)
    elif query.data == "help":
        await cmd_help(update, ctx)

# ====================== הפעלה ======================
async def main():
    app = Application.builder().token(TG_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 הבוט פועל...")
    
    try:
        await app.bot.send_message(
            chat_id=CHAT_ID,
            text="⬡ <b>Intelligence Room הופעל!</b>\n\nשלח /start לפתיחת התפריט.",
            parse_mode="HTML"
        )
    except:
        pass

    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())