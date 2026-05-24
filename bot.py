import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ═══════════════════════════════════════════
# הגדרות
# ═══════════════════════════════════════════
TG_TOKEN = os.environ.get("TG_TOKEN", "7754804245:AAEf5lCTTU3NB7qNnOa1-HKJXcpZLDOdseM")
CHAT_ID  = os.environ.get("CHAT_ID",  "6775881845")

ASSETS = [
    {"s": "NVDA",   "n": "NVIDIA",    "t": "stock"},
    {"s": "AAPL",   "n": "Apple",     "t": "stock"},
    {"s": "TSLA",   "n": "Tesla",     "t": "stock"},
    {"s": "META",   "n": "Meta",      "t": "stock"},
    {"s": "AMD",    "n": "AMD",       "t": "stock"},
    {"s": "MSFT",   "n": "Microsoft", "t": "stock"},
    {"s": "BTC-USD","n": "Bitcoin",   "t": "crypto"},
    {"s": "ETH-USD","n": "Ethereum",  "t": "crypto"},
    {"s": "SOL-USD","n": "Solana",    "t": "crypto"},
]

last_quotes = {}

# ═══════════════════════════════════════════
# שליפת נתונים — Yahoo Finance
# ═══════════════════════════════════════════
async def fetch_quote(session, symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    params  = {"interval": "1d", "range": "5d"}
    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            d      = await r.json()
            result = d["chart"]["result"][0]
            meta   = result["meta"]
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]

            price   = float(meta.get("regularMarketPrice", 0))
            prev    = float(meta.get("chartPreviousClose", price))
            chg_pct = round((price - prev) / prev * 100, 2) if prev else 0
            volume  = int(meta.get("regularMarketVolume", 0))

            # חישוב תמיכה/התנגדות מ-5 ימים אחרונים
            high_5d = max(closes[-5:]) if len(closes) >= 5 else price * 1.05
            low_5d  = min(closes[-5:]) if len(closes) >= 5 else price * 0.95

            print(f"✅ {symbol}: ${price:.2f} ({chg_pct:+.2f}%)")
            return {
                "price":    price,
                "changePct": chg_pct,
                "volume":   volume,
                "prev":     prev,
                "high_5d":  round(high_5d, 2),
                "low_5d":   round(low_5d,  2),
            }
    except Exception as e:
        print(f"❌ {symbol}: {e}")
        return None

# ═══════════════════════════════════════════
# מנוע סיגנלים + המלצות מסחר
# ═══════════════════════════════════════════
def get_signal(q):
    chg = q["changePct"]
    p   = q["price"]
    h5  = q["high_5d"]
    l5  = q["low_5d"]
    rng = h5 - l5 if h5 != l5 else p * 0.1

    # קביעת כיוון
    if chg > 4:
        action = "BUY"
        conf   = min(90, 70 + chg * 2)
        reason = "פריצת מומנטום חזקה"
        entry  = round(p, 2)
        target = round(p * 1.08, 2)
        stop   = round(p * 0.96, 2)
        emoji  = "🚀"
        level  = "HIGH"
    elif chg > 2:
        action = "BUY"
        conf   = 65
        reason = "מומנטום חיובי"
        entry  = round(p, 2)
        target = round(p * 1.05, 2)
        stop   = round(p * 0.97, 2)
        emoji  = "📈"
        level  = "HIGH"
    elif chg > 0.5:
        action = "WATCH"
        conf   = 55
        reason = "עלייה מתונה — המתן לאישור"
        entry  = round(l5 + rng * 0.3, 2)
        target = round(h5, 2)
        stop   = round(l5 * 0.98, 2)
        emoji  = "✅"
        level  = "MED"
    elif chg < -4:
        action = "SELL / SHORT"
        conf   = min(90, 70 + abs(chg) * 2)
        reason = "ירידה חדה — סכנת המשך"
        entry  = round(p, 2)
        target = round(p * 0.92, 2)
        stop   = round(p * 1.04, 2)
        emoji  = "🔴"
        level  = "HIGH"
    elif chg < -2:
        action = "CAUTION"
        conf   = 60
        reason = "לחץ מוכרים — המתן לייצוב"
        entry  = round(l5, 2)
        target = round(p * 0.97, 2)
        stop   = round(p * 1.03, 2)
        emoji  = "⚠️"
        level  = "HIGH"
    else:
        action = "NEUTRAL"
        conf   = 45
        reason = "אין כיוון ברור — המתן"
        entry  = round(l5 + rng * 0.4, 2)
        target = round(h5 * 0.99, 2)
        stop   = round(l5 * 0.97, 2)
        emoji  = "⬜"
        level  = "LOW"

    return {
        "action": action,
        "conf":   int(conf),
        "reason": reason,
        "entry":  entry,
        "target": target,
        "stop":   stop,
        "emoji":  emoji,
        "level":  level,
    }

def fmt_price(asset, price):
    if asset["t"] == "crypto" or price > 1000:
        return f"${price:,.2f}"
    return f"${price:.2f}"

def fmt_chg(chg):
    sign = "+" if chg > 0 else ""
    return f"{sign}{chg:.2f}%"

# ═══════════════════════════════════════════
# סריקה מלאה
# ═══════════════════════════════════════════
async def scan_all():
    global last_quotes
    results = []
    async with aiohttp.ClientSession() as session:
        tasks  = [fetch_quote(session, a["s"]) for a in ASSETS]
        quotes = await asyncio.gather(*tasks)
        for asset, q in zip(ASSETS, quotes):
            if q:
                last_quotes[asset["s"]] = q
            elif asset["s"] in last_quotes:
                q = last_quotes[asset["s"]]
                print(f"⚠️ {asset['s']}: נתונים ישנים")
            if q:
                sig = get_signal(q)
                results.append({"asset": asset, "quote": q, "sig": sig})
    print(f"📊 סריקה הושלמה: {len(results)}/{len(ASSETS)}")
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
        a, q, s = r["asset"], r["quote"], r["sig"]
        price = fmt_price(a, q["price"])
        chg   = fmt_chg(q["changePct"])
        lines.append(f"{s['emoji']} <b>{a['s']}</b>  {price}  <b>{chg}</b>\n    └ {s['action']} · {s['conf']}% ביטחון")
    lines.append(f"\n📡 Yahoo Finance · <i>⬡ Intelligence Room</i>")
    return "\n".join(lines)

def build_trade_signals(results):
    if not results:
        return "❌ אין נתונים זמינים."

    buys    = [r for r in results if r["sig"]["action"] == "BUY"]
    sells   = [r for r in results if "SELL" in r["sig"]["action"]]
    caution = [r for r in results if r["sig"]["action"] == "CAUTION"]
    watch   = [r for r in results if r["sig"]["action"] in ("WATCH", "NEUTRAL")]

    time_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg = f"💹 <b>המלצות מסחר — Intelligence Room</b>\n📅 {time_str}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    if buys:
        msg += "🟢 <b>קנייה — BUY</b>\n\n"
        for r in buys:
            a, q, s = r["asset"], r["quote"], r["sig"]
            msg += (
                f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                f"💰 מחיר נוכחי: <b>{fmt_price(a, q['price'])}</b> ({fmt_chg(q['changePct'])})\n"
                f"📥 כניסה:  <b>{fmt_price(a, s['entry'])}</b>\n"
                f"🎯 יעד:    <b>{fmt_price(a, s['target'])}</b>\n"
                f"🛑 סטופ:   <b>{fmt_price(a, s['stop'])}</b>\n"
                f"📊 ביטחון: <b>{s['conf']}%</b>\n"
                f"💡 {s['reason']}\n\n"
            )

    if sells:
        msg += "🔴 <b>מכירה — SELL</b>\n\n"
        for r in sells:
            a, q, s = r["asset"], r["quote"], r["sig"]
            msg += (
                f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                f"💰 מחיר נוכחי: <b>{fmt_price(a, q['price'])}</b> ({fmt_chg(q['changePct'])})\n"
                f"📤 כניסה לשורט: <b>{fmt_price(a, s['entry'])}</b>\n"
                f"🎯 יעד:         <b>{fmt_price(a, s['target'])}</b>\n"
                f"🛑 סטופ:        <b>{fmt_price(a, s['stop'])}</b>\n"
                f"📊 ביטחון: <b>{s['conf']}%</b>\n"
                f"💡 {s['reason']}\n\n"
            )

    if caution:
        msg += "⚠️ <b>זהירות — CAUTION</b>\n\n"
        for r in caution:
            a, q, s = r["asset"], r["quote"], r["sig"]
            msg += f"• <b>{a['s']}</b>: {fmt_price(a, q['price'])} ({fmt_chg(q['changePct'])}) — {s['reason']}\n"
        msg += "\n"

    if watch:
        msg += "⬜ <b>המתנה — WATCH</b>\n"
        for r in watch:
            a, q, s = r["asset"], r["quote"], r["sig"]
            msg += f"• <b>{a['s']}</b>: {fmt_price(a, q['price'])} ({fmt_chg(q['changePct'])})\n"
        msg += "\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 {len(buys)} קנייה · {len(sells)} מכירה · {len(caution)} זהירות\n"
    msg += "⚠️ <i>זו אינה המלצת השקעה. סחר באחריותך.</i>\n"
    msg += f"<i>⬡ Intelligence Room · AI Trading</i>"
    return msg

def build_briefing(results):
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    ups   = [r for r in results if r["quote"]["changePct"] > 1]
    downs = [r for r in results if r["quote"]["changePct"] < -1]

    msg = f"🌅 <b>תדריך — Intelligence Room</b>\n📅 {date_str}\n\n"

    if ups:
        msg += "🚀 <b>עולים:</b>\n"
        for r in ups:
            msg += f"• <b>{r['asset']['s']}</b>: {fmt_price(r['asset'], r['quote']['price'])} ({fmt_chg(r['quote']['changePct'])})\n"
        msg += "\n"

    if downs:
        msg += "⚠️ <b>יורדים:</b>\n"
        for r in downs:
            msg += f"• <b>{r['asset']['s']}</b>: {fmt_price(r['asset'], r['quote']['price'])} ({fmt_chg(r['quote']['changePct'])})\n"
        msg += "\n"

    msg += f"📊 {len(results)} נכסים · {len(ups)} עולים · {len(downs)} יורדים\n"
    msg += f"<i>⬡ Intelligence Room · AI Trading</i>"
    return msg

def build_alert(asset, q, sig):
    a = asset
    return (
        f"{sig['emoji']} <b>INTELLIGENCE ROOM ALERT</b>\n\n"
        f"🏷 <b>{a['s']}</b> — {a['n']}\n"
        f"💰 מחיר: <b>{fmt_price(a, q['price'])}</b>\n"
        f"📊 שינוי: <b>{fmt_chg(q['changePct'])}</b>\n"
        f"📥 כניסה: <b>{fmt_price(a, sig['entry'])}</b>\n"
        f"🎯 יעד:   <b>{fmt_price(a, sig['target'])}</b>\n"
        f"🛑 סטופ:  <b>{fmt_price(a, sig['stop'])}</b>\n"
        f"📡 סיגנל: <b>{sig['action']}</b> · {sig['conf']}%\n"
        f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
        f"<i>⬡ Intelligence Room · AI Trading</i>"
    )

# ═══════════════════════════════════════════
# תפריט
# ═══════════════════════════════════════════
def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Watchlist",      callback_data="watchlist"),
            InlineKeyboardButton("💹 קנייה/מכירה",    callback_data="signals"),
        ],
        [
            InlineKeyboardButton("🌅 תדריך בוקר",     callback_data="briefing"),
            InlineKeyboardButton("🔍 סריקה + התראות", callback_data="scan"),
        ],
        [
            InlineKeyboardButton("ℹ️ עזרה",            callback_data="help"),
        ],
    ])

def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 תפריט ראשי", callback_data="menu")]
    ])

# ═══════════════════════════════════════════
# פקודות
# ═══════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬡ <b>Intelligence Room</b>\n\n"
        "ברוך הבא! אני מנטר שוק ומשלח המלצות מסחר.\n\n"
        "📡 נתונים: Yahoo Finance\n"
        "💹 המלצות: כניסה · יעד · סטופ\n"
        "⏱ סריקה אוטומטית כל 30 דקות\n\n"
        "בחר פעולה:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⬡ <b>פקודות זמינות:</b>\n\n"
        "/start — תפריט ראשי\n"
        "/watchlist — מחירים חיים\n"
        "/signals — המלצות קנייה/מכירה\n"
        "/briefing — תדריך בוקר\n"
        "/scan — סריקה מלאה + התראות\n\n"
        "⚠️ <i>זו אינה המלצת השקעה. סחר באחריותך.</i>",
        parse_mode="HTML",
        reply_markup=back_menu()
    )

# ═══════════════════════════════════════════
# כפתורים
# ═══════════════════════════════════════════
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    # חזרה לתפריט
    if query.data == "menu":
        await query.edit_message_text(
            "⬡ <b>Intelligence Room</b>\n\nבחר פעולה:",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
        return

    if query.data == "help":
        await query.edit_message_text(
            "⬡ <b>פקודות:</b>\n\n"
            "/start — תפריט\n"
            "/watchlist — מחירים\n"
            "/signals — קנייה/מכירה\n"
            "/briefing — תדריך\n"
            "/scan — סריקה\n\n"
            "⚠️ <i>זו אינה המלצת השקעה.</i>",
            parse_mode="HTML",
            reply_markup=back_menu()
        )
        return

    # טעינה
    loading = {
        "watchlist": "📊 <b>טוען מחירים...</b>",
        "signals":   "💹 <b>מחשב המלצות מסחר...</b>",
        "briefing":  "🌅 <b>מכין תדריך...</b>",
        "scan":      "🔍 <b>סורק שוק...</b>",
    }
    msg = await query.edit_message_text(
        loading.get(query.data, "⏳ טוען..."),
        parse_mode="HTML"
    )

    results = await scan_all()

    if query.data == "watchlist":
        text = build_watchlist(results)
    elif query.data == "signals":
        text = build_trade_signals(results)
    elif query.data == "briefing":
        text = build_briefing(results)
    elif query.data == "scan":
        sent = 0
        for r in results:
            if r["sig"]["level"] == "HIGH":
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=build_alert(r["asset"], r["quote"], r["sig"]),
                    parse_mode="HTML"
                )
                sent += 1
                await asyncio.sleep(1)
        text = build_watchlist(results) + f"\n\n✅ סריקה הושלמה — {sent} התראות נשלחו"
    else:
        text = "❌ פעולה לא ידועה"

    await ctx.bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg.message_id,
        text=text,
        parse_mode="HTML",
        reply_markup=back_menu()
    )

# ═══════════════════════════════════════════
# סריקה אוטומטית — כל 30 דקות
# ═══════════════════════════════════════════
async def auto_scan_loop(app):
    await asyncio.sleep(90)
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M')}] 🔄 סריקה אוטומטית...")
            results = await scan_all()
            sent = 0
            for r in results:
                if r["sig"]["level"] == "HIGH":
                    await app.bot.send_message(
                        chat_id=CHAT_ID,
                        text=build_alert(r["asset"], r["quote"], r["sig"]),
                        parse_mode="HTML"
                    )
                    sent += 1
                    await asyncio.sleep(2)
            print(f"✅ אוטומטי: {len(results)} נכסים, {sent} התראות")
        except Exception as e:
            print(f"❌ שגיאה: {e}")
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
    app.add_handler(CommandHandler("signals",   lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("briefing",  lambda u,c: button_handler(u,c)))
    app.add_handler(CommandHandler("scan",      lambda u,c: button_handler(u,c)))
    app.add_handler(CallbackQueryHandler(button_handler))

    async def post_init(application):
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=(
                "⬡ <b>Intelligence Room הופעל!</b>\n\n"
                "✅ פועל 24/7\n"
                "💹 המלצות: כניסה · יעד · סטופ\n"
                "📡 Yahoo Finance · ⏱ כל 30 דקות\n\n"
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
