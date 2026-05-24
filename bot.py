import os
import asyncio
import aiohttp
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ═══════════════════════════════════════════
# הגדרות מאובטחות
# ═══════════════════════════════════════════
TG_TOKEN  = os.environ.get("TG_TOKEN",  "7754804245:AAEf5lCTTU3NB7qNnOa1-HKJXcpZLDOdseM")
CHAT_ID   = os.environ.get("CHAT_ID",   "6775881845")
ADMIN_ID  = int(os.environ.get("ADMIN_ID", "6775881845"))

# ── פרטי תשלום ──
PAYMENT_INFO = {
    "bit":    "שלח לביט למספר: *יתקבל לאחר פנייה*",
    "paybox": "שלח לפייבוקס למספר: *יתקבל לאחר פנייה*",
    "bank":   (
        "🏦 בנק הבינלאומי הראשון לישראל\n"
        "סניף: 062 — קרית גת\n"
        "מספר חשבון: 259794\n"
        "מספר IBAN/זיהוי: 034653667\n"
        "מדינה: ישראל"
    ),
}

PRICES = {
    "trial":   {"name": "ניסיון חינמי",  "price": 0,    "days": 3},
    "monthly": {"name": "מנוי חודשי",    "price": 300,  "days": 30},
    "yearly":  {"name": "מנוי שנתי",     "price": 3000, "days": 365},
}

ASSETS = [
    {"s": "NVDA",    "n": "NVIDIA",    "t": "stock"},
    {"s": "AAPL",    "n": "Apple",     "t": "stock"},
    {"s": "TSLA",    "n": "Tesla",     "t": "stock"},
    {"s": "META",    "n": "Meta",      "t": "stock"},
    {"s": "AMD",     "n": "AMD",       "t": "stock"},
    {"s": "MSFT",    "n": "Microsoft", "t": "stock"},
    {"s": "BTC-USD", "n": "Bitcoin",   "t": "crypto"},
    {"s": "ETH-USD", "n": "Ethereum",  "t": "crypto"},
    {"s": "SOL-USD", "n": "Solana",    "t": "crypto"},
]

# ═══════════════════════════════════════════
# מסד נתונים מאובטח
# ═══════════════════════════════════════════
DB_FILE      = "users.json"
BLOCKED_FILE = "blocked.json"
LOG_FILE     = "security.log"

def load_db():
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {"users": {}, "pending": {}, "referrals": {}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def load_blocked():
    try:
        with open(BLOCKED_FILE, "r") as f:
            return json.load(f)
    except:
        return {"blocked": [], "attempts": {}}

def save_blocked(data):
    with open(BLOCKED_FILE, "w") as f:
        json.dump(data, f, indent=2)

def security_log(event, user_id, detail=""):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{t}] {event} | UID:{user_id} | {detail}\n")

# ── בדיקות אבטחה ──
def is_blocked(user_id):
    bl = load_blocked()
    return str(user_id) in bl["blocked"]

def record_attempt(user_id):
    bl  = load_blocked()
    uid = str(user_id)
    bl["attempts"][uid] = bl["attempts"].get(uid, 0) + 1
    if bl["attempts"][uid] >= 5:
        if uid not in bl["blocked"]:
            bl["blocked"].append(uid)
            security_log("AUTO_BLOCK", user_id, f"יותר מ-5 ניסיונות")
    save_blocked(bl)
    return bl["attempts"][uid]

def is_admin(user_id):
    return int(user_id) == ADMIN_ID

# ── ניהול משתמשים ──
def get_user(user_id):
    db = load_db()
    return db["users"].get(str(user_id))

def is_subscribed(user_id):
    if is_admin(user_id):
        return True
    user = get_user(user_id)
    if not user or not user.get("expiry"):
        return False
    return datetime.fromisoformat(user["expiry"]) > datetime.now()

def is_trial_used(user_id):
    user = get_user(user_id)
    return user.get("trial_used", False) if user else False

def get_expiry_str(user_id):
    user = get_user(user_id)
    if not user or not user.get("expiry"):
        return "—"
    exp  = datetime.fromisoformat(user["expiry"])
    days = max(0, (exp - datetime.now()).days)
    return f"{exp.strftime('%d/%m/%Y')} ({days} ימים)"

def add_subscription(user_id, username, plan_key, days):
    db  = load_db()
    uid = str(user_id)
    now = datetime.now()
    usr = db["users"].get(uid, {})
    cur = usr.get("expiry")
    base = datetime.fromisoformat(cur) if cur and datetime.fromisoformat(cur) > now else now
    exp  = base + timedelta(days=days)

    db["users"][uid] = {
        "user_id":        user_id,
        "username":       username,
        "plan":           plan_key,
        "expiry":         exp.isoformat(),
        "joined":         usr.get("joined", now.isoformat()),
        "trial_used":     True if plan_key == "trial" else usr.get("trial_used", False),
        "referrals_count": usr.get("referrals_count", 0),
        "referral_code":  usr.get("referral_code", f"REF{user_id}"),
        "approved_by":    "admin",
        "approved_at":    now.isoformat(),
    }
    save_db(db)
    security_log("SUBSCRIPTION", user_id, f"plan={plan_key} days={days} exp={exp.strftime('%d/%m/%Y')}")

def add_pending(user_id, username, plan_key, method):
    db = load_db()
    db["pending"][str(user_id)] = {
        "user_id":  user_id,
        "username": username,
        "plan":     plan_key,
        "method":   method,
        "time":     datetime.now().isoformat(),
        "token":    secrets.token_hex(8),
    }
    save_db(db)

def remove_pending(user_id):
    db = load_db()
    db["pending"].pop(str(user_id), None)
    save_db(db)

def add_referral(referrer_id, new_user_id):
    db  = load_db()
    rid = str(referrer_id)
    if rid not in db["referrals"]:
        db["referrals"][rid] = []
    if str(new_user_id) not in db["referrals"][rid]:
        db["referrals"][rid].append(str(new_user_id))
        count = len(db["referrals"][rid])
        usr   = db["users"].get(rid, {})
        db["users"][rid] = {**usr, "referrals_count": count}
        save_db(db)
        return count
    return len(db["referrals"].get(rid, []))

# ═══════════════════════════════════════════
# Yahoo Finance
# ═══════════════════════════════════════════
last_quotes = {}

async def fetch_quote(session, symbol):
    url     = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with session.get(url, headers=headers, params={"interval":"1d","range":"5d"},
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            d      = await r.json()
            result = d["chart"]["result"][0]
            meta   = result["meta"]
            closes = [c for c in result.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if c]
            price   = float(meta.get("regularMarketPrice", 0))
            prev    = float(meta.get("chartPreviousClose", price))
            chg_pct = round((price-prev)/prev*100, 2) if prev else 0
            high_5d = max(closes[-5:]) if len(closes)>=5 else price*1.05
            low_5d  = min(closes[-5:]) if len(closes)>=5 else price*0.95
            return {"price":price,"changePct":chg_pct,"volume":int(meta.get("regularMarketVolume",0)),
                    "prev":prev,"high_5d":round(high_5d,2),"low_5d":round(low_5d,2)}
    except Exception as e:
        print(f"❌ {symbol}: {e}")
        return None

def get_signal(q):
    chg=q["changePct"]; p=q["price"]; h5=q["high_5d"]; l5=q["low_5d"]
    rng=h5-l5 if h5!=l5 else p*0.1
    if chg>4:   return {"action":"BUY",        "conf":min(90,70+chg*2),"reason":"פריצת מומנטום חזקה",      "entry":round(p,2),           "target":round(p*1.08,2),"stop":round(p*0.96,2),"emoji":"🚀","level":"HIGH"}
    if chg>2:   return {"action":"BUY",        "conf":65,              "reason":"מומנטום חיובי",            "entry":round(p,2),           "target":round(p*1.05,2),"stop":round(p*0.97,2),"emoji":"📈","level":"HIGH"}
    if chg>0.5: return {"action":"WATCH",      "conf":55,              "reason":"עלייה מתונה — המתן",       "entry":round(l5+rng*0.3,2), "target":round(h5,2),    "stop":round(l5*0.98,2),"emoji":"✅","level":"MED"}
    if chg<-4:  return {"action":"SELL/SHORT", "conf":min(90,70+abs(chg)*2),"reason":"ירידה חדה — סכנה",   "entry":round(p,2),           "target":round(p*0.92,2),"stop":round(p*1.04,2),"emoji":"🔴","level":"HIGH"}
    if chg<-2:  return {"action":"CAUTION",    "conf":60,              "reason":"לחץ מוכרים — המתן",        "entry":round(l5,2),          "target":round(p*0.97,2),"stop":round(p*1.03,2),"emoji":"⚠️","level":"HIGH"}
    return              {"action":"NEUTRAL",   "conf":45,              "reason":"אין כיוון ברור",            "entry":round(l5+rng*0.4,2), "target":round(h5*0.99,2),"stop":round(l5*0.97,2),"emoji":"⬜","level":"LOW"}

def fp(asset, price):
    return f"${price:,.2f}" if (asset["t"]=="crypto" or price>1000) else f"${price:.2f}"

def fc(chg):
    return f"{'+' if chg>0 else ''}{chg:.2f}%"

async def scan_all():
    global last_quotes
    results = []
    async with aiohttp.ClientSession() as session:
        qs = await asyncio.gather(*[fetch_quote(session, a["s"]) for a in ASSETS])
        for asset, q in zip(ASSETS, qs):
            if q:   last_quotes[asset["s"]] = q
            elif asset["s"] in last_quotes: q = last_quotes[asset["s"]]
            if q:   results.append({"asset":asset,"quote":q,"sig":get_signal(q)})
    return results

# ═══════════════════════════════════════════
# הודעות
# ═══════════════════════════════════════════
def build_watchlist(results):
    if not results: return "❌ אין נתונים — נסה שוב."
    t     = datetime.now().strftime("%H:%M:%S")
    lines = [f"📊 <b>WATCHLIST — Intelligence Room</b>\n🕐 {t}\n"]
    for r in results:
        a,q,s = r["asset"],r["quote"],r["sig"]
        lines.append(f"{s['emoji']} <b>{a['s']}</b>  {fp(a,q['price'])}  <b>{fc(q['changePct'])}</b>\n    └ {s['action']} · {int(s['conf'])}% ביטחון")
    lines.append("\n📡 Yahoo Finance · <i>⬡ Intelligence Room</i>")
    return "\n".join(lines)

def build_signals(results):
    if not results: return "❌ אין נתונים."
    buys    = [r for r in results if r["sig"]["action"]=="BUY"]
    sells   = [r for r in results if "SELL" in r["sig"]["action"]]
    caution = [r for r in results if r["sig"]["action"]=="CAUTION"]
    watch   = [r for r in results if r["sig"]["action"] in ("WATCH","NEUTRAL")]
    t   = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg = f"💹 <b>המלצות מסחר — Intelligence Room</b>\n📅 {t}\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if buys:
        msg += "🟢 <b>קנייה — BUY</b>\n\n"
        for r in buys:
            a,q,s=r["asset"],r["quote"],r["sig"]
            msg += (f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                    f"💰 מחיר: <b>{fp(a,q['price'])}</b> ({fc(q['changePct'])})\n"
                    f"📥 כניסה:  <b>{fp(a,s['entry'])}</b>\n"
                    f"🎯 יעד:    <b>{fp(a,s['target'])}</b>\n"
                    f"🛑 סטופ:   <b>{fp(a,s['stop'])}</b>\n"
                    f"📊 ביטחון: <b>{int(s['conf'])}%</b>\n"
                    f"💡 {s['reason']}\n\n")
    if sells:
        msg += "🔴 <b>מכירה — SELL</b>\n\n"
        for r in sells:
            a,q,s=r["asset"],r["quote"],r["sig"]
            msg += (f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                    f"💰 מחיר: <b>{fp(a,q['price'])}</b> ({fc(q['changePct'])})\n"
                    f"📤 כניסה שורט: <b>{fp(a,s['entry'])}</b>\n"
                    f"🎯 יעד:        <b>{fp(a,s['target'])}</b>\n"
                    f"🛑 סטופ:       <b>{fp(a,s['stop'])}</b>\n"
                    f"📊 ביטחון: <b>{int(s['conf'])}%</b>\n"
                    f"💡 {s['reason']}\n\n")
    if caution:
        msg += "⚠️ <b>זהירות:</b>\n"
        for r in caution:
            a,q,s=r["asset"],r["quote"],r["sig"]
            msg += f"• <b>{a['s']}</b>: {fp(a,q['price'])} ({fc(q['changePct'])}) — {s['reason']}\n"
        msg += "\n"
    if watch:
        msg += "⬜ <b>המתנה:</b>\n"
        for r in watch:
            a,q,s=r["asset"],r["quote"],r["sig"]
            msg += f"• <b>{a['s']}</b>: {fp(a,q['price'])} ({fc(q['changePct'])})\n"
        msg += "\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n📊 {len(buys)} קנייה · {len(sells)} מכירה · {len(caution)} זהירות\n"
    msg += "⚠️ <i>זו אינה המלצת השקעה. סחר באחריותך.</i>\n<i>⬡ Intelligence Room</i>"
    return msg

def build_briefing(results):
    t   = datetime.now().strftime("%d/%m/%Y %H:%M")
    ups = [r for r in results if r["quote"]["changePct"]>1]
    dns = [r for r in results if r["quote"]["changePct"]<-1]
    msg = f"🌅 <b>תדריך — Intelligence Room</b>\n📅 {t}\n\n"
    if ups:
        msg += "🚀 <b>עולים:</b>\n"
        for r in ups: msg += f"• <b>{r['asset']['s']}</b>: {fp(r['asset'],r['quote']['price'])} ({fc(r['quote']['changePct'])})\n"
        msg += "\n"
    if dns:
        msg += "⚠️ <b>יורדים:</b>\n"
        for r in dns: msg += f"• <b>{r['asset']['s']}</b>: {fp(r['asset'],r['quote']['price'])} ({fc(r['quote']['changePct'])})\n"
        msg += "\n"
    msg += f"📊 {len(results)} נכסים · {len(ups)} עולים · {len(dns)} יורדים\n<i>⬡ Intelligence Room</i>"
    return msg

def build_alert(asset, q, sig):
    return (f"{sig['emoji']} <b>INTELLIGENCE ROOM ALERT</b>\n\n"
            f"🏷 <b>{asset['s']}</b> — {asset['n']}\n"
            f"💰 מחיר: <b>{fp(asset,q['price'])}</b>\n"
            f"📊 שינוי: <b>{fc(q['changePct'])}</b>\n"
            f"📥 כניסה: <b>{fp(asset,sig['entry'])}</b>\n"
            f"🎯 יעד:   <b>{fp(asset,sig['target'])}</b>\n"
            f"🛑 סטופ:  <b>{fp(asset,sig['stop'])}</b>\n"
            f"📡 {sig['action']} · {int(sig['conf'])}%\n"
            f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
            f"<i>⬡ Intelligence Room · AI Trading</i>")

# ═══════════════════════════════════════════
# תפריטים
# ═══════════════════════════════════════════
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Watchlist",          callback_data="watchlist"),
         InlineKeyboardButton("💹 קנייה/מכירה",        callback_data="signals")],
        [InlineKeyboardButton("🌅 תדריך בוקר",         callback_data="briefing"),
         InlineKeyboardButton("🔍 סריקה + התראות",     callback_data="scan")],
        [InlineKeyboardButton("👑 מנויים",              callback_data="subscribe"),
         InlineKeyboardButton("👥 חבר מביא חבר",       callback_data="referral")],
        [InlineKeyboardButton("ℹ️ עזרה",                callback_data="help")],
    ])

def sub_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 ניסיון חינמי — 3 ימים",  callback_data="plan_trial")],
        [InlineKeyboardButton("📅 מנוי חודשי — ₪300",       callback_data="plan_monthly")],
        [InlineKeyboardButton("🏆 מנוי שנתי — ₪3,000",      callback_data="plan_yearly")],
        [InlineKeyboardButton("🔙 חזרה",                     callback_data="menu")],
    ])

def pay_menu(plan_key):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ביט",           callback_data=f"pay_bit_{plan_key}")],
        [InlineKeyboardButton("💳 פייבוקס",       callback_data=f"pay_paybox_{plan_key}")],
        [InlineKeyboardButton("🏦 העברה בנקאית", callback_data=f"pay_bank_{plan_key}")],
        [InlineKeyboardButton("🔙 חזרה",          callback_data="subscribe")],
    ])

def back_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 רענן", callback_data="menu"),
         InlineKeyboardButton("🔙 תפריט ראשי", callback_data="menu")]
    ])

def no_sub_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 הצטרף עכשיו", callback_data="subscribe")],
        [InlineKeyboardButton("🔙 תפריט",       callback_data="menu")],
    ])

def action_menu(action):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 רענן",        callback_data=action),
         InlineKeyboardButton("🔙 תפריט",       callback_data="menu")]
    ])

# ═══════════════════════════════════════════
# בדיקת גישה
# ═══════════════════════════════════════════
async def check_access(update, ctx, callback=False):
    uid = update.effective_user.id

    # חסום?
    if is_blocked(uid) and not is_admin(uid):
        security_log("BLOCKED_ATTEMPT", uid)
        msg = "🚫 הגישה שלך נחסמה. פנה לתמיכה."
        if callback:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return False

    # מנוי?
    if is_subscribed(uid):
        return True

    # אין מנוי
    security_log("NO_SUB_ATTEMPT", uid)
    msg = ("🔒 <b>תוכן זה זמין למנויים בלבד</b>\n\n"
           "הצטרף ל-Intelligence Room:\n"
           "🆓 ניסיון חינמי 3 ימים\n"
           "📅 מנוי חודשי ₪300\n"
           "🏆 מנוי שנתי ₪3,000\n\n"
           "לחץ להצטרפות ↓")
    if callback:
        await update.callback_query.edit_message_text(msg, parse_mode="HTML", reply_markup=no_sub_menu())
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=no_sub_menu())
    return False

# ═══════════════════════════════════════════
# פקודות
# ═══════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.first_name or "משתמש"

    # חסום?
    if is_blocked(uid) and not is_admin(uid):
        await update.message.reply_text("🚫 הגישה שלך נחסמה. פנה לתמיכה.")
        return

    # טיפול בקוד הפניה
    args = ctx.args
    if args and args[0].startswith("REF"):
        referrer_id = args[0][3:]
        if str(referrer_id) != str(uid):
            count = add_referral(referrer_id, uid)
            if count > 0 and count % 2 == 0:
                add_subscription(int(referrer_id), "", "monthly", 30)
                try:
                    await ctx.bot.send_message(
                        chat_id=int(referrer_id),
                        text=("🎉 <b>מזל טוב!</b>\n\n"
                              "צירפת 2 חברים — קיבלת <b>חודש חינמי!</b>\n\n"
                              f"תוקף חדש: {get_expiry_str(referrer_id)}\n\n"
                              "<i>⬡ Intelligence Room</i>"),
                        parse_mode="HTML"
                    )
                except: pass

    # רישום משתמש חדש
    db = load_db()
    if str(uid) not in db["users"]:
        db["users"][str(uid)] = {
            "user_id":        uid,
            "username":       uname,
            "plan":           None,
            "expiry":         None,
            "joined":         datetime.now().isoformat(),
            "trial_used":     False,
            "referrals_count": 0,
            "referral_code":  f"REF{uid}",
        }
        save_db(db)
        security_log("NEW_USER", uid, f"username={uname}")

    sub    = is_subscribed(uid)
    status = f"✅ מנוי פעיל עד: {get_expiry_str(uid)}" if sub else "❌ אין מנוי פעיל"

    await update.message.reply_text(
        f"⬡ <b>Intelligence Room</b>\n\n"
        f"ברוך הבא! 👋\n"
        f"{status}\n\n"
        f"בחר פעולה:",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

# ── לוח בקרה מנהל ──
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        record_attempt(update.effective_user.id)
        security_log("UNAUTHORIZED_ADMIN", update.effective_user.id)
        return

    db     = load_db()
    users  = db["users"]
    pend   = db["pending"]
    active = [u for u in users.values()
              if u.get("expiry") and datetime.fromisoformat(u["expiry"]) > datetime.now()]

    msg = (f"👑 <b>לוח בקרה — מנהל</b>\n\n"
           f"👥 סה\"כ משתמשים: {len(users)}\n"
           f"✅ מנויים פעילים: {len(active)}\n"
           f"⏳ ממתינים לאישור: {len(pend)}\n\n")

    if pend:
        msg += "⏳ <b>ממתינים לאישור:</b>\n\n"
        for uid, p in pend.items():
            plan = PRICES.get(p["plan"], {})
            t    = datetime.fromisoformat(p["time"]).strftime("%d/%m %H:%M")
            msg += (f"👤 @{p.get('username','?')} (ID: {uid})\n"
                    f"📋 {plan.get('name','?')} — ₪{plan.get('price',0)}\n"
                    f"💳 {p.get('method','?')} · {t}\n"
                    f"✅ /approve_{uid}\n"
                    f"❌ /reject_{uid}\n\n")

    if active:
        msg += "✅ <b>מנויים פעילים:</b>\n"
        for u in active[:10]:
            exp = datetime.fromisoformat(u["expiry"]).strftime("%d/%m/%Y")
            msg += f"• @{u.get('username','?')} — {u.get('plan','?')} עד {exp}\n"

    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid  = update.message.text.replace("/approve_", "").strip()
    db   = load_db()
    pend = db["pending"].get(uid)
    if not pend:
        await update.message.reply_text("❌ לא נמצא.")
        return
    plan = PRICES[pend["plan"]]
    add_subscription(int(uid), pend.get("username",""), pend["plan"], plan["days"])
    remove_pending(uid)
    security_log("APPROVED", uid, f"plan={pend['plan']} by_admin={ADMIN_ID}")
    await update.message.reply_text(f"✅ אושר! @{pend.get('username','?')} — {plan['name']}")
    try:
        await ctx.bot.send_message(
            chat_id=int(uid),
            text=(f"✅ <b>המנוי שלך אושר!</b>\n\n"
                  f"תוכנית: <b>{plan['name']}</b>\n"
                  f"תוקף: <b>{get_expiry_str(uid)}</b>\n\n"
                  f"שלח /start להתחלה 🚀\n\n"
                  f"<i>⬡ Intelligence Room</i>"),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 פתח תפריט", callback_data="menu")]])
        )
    except: pass

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid  = update.message.text.replace("/reject_", "").strip()
    db   = load_db()
    pend = db["pending"].get(uid)
    if not pend:
        await update.message.reply_text("❌ לא נמצא.")
        return
    remove_pending(uid)
    security_log("REJECTED", uid, f"by_admin={ADMIN_ID}")
    await update.message.reply_text(f"❌ נדחה — @{pend.get('username','?')}")
    try:
        await ctx.bot.send_message(
            chat_id=int(uid),
            text=("❌ <b>התשלום לא אושר</b>\n\n"
                  "אנא שלח צילום מסך ברור של אישור התשלום.\n\n"
                  "<i>⬡ Intelligence Room</i>"),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 תפריט", callback_data="menu")]])
        )
    except: pass

async def cmd_block(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid = update.message.text.replace("/block_", "").strip()
    bl  = load_blocked()
    if uid not in bl["blocked"]:
        bl["blocked"].append(uid)
        save_blocked(bl)
        security_log("MANUAL_BLOCK", uid, f"by_admin={ADMIN_ID}")
        await update.message.reply_text(f"🚫 משתמש {uid} נחסם.")
    else:
        await update.message.reply_text(f"⚠️ משתמש {uid} כבר חסום.")

async def cmd_unblock(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid = update.message.text.replace("/unblock_", "").strip()
    bl  = load_blocked()
    if uid in bl["blocked"]:
        bl["blocked"].remove(uid)
        save_blocked(bl)
        security_log("UNBLOCK", uid, f"by_admin={ADMIN_ID}")
        await update.message.reply_text(f"✅ משתמש {uid} שוחרר.")

# ═══════════════════════════════════════════
# כפתורים
# ═══════════════════════════════════════════
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    uid     = query.from_user.id
    uname   = query.from_user.username or query.from_user.first_name or "משתמש"
    chat_id = query.message.chat_id
    data    = query.data

    # חסום?
    if is_blocked(uid) and not is_admin(uid):
        await query.answer("🚫 הגישה שלך נחסמה.", show_alert=True)
        return

    # ── תפריט ──
    if data == "menu":
        sub    = is_subscribed(uid)
        status = f"✅ מנוי פעיל עד: {get_expiry_str(uid)}" if sub else "❌ אין מנוי פעיל"
        await query.edit_message_text(
            f"⬡ <b>Intelligence Room</b>\n\n{status}\n\nבחר פעולה:",
            parse_mode="HTML", reply_markup=main_menu()
        )
        return

    # ── עזרה ──
    if data == "help":
        await query.edit_message_text(
            "⬡ <b>פקודות זמינות:</b>\n\n"
            "/start — תפריט ראשי\n"
            "/watchlist — מחירים חיים\n"
            "/signals — קנייה/מכירה\n"
            "/briefing — תדריך בוקר\n"
            "/scan — סריקה מלאה\n\n"
            "⚠️ <i>זו אינה המלצת השקעה. סחר באחריותך.</i>",
            parse_mode="HTML", reply_markup=back_menu()
        )
        return

    # ── מנויים ──
    if data == "subscribe":
        sub = is_subscribed(uid)
        if sub:
            txt = f"✅ <b>יש לך מנוי פעיל!</b>\n\nתוקף: {get_expiry_str(uid)}\n\nרוצה לחדש?"
        else:
            txt = ("👑 <b>Intelligence Room — מנויים</b>\n\n"
                   "🆓 <b>ניסיון חינמי</b> — 3 ימים\n"
                   "📅 <b>מנוי חודשי</b> — ₪300/חודש\n"
                   "🏆 <b>מנוי שנתי</b> — ₪3,000/שנה\n   (חסכון ₪600 לעומת חודשי)\n\n"
                   "בחר תוכנית:")
        await query.edit_message_text(txt, parse_mode="HTML", reply_markup=sub_menu())
        return

    # ── בחירת תוכנית ──
    if data.startswith("plan_"):
        plan_key = data.replace("plan_", "")
        plan     = PRICES.get(plan_key)
        if not plan: return

        if plan_key == "trial":
            if is_trial_used(uid):
                await query.edit_message_text(
                    "❌ <b>כבר השתמשת בניסיון החינמי</b>\n\nשדרג למנוי:",
                    parse_mode="HTML", reply_markup=sub_menu()
                )
                return
            add_subscription(uid, uname, "trial", 3)
            security_log("TRIAL_ACTIVATED", uid)
            await ctx.bot.send_message(chat_id=ADMIN_ID,
                text=f"🆓 ניסיון חינמי הופעל: @{uname} (ID:{uid})")
            await query.edit_message_text(
                "🎉 <b>הניסיון החינמי הופעל!</b>\n\n"
                f"✅ תוקף: {get_expiry_str(uid)}\n\n"
                "תהנה מ-Intelligence Room!\n<i>⬡ Intelligence Room</i>",
                parse_mode="HTML", reply_markup=back_menu()
            )
            return

        await query.edit_message_text(
            f"💳 <b>{plan['name']} — ₪{plan['price']}</b>\n\nבחר אמצעי תשלום:",
            parse_mode="HTML", reply_markup=pay_menu(plan_key)
        )
        return

    # ── בחירת תשלום ──
    if data.startswith("pay_"):
        parts    = data.split("_")
        method   = parts[1]
        plan_key = parts[2]
        plan     = PRICES.get(plan_key)
        if not plan: return

        details = {
            "bit":    f"💳 <b>ביט</b>\nשלח ₪{plan['price']} למספר:\n<b>{PAYMENT_INFO['bit']}</b>",
            "paybox": f"💳 <b>פייבוקס</b>\nשלח ₪{plan['price']} למספר:\n<b>{PAYMENT_INFO['paybox']}</b>",
            "bank":   f"🏦 <b>העברה בנקאית</b>\n\n{PAYMENT_INFO['bank']}\n\nסכום להעברה: <b>₪{plan['price']}</b>",
        }

        add_pending(uid, uname, plan_key, method)
        security_log("PAYMENT_INITIATED", uid, f"plan={plan_key} method={method}")

        await query.edit_message_text(
            f"📋 <b>הוראות תשלום</b>\n\n"
            f"{details[method]}\n\n"
            f"✅ <b>לאחר התשלום:</b>\n"
            f"1. צלם את אישור התשלום\n"
            f"2. שלח את הצילום לבוט הזה\n"
            f"3. המנוי יאושר תוך 24 שעות\n\n"
            f"⚠️ ללא צילום מסך — לא יאושר\n\n"
            f"<i>⬡ Intelligence Room</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 שלחתי — ממתין לאישור", callback_data=f"sent_{plan_key}")],
                [InlineKeyboardButton("🔙 חזרה", callback_data="subscribe")],
            ])
        )

        await ctx.bot.send_message(
            chat_id=ADMIN_ID,
            text=(f"⏳ <b>תשלום ממתין לאישור</b>\n\n"
                  f"👤 @{uname} (ID: {uid})\n"
                  f"📋 {plan['name']} — ₪{plan['price']}\n"
                  f"💳 {method}\n"
                  f"🕐 {datetime.now().strftime('%d/%m %H:%M')}\n\n"
                  f"לאישור: /approve_{uid}\n"
                  f"לדחייה: /reject_{uid}\n"
                  f"לחסימה: /block_{uid}"),
            parse_mode="HTML"
        )
        return

    # ── אישור שליחה ──
    if data.startswith("sent_"):
        plan_key = data.replace("sent_", "")
        plan     = PRICES.get(plan_key, {})
        await query.edit_message_text(
            "⏳ <b>קיבלנו את הבקשה שלך!</b>\n\n"
            f"📋 תוכנית: <b>{plan.get('name','')}</b>\n"
            f"⏰ המנוי יאושר תוך 24 שעות\n\n"
            "תקבל הודעה כשהמנוי יופעל ✅\n\n"
            "<i>⬡ Intelligence Room</i>",
            parse_mode="HTML", reply_markup=back_menu()
        )
        return

    # ── חבר מביא חבר ──
    if data == "referral":
        db    = load_db()
        user  = db["users"].get(str(uid), {})
        code  = user.get("referral_code", f"REF{uid}")
        count = len(db["referrals"].get(str(uid), []))
        needed = 2 - (count % 2) if count % 2 != 0 else 2
        link  = f"https://t.me/{ctx.bot.username}?start={code}"
        await query.edit_message_text(
            f"👥 <b>חבר מביא חבר</b>\n\n"
            f"הקישור שלך:\n<code>{link}</code>\n\n"
            f"📊 חברים שצירפת: <b>{count}</b>\n"
            f"🎁 עוד <b>{needed}</b> חבר/ים לחודש חינם!\n\n"
            f"📋 <b>איך זה עובד:</b>\n"
            f"• שתף את הקישור עם חברים\n"
            f"• כל 2 חברים = חודש חינם!\n"
            f"• אין הגבלה על מספר ההפניות\n\n"
            f"<i>⬡ Intelligence Room</i>",
            parse_mode="HTML", reply_markup=back_menu()
        )
        return

    # ── פעולות שדורשות מנוי ──
    if not await check_access(update, ctx, callback=True):
        return

    loading = {
        "watchlist": "📊 <b>טוען מחירים...</b>",
        "signals":   "💹 <b>מחשב המלצות מסחר...</b>",
        "briefing":  "🌅 <b>מכין תדריך...</b>",
        "scan":      "🔍 <b>סורק שוק...</b>",
    }
    if data not in loading:
        return

    security_log("ACTION", uid, data)
    msg = await query.edit_message_text(loading[data], parse_mode="HTML")
    results = await scan_all()

    if data == "watchlist":
        text = build_watchlist(results)
    elif data == "signals":
        text = build_signals(results)
    elif data == "briefing":
        text = build_briefing(results)
    elif data == "scan":
        sent = 0
        for r in results:
            if r["sig"]["level"] == "HIGH":
                await ctx.bot.send_message(chat_id=chat_id,
                    text=build_alert(r["asset"],r["quote"],r["sig"]), parse_mode="HTML")
                sent += 1
                await asyncio.sleep(1)
        text = build_watchlist(results) + f"\n\n✅ סריקה הושלמה — {sent} התראות נשלחו"
    else:
        text = "❌ שגיאה"

    await ctx.bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg.message_id,
        text=text,
        parse_mode="HTML",
        reply_markup=action_menu(data)
    )

# ═══════════════════════════════════════════
# טיפול בהודעות (צילומי מסך)
# ═══════════════════════════════════════════
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.first_name or "משתמש"

    if is_blocked(uid) and not is_admin(uid):
        await update.message.reply_text("🚫 הגישה שלך נחסמה.")
        return

    db   = load_db()
    pend = db["pending"].get(str(uid))

    if update.message.photo and pend:
        plan = PRICES.get(pend["plan"], {})
        security_log("PAYMENT_SCREENSHOT", uid, f"plan={pend['plan']}")
        await ctx.bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
        await ctx.bot.send_message(
            chat_id=ADMIN_ID,
            text=(f"📸 <b>אישור תשלום התקבל!</b>\n\n"
                  f"👤 @{uname} (ID: {uid})\n"
                  f"📋 {plan.get('name','?')} — ₪{plan.get('price','?')}\n"
                  f"💳 {pend.get('method','?')}\n"
                  f"🕐 {datetime.now().strftime('%d/%m %H:%M')}\n\n"
                  f"✅ לאישור: /approve_{uid}\n"
                  f"❌ לדחייה: /reject_{uid}\n"
                  f"🚫 לחסימה: /block_{uid}"),
            parse_mode="HTML"
        )
        await update.message.reply_text(
            "✅ <b>צילום המסך התקבל!</b>\n\n"
            "⏰ המנוי יאושר תוך 24 שעות\n"
            "תקבל הודעה כשיופעל ✅\n\n"
            "<i>⬡ Intelligence Room</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 תפריט", callback_data="menu")]])
        )
    elif update.message.photo and not pend:
        await update.message.reply_text(
            "תמונה התקבלה, אך אין בקשת תשלום פעילה.\n"
            "שלח /start ובחר תוכנית מנוי.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 תפריט", callback_data="menu")]])
        )
    elif update.message.text:
        await update.message.reply_text(
            "שלח /start לפתיחת התפריט ⬡",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 פתח תפריט", callback_data="menu")]])
        )

# ═══════════════════════════════════════════
# סריקה אוטומטית
# ═══════════════════════════════════════════
async def auto_scan_loop(app):
    await asyncio.sleep(90)
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M')}] 🔄 סריקה אוטומטית...")
            results = await scan_all()
            db      = load_db()
            active  = [u for u in db["users"].values()
                       if u.get("expiry") and datetime.fromisoformat(u["expiry"]) > datetime.now()]
            active.append({"user_id": ADMIN_ID})

            for r in results:
                if r["sig"]["level"] == "HIGH":
                    alert = build_alert(r["asset"], r["quote"], r["sig"])
                    for user in active:
                        try:
                            await app.bot.send_message(
                                chat_id=user["user_id"],
                                text=alert, parse_mode="HTML"
                            )
                            await asyncio.sleep(0.3)
                        except: pass

            print(f"✅ {len(results)} נכסים → {len(active)} מנויים")
        except Exception as e:
            print(f"❌ שגיאה: {e}")
        await asyncio.sleep(30 * 60)

# ═══════════════════════════════════════════
# הפעלה
# ═══════════════════════════════════════════
def main():
    print("🚀 מפעיל Intelligence Room Bot...")
    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("admin",  cmd_admin))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_"), cmd_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_"),  cmd_reject))
    app.add_handler(MessageHandler(filters.Regex(r"^/block_"),   cmd_block))
    app.add_handler(MessageHandler(filters.Regex(r"^/unblock_"), cmd_unblock))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    async def post_init(application):
        await application.bot.send_message(
            chat_id=ADMIN_ID,
            text=("⬡ <b>Intelligence Room הופעל!</b>\n\n"
                  "✅ מנויים · 👥 הפניות · 🔒 אבטחה\n"
                  "📡 Yahoo Finance · ⏱ כל 30 דקות\n\n"
                  "/admin — לוח בקרה\n"
                  "/block_ID — חסום משתמש\n"
                  "/unblock_ID — שחרר חסימה"),
            parse_mode="HTML"
        )
        asyncio.create_task(auto_scan_loop(application))

    app.post_init = post_init
    print("✅ הבוט פועל!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
