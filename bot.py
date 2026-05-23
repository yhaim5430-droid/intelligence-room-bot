import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ═══════════════════════════════════════════
# הגדרות
# ═══════════════════════════════════════════
TG_TOKEN   = os.environ.get("TG_TOKEN",   "7754804245:AAEf5lCTTU3NB7qNnOa1-HKJXcpZLDOdseM")
ALPHA_KEY  = os.environ.get("ALPHA_KEY",  "40T4V3WC8TLYOELC")
CHAT_ID    = os.environ.get("CHAT_ID",    "6775881845")

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

# ═══════════════════════════════════════════
# שליפת נתונים
# ═══════════════════════════════════════════
async def fetch_stock(session, symbol):
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_KEY}"
    async with session.get(url) as r:
        d = await r.json()
        q = d.get("Global Quote", {})
        if not q.get("05. price"): return None
        return {
            "price":     float(q["05. price"]),
            "changePct": float(q["10. change percent"].replace("%", "")),
            "volume":    int(q["06. volume"]),
        }

async def fetch_crypto(session, symbol):
    url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={symbol}&to_currency=USD&apikey={ALPHA_KEY}"
    async with session.get(url) as r:
        d = await r.json()
        x = d.get("Realtime Currency Exchange Rate", {})
        if not x: return None
        return {"price": float(x["5. Exchange Rate"]), "changePct": 0.0}

# ═══════════════════════════════════════════
# סיגנל
# ═══════════════════════════════════════════
def get_signal(chg):
    if chg > 5:   return ("🚀 BREAKOUT",  "HIGH", True)
    if chg > 3:   return ("📈 MOMENTUM",  "HIGH", True)
    if chg > 1:   return ("✅ חיובי",     "MED",  True)
    if chg < -5:  return ("🔴 CRASH",     "HIGH", False)
    if chg < -3:  return ("⚠️ SELL",      "HIGH", False)
    if chg < -1:  return ("🟡 CAUTION",   "MED",  False)
    return              ("⬜ NEUTRAL",   "LOW",  None)

def fmt_price(asset, q):
    if asset["t"] == "crypto":
        return f"${q['price']:,.2f}"
    return f"${q['price']:.2f}"

def fmt_chg(q):
    c = q["changePct"]
    if c == 0: return "live"
    return f"{'+' if c > 0 else ''}{c:.2f}%"

# ═══════════════════════════════════════════
# סריקה מלאה
# ═══════════════════════════════════════════
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
                await asyncio.sleep(13)
            except Exception as e:
                print(f"Error {asset['s']}: {e}")
    return results

# ═══════════════════════════════════════════
# הודעות טלגרם
# ═══════════════════════════════════════════
def build_alert(asset, q, sig):
    time_str = datetime.now().strftime("%H:%M")
    return (
        f"{sig.split()[0]} <b>INTELLIGENCE ROOM</b>\n\n"
        f"🏷 <b>{asset['s']}</b> — {asset['n']}\n"
        f"💰 מחיר: <b>{fmt_price(asset, q)}</b>\n"
        f"📊 שינוי: <b>{fmt_chg(q)}</b>\n"
        f"📡 סיגנל: <b>{sig}</b>\n"
        f"🕐 {time_str}\n\n"
        f"<i>⬡ Intelligence Room · AI Trading System</i>"
    )

def build_watchlist(results):
    if not results:
        return "❌ אין נתונים — נסה שוב מאוחר יותר"
    
    lines = ["📊 <b>WATCHLIST — Intelligence Room</b>\n"]
    for r in results:
        a, q = r["asset"], r["quote"]
        chg = fmt_chg(q)
        sig = r["signal"]
        arrow = "🟢" if r["up"] else ("🔴" if r["up"] is False else "⚪")
        lines.append(f"{arrow} <b>{a['s']}</b> {fmt_price(a,q)} {chg} · {sig}")
    
    lines.append(f"\n<i>עודכן: {datetime.now().strftime('%H:%M:%S')}</i>")
    return "\n".join(lines)

def build_briefing(results):
    date_str = datetime.now().strftime("%A, %d/%m/%Y")
    ups   = [r for r in results if r["quote"]["changePct"] > 1]
    downs = [r for r in results if r["quote"]["changePct"] < -1]
    high  = [r for r in results if r["level"] == "HIGH"]
    
    msg = f"🌅 <b>תדריך בוקר — Intelligence Room</b>\n{date_str}\n\n"
    
    if ups:
        msg += "🚀 <b>מובילי עליות:</b>\n"
        for r in ups:
            msg += f"• {r['asset']['s']}: {fmt_price(r['asset'],r['quote'])} ({fmt_chg(r['quote'])})\n"
        msg += "\n"
    
    if downs:
        msg += "⚠️ <b>מובילי ירידות:</b>\n"
        for r in downs:
            msg += f"• {r['asset']['s']}: {fmt_price(r['asset'],r['quote'])} ({fmt_chg(r['quote'])})\n"
        msg += "\n"
    
    msg += f"📊 <b>סיכום:</b> {len(results)} נכסים · {len(ups)} עולים · {len(downs)} יורדים · {len(high)} התראות\n"
    msg += f"\n<i>⬡ Intelligence Room · AI Trading System</i>"
    return msg

# ═══════════════════════════════════════════
# פקודות טלגרם
# ═══════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Watchlist", callback_data="watchlist"),
         InlineKeyboardButton("🌅 תדריך בוקר", callback_data="briefing")],
        [InlineKeyboardButton("🔍 סריקה מלאה", callback_data="scan"),
         InlineKeyboardButton("ℹ️ עזרה", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⬡ <b>Intelligence Room</b>\n\nברוך הבא למערכת הבינה המלאכותית למסחר!\n\nבחר פעולה:",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 <b>מתחיל סריקת שוק...</b>\n\nזה לוקח כ-2 דקות, המתן...", parse_mode="HTML")
    results = await scan_all()
    
    # שלח התראות על נכסים חמים
    alerts_sent = 0
    for r in results:
        if r["level"] == "HIGH":
            alert_msg = build_alert(r["asset"], r["quote"], r["signal"])
            await ctx.bot.send_message(chat_id=update.effective_chat.id, text=alert_msg, parse_mode="HTML")
            alerts_sent += 1
            await asyncio.sleep(1)
    
    # שלח watchlist מלא
    wl = build_watchlist(results)
    await ctx.bot.send_message(chat_id=update.effective_chat.id, text=wl, parse_mode="HTML")
    await msg.delete()

async def cmd_briefing(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📋 <b>מכין תדריך בוקר...</b>\n\nממתין לנתונים...", parse_mode="HTML")
    results = await scan_all()
    briefing = build_briefing(results)
    await ctx.bot.send_message(chat_id=update.effective_chat.id, text=briefing, parse_mode="HTML")
    await msg.delete()

async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📊 <b>טוען נתונים...</b>", parse_mode="HTML")
    results = await scan_all()
    wl = build_watchlist(results)
    await msg.edit_text(wl, parse_mode="HTML")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "⬡ <b>Intelligence Room — פקודות</b>\n\n"
        "/start — תפריט ראשי\n"
        "/scan — סריקה מלאה + התראות\n"
        "/watchlist — מחירים חיים\n"
        "/briefing — תדריך בוקר\n"
        "/help — עזרה\n\n"
        "<i>הבוט סורק אוטומטית כל 5 דקות ושולח התראות</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# כפתורים
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "watchlist":
        await query.edit_message_text("📊 <b>טוען נתונים...</b>", parse_mode="HTML")
        results = await scan_all()
        wl = build_watchlist(results)
        await query.edit_message_text(wl, parse_mode="HTML")
    
    elif query.data == "briefing":
        await query.edit_message_text("🌅 <b>מכין תדריך...</b>", parse_mode="HTML")
        results = await scan_all()
        briefing = build_briefing(results)
        await query.edit_message_text(briefing, parse_mode="HTML")
    
    elif query.data == "scan":
        await query.edit_message_text("🔍 <b>סורק שוק...</b>\n\nזה לוקח כ-2 דקות...", parse_mode="HTML")
        results = await scan_all()
        for r in results:
            if r["level"] == "HIGH":
                alert_msg = build_alert(r["asset"], r["quote"], r["signal"])
                await ctx.bot.send_message(chat_id=query.message.chat_id, text=alert_msg, parse_mode="HTML")
                await asyncio.sleep(1)
        wl = build_watchlist(results)
        await ctx.bot.send_message(chat_id=query.message.chat_id, text=wl, parse_mode="HTML")
    
    elif query.data == "help":
        text = (
            "⬡ <b>פקודות זמינות:</b>\n\n"
            "/start — תפריט ראשי\n"
            "/scan — סריקה + התראות\n"
            "/watchlist — מחירים חיים\n"
            "/briefing — תדריך בוקר\n"
        )
        await query.edit_message_text(text, parse_mode="HTML")

# ═══════════════════════════════════════════
# סריקה אוטומטית ברקע
# ═══════════════════════════════════════════
async def auto_scan(app):
    await asyncio.sleep(30)  # המתן 30 שניות אחרי ההפעלה
    while True:
        try:
            print("🔍 סריקה אוטומטית...")
            results = await scan_all()
            for r in results:
                if r["level"] == "HIGH":
                    alert_msg = build_alert(r["asset"], r["quote"], r["signal"])
                    await app.bot.send_message(chat_id=CHAT_ID, text=alert_msg, parse_mode="HTML")
                    await asyncio.sleep(2)
            print(f"✅ סריקה הושלמה — {len(results)} נכסים")
        except Exception as e:
            print(f"❌ שגיאה בסריקה אוטומטית: {e}")
        await asyncio.sleep(5 * 60)  # כל 5 דקות

# ═══════════════════════════════════════════
# הפעלה
# ═══════════════════════════════════════════
async def main():
    app = Application.builder().token(TG_TOKEN).build()
    
    # פקודות
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("scan",      cmd_scan))
    app.add_handler(CommandHandler("briefing",  cmd_briefing))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # שלח הודעת הפעלה
    await app.bot.send_message(
        chat_id=CHAT_ID,
        text="⬡ <b>Intelligence Room הופעל!</b>\n\nהמערכת פועלת 24/7 ותשלח התראות אוטומטיות.\n\nשלח /start להתחלה.",
        parse_mode="HTML"
    )
    
    # הפעל סריקה אוטומטית ברקע
    asyncio.create_task(auto_scan(app))
    
    print("🤖 הבוט פועל...")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
