import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ═══════════════════════════════════════════
# הגדרות
# ═══════════════════════════════════════════
TG_TOKEN  = os.environ.get("TG_TOKEN",  "7754804245:AAEf5lCTTU3NB7qNnOa1-HKJXcpZLDOdseM")
CHAT_ID   = os.environ.get("CHAT_ID",   "6775881845")

ASSETS = [
    {"s": "NVDA",  "n": "NVIDIA",    "t": "stock"},
    {"s": "AAPL",  "n": "Apple",     "t": "stock"},
    {"s": "TSLA",  "n": "Tesla",     "t": "stock"},
    {"s": "META",  "n": "Meta",      "t": "stock"},
    {"s": "AMD",   "n": "AMD",       "t": "stock"},
    {"s": "MSFT",  "n": "Microsoft", "t": "stock"},
    {"s": "BTC-USD","n": "Bitcoin",  "t": "crypto"},
    {"s": "ETH-USD","n": "Ethereum", "t": "crypto"},
    {"s": "SOL-USD","n": "Solana",   "t": "crypto"},
]

last_quotes = {}

# ═══════════════════════════════════════════
# שליפת נתונים — Yahoo Finance (חינמי, ללא הגבלה)
# ═══════════════════════════════════════════
async def fetch_quote(session, symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    params = {"interval": "1d", "range": "2d"}

    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            d = await r.json()
            result = d["chart"]["result"][0]
            meta   = result["meta"]

            price    = float(meta.get("regularMarketPrice", 0))
            prev     = float(meta.get("chartPreviousClose", price))
            change   = price - prev
            chg_pct  = (change / prev * 100) if prev else 0
            volume   = int(meta.get("regularMarketVolume", 0))

            print(f"✅ {symbol}: ${price:.2f} ({chg_pct:+.2f}%)")
            return {
                "price":     price,
                "changePct": round(chg_pct, 2),
                "change":    round(change, 2),
                "volume":    volume,
                "prev":      prev,
            }
    except Exception as e:
        print(f"❌ {symbol}: {e}")
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
    if asset["t"] == "crypto" or p > 1000:
        return f"${p:,.2f}"
    return f"${p:.2f}"

def fmt_chg(q):
    c = q["changePct"]
    sign = "+" if c > 0 else ""
    return f"{sign}{c:.2f}%"

# ═══════════════════════════════════════════
# סריקה מלאה
# ═══════════════════════════════════════════
async def scan_all():
    global last_quotes
    results = []

    async with aiohttp.ClientSession() as session:
        # Yahoo Finance — אפשר להריץ במקביל, אין הגבלה
        tasks = [fetch_quote(session, a["s"]) for a in ASSETS]
        quotes = await asyncio.gather(*tasks)

        for asset, q in zip(ASSETS, quotes):
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
            elif asset["s"] in last_quotes:
                # השתמש בנתונים ישנים
                q = last_quotes[asset["s"]]
                sig, level, up = get_signal(q["changePct"])
                results.append({"asset": asset, "quote": q, "signal": sig, "level": level, "up": up})
                print(f"⚠️ {asset['s']}: נתונים ישנים")

    print(f"📊 סריקה הושלמה: {len(results)}/{len(ASSETS)} נכסים")
    return results

# ═══════════════════════════════════════════
# בניית הודעות
# ═══════════════════════════════════════════
def build_watchlist(results):
    if not results:
        return "❌ <b>לא התקבלו נתונים</b>\n\nנסה שוב עוד כמה דקות."

    time_str = datetime.now().strftime("%H:%M:%S")
    lines = [f"📊 <b>WATCHLIST — Intelligence Room</b>\n🕐 {time_str}\n"]

    for r in results:
        a, q = r["asset"], r["quote"]
        arrow = "🟢" if r["up"] else ("🔴" if r["up"] is False else "⚪")
        price = fmt_price(a, q)
        chg   = fmt_chg(q)
        sig   = r["signal"]
        lines.append(f"{arrow} <b>{a['s']}</b>  {price}  <b>{chg}</b>\n    └ {sig}")

    lines.append(f"\n📡 Yahoo Finance · <i>⬡ Intelligence Room</i>")
    return "\n".join(lines)

def build_alert(asset, q, sig):
    return (
        f"{sig.split()[0]} <b>INTELLIGENCE ROOM ALERT</b>\n\n"
        f"🏷 <b>{asset['s']}</b> — {asset['n']}\n"
        f"💰 מחיר: <b>{fmt_price(asset, q)}</b>\n"
        f"📊 שינוי: <b>{fmt_chg(q)}</b>\n"
        f"📡 סיגנל: <b>{sig}</b>\n"
        f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
        f"<i>⬡ Intelligence Room · AI Trading System</i>"
    )

def build_briefing(results):
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    ups   = [r for r in results if r["quote"]["changePct"] > 1]
    downs = [r for r in results if r["quote"]["changePct"] < -1]
    neut  = [r for r in results if abs(r["quote"]["changePct"]) <= 1]

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

    if neut:
        msg += "⬜ <b>ניטרלי:</b>\n"
        for r in neut:
            msg += f"• <b>{r['asset']['s']}</b>: {fmt_price(r['asset'],r['quote'])} ({fmt_chg(r['quote'])})\n"
        msg += "\n"

    msg += f"📊 {len(results)} נכסים · {len(ups)} עולים · {len(downs)} יורדים\n"
    msg += f"📡 Yahoo Finance · <i>⬡ Intelligence Room</i>"
    return msg

# ═══════════════════════════════════════════
# תפריט
# ═══════════════════════════════════════════
def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Watchlist",    callback_data="watchlist"),
            InlineKeyboardButton("🌅 תדריך",        callback_data="briefing"),
        ],
        [
            InlineKeyboardButton("🔍 סריקה + התראות", callback_data="scan"),
            InlineKeyboardButton("ℹ️ עזרה",           callback_data="help"),
        ],
    ])

# ═══════════════════════════════════════════
# פקודות
# ═══════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬡ <b>Intelligence Room</b>\n\n"
        "ברוך הבא! אני מנטר שוק ומשלח התראות אוטומטיות.\n\n"
        "📡 מקור נתונים: Yahoo Finance\n"
        "⏱ סריקה אוטומטית: כל 30 דקות\n\n"
        "בחר פעולה:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬡ <b>פקודות זמינות:</b>\n\n"
        "/start — תפריט ראשי\n"
        "/watchlist — מחירים חיים\n"
        "/briefing — תדריך בוקר\n"
        "/scan — סריקה מלאה + התראות\n\n"
        "📡 נתונים: Yahoo Finance (חינמי, ללא הגבלה)\n"
        "⏱ סריקה אוטומטית כל 30 דקות",
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
            "/watchlist — מחירים\n"
            "/briefing — תדריך\n"
            "/scan — סריקה\n\n"
            "📡 Yahoo Finance · ⏱ כל 30 דקות",
            parse_mode="HTML"
        )
        return

    loading = {
        "watchlist": "📊 <b>טוען מחירים...</b>",
        "briefing":  "🌅 <b>מכין תדריך...</b>",
        "scan":      "🔍 <b>סורק שוק...</b>",
    }
    msg = await query.edit_message_text(loading[query.data], parse_mode="HTML")

    results = await scan_all()

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

        wl = build_watchlist(results)
        summary = f"\n\n✅ סריקה הושלמה — {sent} התראות"
        await ctx.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=wl + summary,
            parse_mode="HTML"
        )

# ═══════════════════════════════════════════
# סריקה אוטומטית — כל 30 דקות
# ═══════════════════════════════════════════
async def auto_scan_loop(app):
    await asyncio.sleep(60)
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M')}] 🔄 סריקה אוטומטית...")
            results = await scan_all()
            sent = 0
            for r in results:
                if r["level"] == "HIGH":
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=build_alert(r["asset"], r["quote"], r["signal"]),
                        parse_mode="HTML"
                    )
                    sent += 1
                    await asyncio.sleep(2)
            print(f"✅ אוטומטי: {len(results)} נכסים, {sent} התראות")
        except Exception as e:
            print(f"❌ שגיאה אוטומטית: {e}")
        await asyncio.sleep(30 * 60)

# ═══════════════════════════════════════════
# הפעלה
# ═══════════════════════════════════════════
def main():
    print("🚀 מפעיל Intelligence Room Bot...")
    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("watchlist", lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("briefing",  lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("scan",      lambda u,c: button_handler(u,c)))
    app.add_handler(CallbackQueryHandler(button_handler))

    async def post_init(application):
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "⬡ <b>Intelligence Room הופעל!</b>\n\n"
                "✅ הבוט פועל 24/7\n"
                "📡 נתונים: Yahoo Finance (ללא הגבלה)\n"
                "⏱ סריקה אוטומטית כל 30 דקות\n\n"
                "שלח /start להתחלה"
            ),
            parse_mode="HTML"
        )
        asyncio.create_task(auto_scan_loop(application))

    app.post_init = post_init
    print("✅ הבוט פועל!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
