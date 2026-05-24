import os
import asyncio
import aiohttp
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ═══════════════════════════════════════════
# הגדרות
# ═══════════════════════════════════════════
TG_TOKEN  = os.environ.get("TG_TOKEN",  "7754804245:AAEf5lCTTU3NB7qNnOa1-HKJXcpZLDOdseM")
ALPHA_KEY = os.environ.get("ALPHA_KEY", "40T4V3WC8TLYOELC")
CHAT_ID   = os.environ.get("CHAT_ID",   "6775881845")

# רק 5 נכסים כדי לא לחרוג ממגבלת API
ASSETS = [
    {"s": "NVDA", "n": "NVIDIA",   "t": "stock"},
    {"s": "AAPL", "n": "Apple",    "t": "stock"},
    {"s": "TSLA", "n": "Tesla",    "t": "stock"},
    {"s": "BTC",  "n": "Bitcoin",  "t": "crypto"},
    {"s": "ETH",  "n": "Ethereum", "t": "crypto"},
]

last_quotes = {}  # שמירת נתונים אחרונים

# ═══════════════════════════════════════════
# שליפת נתונים — עם retry אוטומטי
# ═══════════════════════════════════════════
async def fetch_stock(session, symbol):
    for attempt in range(3):
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_KEY}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                text = await r.text()
                print(f"[{symbol}] Response: {text[:200]}")
                d = json.loads(text)
                
                # בדיקה אם API limit
                if "Note" in d or "Information" in d:
                    print(f"[{symbol}] API limit hit!")
                    await asyncio.sleep(60)
                    continue
                
                q = d.get("Global Quote", {})
                if not q.get("05. price"):
                    print(f"[{symbol}] No price in response")
                    return None
                    
                return {
                    "price":     float(q["05. price"]),
                    "changePct": float(q["10. change percent"].replace("%", "").strip()),
                    "volume":    int(q.get("06. volume", 0)),
                }
        except Exception as e:
            print(f"[{symbol}] Attempt {attempt+1} failed: {e}")
            await asyncio.sleep(5)
    return None

async def fetch_crypto(session, symbol):
    for attempt in range(3):
        try:
            url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={symbol}&to_currency=USD&apikey={ALPHA_KEY}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                text = await r.text()
                print(f"[{symbol}] Response: {text[:200]}")
                d = json.loads(text)
                
                if "Note" in d or "Information" in d:
                    print(f"[{symbol}] API limit hit!")
                    await asyncio.sleep(60)
                    continue
                
                x = d.get("Realtime Currency Exchange Rate", {})
                if not x.get("5. Exchange Rate"):
                    print(f"[{symbol}] No rate in response")
                    return None
                    
                return {
                    "price":     float(x["5. Exchange Rate"]),
                    "changePct": 0.0,
                }
        except Exception as e:
            print(f"[{symbol}] Attempt {attempt+1} failed: {e}")
            await asyncio.sleep(5)
    return None

# ═══════════════════════════════════════════
# סיגנל
# ═══════════════════════════════════════════
def get_signal(chg):
    if chg > 5:  return ("🚀 BREAKOUT", "HIGH", True)
    if chg > 3:  return ("📈 MOMENTUM", "HIGH", True)
    if chg > 1:  return ("✅ חיובי",    "MED",  True)
    if chg < -5: return ("🔴 CRASH",    "HIGH", False)
    if chg < -3: return ("⚠️ SELL",     "HIGH", False)
    if chg < -1: return ("🟡 CAUTION",  "MED",  False)
    return             ("⬜ NEUTRAL",  "LOW",  None)

def fmt_price(asset, q):
    p = q["price"]
    if asset["t"] == "crypto":
        return f"${p:,.2f}"
    return f"${p:.2f}"

def fmt_chg(q):
    c = q["changePct"]
    if c == 0: return "—"
    sign = "+" if c > 0 else ""
    return f"{sign}{c:.2f}%"

# ═══════════════════════════════════════════
# סריקה — נכס אחד בכל פעם עם המתנה
# ═══════════════════════════════════════════
async def scan_all(status_msg=None, bot=None, chat_id=None):
    global last_quotes
    results = []
    total = len(ASSETS)

    async with aiohttp.ClientSession() as session:
        for i, asset in enumerate(ASSETS):
            # עדכן סטטוס אם יש
            if status_msg and bot:
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_msg,
                        text=f"🔍 <b>סורק שוק...</b>\n\n{i+1}/{total}: {asset['s']} {asset['n']}\n\n⏳ ממתין לנתונים...",
                        parse_mode="HTML"
                    )
                except:
                    pass

            try:
                if asset["t"] == "stock":
                    q = await fetch_stock(session, asset["s"])
                else:
                    q = await fetch_crypto(session, asset["s"])

                if q:
                    last_quotes[asset["s"]] = q
                    sig, level, up = get_signal(q["changePct"])
                    results.append({
                        "asset":  asset,
                        "quote":  q,
                        "signal": sig,
                        "level":  level,
                        "up":     up,
                    })
                    print(f"✅ {asset['s']}: ${q['price']:.2f} ({q['changePct']:.2f}%)")
                else:
                    # נסה להשתמש בנתונים ישנים
                    if asset["s"] in last_quotes:
                        q = last_quotes[asset["s"]]
                        sig, level, up = get_signal(q["changePct"])
                        results.append({"asset": asset, "quote": q, "signal": sig, "level": level, "up": up})
                        print(f"⚠️ {asset['s']}: נתונים ישנים")

            except Exception as e:
                print(f"❌ {asset['s']}: {e}")

            # המתנה בין קריאות — 15 שניות (מגבלת Alpha Vantage)
            if i < total - 1:
                await asyncio.sleep(15)

    return results

# ═══════════════════════════════════════════
# בניית הודעות
# ═══════════════════════════════════════════
def build_watchlist(results):
    if not results:
        return (
            "❌ <b>לא התקבלו נתונים</b>\n\n"
            "ייתכן שהגעת למגבלת ה-API החינמי (500 קריאות/יום)\n\n"
            "נסה שוב מחר או שדרג את Alpha Vantage"
        )

    time_str = datetime.now().strftime("%H:%M:%S")
    lines = [f"📊 <b>WATCHLIST — Intelligence Room</b>\n🕐 {time_str}\n"]

    for r in results:
        a, q = r["asset"], r["quote"]
        arrow = "🟢" if r["up"] else ("🔴" if r["up"] is False else "⚪")
        price = fmt_price(a, q)
        chg   = fmt_chg(q)
        sig   = r["signal"]
        lines.append(f"{arrow} <b>{a['s']}</b>  {price}  {chg}\n    └ {sig}")

    lines.append(f"\n<i>⬡ Intelligence Room · AI Trading</i>")
    return "\n".join(lines)

def build_alert(asset, q, sig):
    return (
        f"{sig.split()[0]} <b>INTELLIGENCE ROOM ALERT</b>\n\n"
        f"🏷 <b>{asset['s']}</b> — {asset['n']}\n"
        f"💰 מחיר: <b>{fmt_price(asset, q)}</b>\n"
        f"📊 שינוי: <b>{fmt_chg(q)}</b>\n"
        f"📡 סיגנל: <b>{sig}</b>\n"
        f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
        f"<i>⬡ Intelligence Room · AI Trading</i>"
    )

def build_briefing(results):
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    ups   = [r for r in results if r["quote"]["changePct"] > 1]
    downs = [r for r in results if r["quote"]["changePct"] < -1]

    msg = f"🌅 <b>תדריך — Intelligence Room</b>\n📅 {date_str}\n\n"

    if ups:
        msg += "🚀 <b>עולים:</b>\n"
        for r in ups:
            msg += f"• <b>{r['asset']['s']}</b>: {fmt_price(r['asset'],r['quote'])} ({fmt_chg(r['quote'])})\n"
        msg += "\n"

    if downs:
        msg += "⚠️ <b>יורדים:</b>\n"
        for r in downs:
            msg += f"• <b>{r['asset']['s']}</b>: {fmt_price(r['asset'],r['quote'])} ({fmt_chg(r['quote'])})\n"
        msg += "\n"

    if not ups and not downs:
        msg += "📊 השוק רגוע — אין תנועות משמעותיות\n\n"

    msg += f"📈 {len(results)} נכסים · {len(ups)} עולים · {len(downs)} יורדים\n"
    msg += f"\n<i>⬡ Intelligence Room · AI Trading</i>"
    return msg

# ═══════════════════════════════════════════
# תפריט ראשי
# ═══════════════════════════════════════════
def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Watchlist", callback_data="watchlist"),
            InlineKeyboardButton("🌅 תדריך",     callback_data="briefing"),
        ],
        [
            InlineKeyboardButton("🔍 סריקה מלאה", callback_data="scan"),
            InlineKeyboardButton("ℹ️ עזרה",       callback_data="help"),
        ],
    ])

# ═══════════════════════════════════════════
# פקודות
# ═══════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬡ <b>Intelligence Room</b>\n\n"
        "ברוך הבא! אני מנטר שוק ומשלח התראות אוטומטיות.\n\n"
        "בחר פעולה:",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬡ <b>פקודות זמינות:</b>\n\n"
        "/start — תפריט ראשי\n"
        "/scan — סריקה מלאה + התראות\n"
        "/watchlist — מחירים חיים\n"
        "/briefing — תדריך בוקר\n\n"
        "⏱ הבוט סורק אוטומטית כל 30 דקות\n"
        "📡 נתונים: Alpha Vantage\n"
        "🔢 נכסים במעקב: 5",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════
# כפתורים
# ═══════════════════════════════════════════
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "help":
        await query.edit_message_text(
            "⬡ <b>פקודות:</b>\n\n"
            "/start — תפריט\n"
            "/scan — סריקה\n"
            "/watchlist — מחירים\n"
            "/briefing — תדריך\n\n"
            "⏱ סריקה אוטומטית כל 30 דקות",
            parse_mode="HTML"
        )
        return

    # הצג הודעת טעינה
    loading_texts = {
        "watchlist": "📊 <b>טוען מחירים...</b>\n\n⏳ כ-90 שניות...",
        "briefing":  "🌅 <b>מכין תדריך...</b>\n\n⏳ כ-90 שניות...",
        "scan":      "🔍 <b>סורק שוק...</b>\n\n⏳ כ-90 שניות...",
    }
    msg = await query.edit_message_text(
        loading_texts.get(query.data, "⏳ טוען..."),
        parse_mode="HTML"
    )

    results = await scan_all(
        status_msg=msg.message_id,
        bot=ctx.bot,
        chat_id=chat_id
    )

    if query.data == "watchlist":
        await ctx.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=build_watchlist(results),
            parse_mode="HTML"
        )

    elif query.data == "briefing":
        await ctx.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=build_briefing(results),
            parse_mode="HTML"
        )

    elif query.data == "scan":
        # שלח התראות
        sent = 0
        for r in results:
            if r["level"] == "HIGH":
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=build_alert(r["asset"], r["quote"], r["signal"]),
                    parse_mode="HTML"
                )
                sent += 1
                await asyncio.sleep(1)

        # שלח watchlist
        wl = build_watchlist(results)
        summary = f"\n\n✅ <b>סריקה הושלמה</b> — {sent} התראות נשלחו"
        await ctx.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=wl + summary,
            parse_mode="HTML"
        )

# ═══════════════════════════════════════════
# סריקה אוטומטית ברקע — כל 30 דקות
# ═══════════════════════════════════════════
async def auto_scan_loop(app):
    await asyncio.sleep(60)  # המתן דקה אחרי ההפעלה
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M')}] 🔄 סריקה אוטומטית...")
            results = await scan_all()

            alerts_sent = 0
            for r in results:
                if r["level"] == "HIGH":
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=build_alert(r["asset"], r["quote"], r["signal"]),
                        parse_mode="HTML"
                    )
                    alerts_sent += 1
                    await asyncio.sleep(2)

            print(f"✅ סריקה הושלמה — {len(results)} נכסים, {alerts_sent} התראות")

        except Exception as e:
            print(f"❌ שגיאה בסריקה אוטומטית: {e}")

        await asyncio.sleep(30 * 60)  # כל 30 דקות

# ═══════════════════════════════════════════
# הפעלה
# ═══════════════════════════════════════════
def main():
    print("🚀 מפעיל Intelligence Room Bot...")

    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("scan",      lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("watchlist", lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("briefing",  lambda u,c: button_handler(u,c)))
    app.add_handler(CallbackQueryHandler(button_handler))

    async def post_init(application):
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "⬡ <b>Intelligence Room הופעל!</b>\n\n"
                "✅ הבוט פועל 24/7\n"
                "📡 מנטר 5 נכסים\n"
                "⏱ סריקה אוטומטית כל 30 דקות\n\n"
                "שלח /start להתחלה"
            ),
            parse_mode="HTML"
        )
        asyncio.create_task(auto_scan_loop(application))

    app.post_init = post_init

    print("✅ הבוט פועל — ממתין להודעות...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
