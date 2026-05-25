"""
Intelligence Room Bot — Production Ready
Railway + python-telegram-bot v20+
"""

import os
import asyncio
import aiohttp
import json
import secrets
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ═══════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# CONFIG — כל הערכים מ-ENV בלבד, ללא hardcode
# ═══════════════════════════════════════════════════════
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
ADMIN_ID = None  # ייטען ב-startup_diagnostics

PAYMENT_INFO = {
    "bit":    "050-XXXXXXX",   # עדכן מספר ביט
    "paybox": "050-XXXXXXX",   # עדכן מספר פייבוקס
    "bank": (
        "🏦 בנק הבינלאומי הראשון לישראל\n"
        "סניף: 062 — קרית גת\n"
        "חשבון: 259794\n"
        "זיהוי: 034653667"
    ),
}

PRICES = {
    "trial":   {"name": "ניסיון חינמי", "price": 0,    "days": 3},
    "monthly": {"name": "מנוי חודשי",   "price": 300,  "days": 30},
    "yearly":  {"name": "מנוי שנתי",    "price": 3000, "days": 365},
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

# ═══════════════════════════════════════════════════════
# STARTUP DIAGNOSTICS
# ═══════════════════════════════════════════════════════
def startup_diagnostics():
    global ADMIN_ID

    log.info("=" * 50)
    log.info("Intelligence Room Bot — Startup Diagnostics")
    log.info("=" * 50)

    # טעינת ADMIN_ID מ-ENV
    raw = os.environ.get("ADMIN_ID", "").strip()
    if not raw:
        log.error("❌ ADMIN_ID לא הוגדר ב-Railway Variables!")
    else:
        try:
            ADMIN_ID = int(raw)
            log.info(f"✅ ADMIN_ID נטען: {ADMIN_ID}")
        except ValueError:
            log.error(f"❌ ADMIN_ID לא תקין: '{raw}' — חייב להיות מספר!")
            ADMIN_ID = None

    # בדיקת TG_TOKEN
    if not TG_TOKEN:
        log.error("❌ TG_TOKEN לא הוגדר!")
    else:
        log.info(f"✅ TG_TOKEN נטען: {TG_TOKEN[:10]}...")

    log.info(f"✅ נכסים: {len(ASSETS)}")
    log.info(f"✅ תוכניות: {list(PRICES.keys())}")
    log.info("=" * 50)

    return bool(TG_TOKEN and ADMIN_ID)

# ═══════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════
DB_FILE      = "users.json"
BLOCKED_FILE = "blocked.json"

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"DB save error [{path}]: {e}")

def load_db():
    return _load(DB_FILE, {"users": {}, "pending": {}, "referrals": {}})

def save_db(db):
    _save(DB_FILE, db)

def load_blocked():
    return _load(BLOCKED_FILE, {"blocked": [], "attempts": {}})

def save_blocked(b):
    _save(BLOCKED_FILE, b)

# ═══════════════════════════════════════════════════════
# AUTH — שכבת הרשאות נקייה
# ═══════════════════════════════════════════════════════
def is_admin(user_id: int) -> bool:
    """בדיקה האם המשתמש הוא האדמין — FULL BYPASS"""
    if ADMIN_ID is None:
        log.warning("is_admin: ADMIN_ID לא הוגדר!")
        return False
    result = int(user_id) == int(ADMIN_ID)
    if result:
        log.info(f"✅ ADMIN ACCESS: {user_id}")
    return result

def is_blocked(user_id: int) -> bool:
    if is_admin(user_id):
        return False  # אדמין לעולם לא חסום
    bl = load_blocked()
    return str(user_id) in bl.get("blocked", [])

def has_active_sub(user_id: int) -> bool:
    """בדיקת מנוי פעיל — אדמין תמיד מקבל True"""
    if is_admin(user_id):
        return True  # ADMIN BYPASS
    db   = load_db()
    user = db["users"].get(str(user_id))
    if not user or not user.get("expiry"):
        return False
    try:
        return datetime.fromisoformat(user["expiry"]) > datetime.now()
    except:
        return False

def record_attempt(user_id: int):
    bl  = load_blocked()
    uid = str(user_id)
    bl.setdefault("attempts", {})[uid] = bl["attempts"].get(uid, 0) + 1
    if bl["attempts"][uid] >= 5:
        if uid not in bl.get("blocked", []):
            bl.setdefault("blocked", []).append(uid)
            log.warning(f"AUTO-BLOCK: {user_id} (5 attempts)")
    save_blocked(bl)

# ═══════════════════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════════════════
def ensure_user(user_id: int, username: str):
    db  = load_db()
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "user_id":        user_id,
            "username":       username,
            "plan":           None,
            "expiry":         None,
            "joined":         datetime.now().isoformat(),
            "trial_used":     False,
            "referrals_count": 0,
            "referral_code":  f"REF{user_id}",
        }
        save_db(db)
        log.info(f"NEW USER: {user_id} @{username}")
    return db["users"][uid]

def get_expiry_str(user_id) -> str:
    if is_admin(user_id):
        return "∞ אדמין — גישה מלאה"
    db   = load_db()
    user = db["users"].get(str(user_id))
    if not user or not user.get("expiry"):
        return "אין מנוי"
    try:
        exp  = datetime.fromisoformat(user["expiry"])
        days = max(0, (exp - datetime.now()).days)
        return f"{exp.strftime('%d/%m/%Y')} ({days} ימים)"
    except:
        return "שגיאה"

def is_trial_used(user_id: int) -> bool:
    db   = load_db()
    user = db["users"].get(str(user_id), {})
    return user.get("trial_used", False)

def add_subscription(user_id: int, username: str, plan_key: str, days: int):
    db  = load_db()
    uid = str(user_id)
    now = datetime.now()
    usr = db["users"].get(uid, {})

    cur  = usr.get("expiry")
    base = now
    if cur:
        try:
            parsed = datetime.fromisoformat(cur)
            if parsed > now:
                base = parsed
        except:
            pass

    exp = base + timedelta(days=days)
    db["users"][uid] = {
        **usr,
        "user_id":    user_id,
        "username":   username or usr.get("username", ""),
        "plan":       plan_key,
        "expiry":     exp.isoformat(),
        "trial_used": True if plan_key == "trial" else usr.get("trial_used", False),
        "approved_at": now.isoformat(),
    }
    save_db(db)
    log.info(f"SUB ADDED: {user_id} plan={plan_key} until={exp.strftime('%d/%m/%Y')}")

def add_pending(user_id: int, username: str, plan_key: str, method: str):
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

def add_referral(referrer_id, new_user_id) -> int:
    db  = load_db()
    rid = str(referrer_id)
    db.setdefault("referrals", {})
    db["referrals"].setdefault(rid, [])
    if str(new_user_id) not in db["referrals"][rid]:
        db["referrals"][rid].append(str(new_user_id))
        count = len(db["referrals"][rid])
        usr   = db["users"].get(rid, {})
        db["users"][rid] = {**usr, "referrals_count": count}
        save_db(db)
        return count
    return len(db["referrals"].get(rid, []))

# ═══════════════════════════════════════════════════════
# MARKET DATA — Yahoo Finance
# ═══════════════════════════════════════════════════════
_last_quotes: dict = {}

async def fetch_quote(session: aiohttp.ClientSession, symbol: str) -> dict | None:
    url     = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    params  = {"interval": "1d", "range": "5d"}
    try:
        async with session.get(url, headers=headers, params=params,
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            d      = await r.json(content_type=None)
            result = d["chart"]["result"][0]
            meta   = result["meta"]
            closes = [c for c in
                      result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                      if c is not None]

            price   = float(meta.get("regularMarketPrice", 0))
            prev    = float(meta.get("chartPreviousClose", price) or price)
            chg_pct = round((price - prev) / prev * 100, 2) if prev else 0.0
            high_5d = max(closes[-5:]) if len(closes) >= 5 else price * 1.05
            low_5d  = min(closes[-5:]) if len(closes) >= 5 else price * 0.95

            return {
                "price":     price,
                "changePct": chg_pct,
                "volume":    int(meta.get("regularMarketVolume", 0)),
                "prev":      prev,
                "high_5d":   round(high_5d, 2),
                "low_5d":    round(low_5d,  2),
            }
    except Exception as e:
        log.warning(f"fetch_quote [{symbol}]: {e}")
        return None

async def scan_all() -> list:
    global _last_quotes
    results = []
    async with aiohttp.ClientSession() as session:
        qs = await asyncio.gather(*[fetch_quote(session, a["s"]) for a in ASSETS])
    for asset, q in zip(ASSETS, qs):
        if q:
            _last_quotes[asset["s"]] = q
        elif asset["s"] in _last_quotes:
            q = _last_quotes[asset["s"]]
            log.info(f"Using cached quote for {asset['s']}")
        if q:
            results.append({"asset": asset, "quote": q, "sig": get_signal(q)})
    log.info(f"scan_all: {len(results)}/{len(ASSETS)} assets")
    return results

# ═══════════════════════════════════════════════════════
# SIGNAL ENGINE
# ═══════════════════════════════════════════════════════
def get_signal(q: dict) -> dict:
    chg = q["changePct"]
    p   = q["price"]
    h5  = q["high_5d"]
    l5  = q["low_5d"]
    rng = max(h5 - l5, p * 0.01)

    if chg > 4:
        return dict(action="BUY",       conf=min(90, 70+chg*2), emoji="🚀",
                    reason="פריצת מומנטום חזקה",   level="HIGH",
                    entry=round(p,2), target=round(p*1.08,2), stop=round(p*0.96,2))
    if chg > 2:
        return dict(action="BUY",       conf=65, emoji="📈",
                    reason="מומנטום חיובי",         level="HIGH",
                    entry=round(p,2), target=round(p*1.05,2), stop=round(p*0.97,2))
    if chg > 0.5:
        return dict(action="WATCH",     conf=55, emoji="✅",
                    reason="עלייה מתונה — המתן",   level="MED",
                    entry=round(l5+rng*0.3,2), target=round(h5,2), stop=round(l5*0.98,2))
    if chg < -4:
        return dict(action="SELL/SHORT",conf=min(90, 70+abs(chg)*2), emoji="🔴",
                    reason="ירידה חדה — סכנה",     level="HIGH",
                    entry=round(p,2), target=round(p*0.92,2), stop=round(p*1.04,2))
    if chg < -2:
        return dict(action="CAUTION",   conf=60, emoji="⚠️",
                    reason="לחץ מוכרים — המתן",    level="HIGH",
                    entry=round(l5,2), target=round(p*0.97,2), stop=round(p*1.03,2))
    return     dict(action="NEUTRAL",   conf=45, emoji="⬜",
                    reason="אין כיוון ברור",        level="LOW",
                    entry=round(l5+rng*0.4,2), target=round(h5*0.99,2), stop=round(l5*0.97,2))

def fp(asset: dict, price: float) -> str:
    return f"${price:,.2f}" if (asset["t"] == "crypto" or price > 1000) else f"${price:.2f}"

def fc(chg: float) -> str:
    return f"{'+' if chg >= 0 else ''}{chg:.2f}%"

# ═══════════════════════════════════════════════════════
# MESSAGE BUILDERS
# ═══════════════════════════════════════════════════════
def build_watchlist(results: list) -> str:
    if not results:
        return "❌ <b>אין נתונים זמינים</b>\n\nנסה שוב עוד כמה דקות."
    t     = datetime.now().strftime("%H:%M:%S")
    lines = [f"📊 <b>WATCHLIST — Intelligence Room</b>\n🕐 {t}\n"]
    for r in results:
        a, q, s = r["asset"], r["quote"], r["sig"]
        lines.append(
            f"{s['emoji']} <b>{a['s']}</b>  {fp(a, q['price'])}  <b>{fc(q['changePct'])}</b>\n"
            f"    └ {s['action']} · {int(s['conf'])}% ביטחון"
        )
    lines.append("\n📡 Yahoo Finance · <i>⬡ Intelligence Room</i>")
    return "\n".join(lines)

def build_signals(results: list) -> str:
    if not results:
        return "❌ אין נתונים."
    buys    = [r for r in results if r["sig"]["action"] == "BUY"]
    sells   = [r for r in results if "SELL" in r["sig"]["action"]]
    caution = [r for r in results if r["sig"]["action"] == "CAUTION"]
    watch   = [r for r in results if r["sig"]["action"] in ("WATCH", "NEUTRAL")]
    t   = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg = f"💹 <b>המלצות מסחר — Intelligence Room</b>\n📅 {t}\n{'━'*20}\n\n"

    if buys:
        msg += "🟢 <b>קנייה — BUY</b>\n\n"
        for r in buys:
            a, q, s = r["asset"], r["quote"], r["sig"]
            msg += (f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                    f"💰 {fp(a,q['price'])} ({fc(q['changePct'])})\n"
                    f"📥 כניסה: <b>{fp(a,s['entry'])}</b>\n"
                    f"🎯 יעד:   <b>{fp(a,s['target'])}</b>\n"
                    f"🛑 סטופ:  <b>{fp(a,s['stop'])}</b>\n"
                    f"📊 {int(s['conf'])}% · {s['reason']}\n\n")
    if sells:
        msg += "🔴 <b>מכירה — SELL</b>\n\n"
        for r in sells:
            a, q, s = r["asset"], r["quote"], r["sig"]
            msg += (f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                    f"💰 {fp(a,q['price'])} ({fc(q['changePct'])})\n"
                    f"📤 כניסה שורט: <b>{fp(a,s['entry'])}</b>\n"
                    f"🎯 יעד:        <b>{fp(a,s['target'])}</b>\n"
                    f"🛑 סטופ:       <b>{fp(a,s['stop'])}</b>\n"
                    f"📊 {int(s['conf'])}% · {s['reason']}\n\n")
    if caution:
        msg += "⚠️ <b>זהירות:</b>\n"
        for r in caution:
            a, q, s = r["asset"], r["quote"], r["sig"]
            msg += f"• <b>{a['s']}</b> {fp(a,q['price'])} ({fc(q['changePct'])}) — {s['reason']}\n"
        msg += "\n"
    if watch:
        msg += "⬜ <b>המתנה:</b>\n"
        for r in watch:
            a, q = r["asset"], r["quote"]
            msg += f"• <b>{a['s']}</b> {fp(a,q['price'])} ({fc(q['changePct'])})\n"
        msg += "\n"

    msg += (f"{'━'*20}\n"
            f"📊 {len(buys)} קנייה · {len(sells)} מכירה · {len(caution)} זהירות\n"
            f"⚠️ <i>זו אינה המלצת השקעה. סחר באחריותך.</i>\n"
            f"<i>⬡ Intelligence Room</i>")
    return msg

def build_briefing(results: list) -> str:
    t   = datetime.now().strftime("%d/%m/%Y %H:%M")
    ups = [r for r in results if r["quote"]["changePct"] > 1]
    dns = [r for r in results if r["quote"]["changePct"] < -1]
    msg = f"🌅 <b>תדריך — Intelligence Room</b>\n📅 {t}\n\n"
    if ups:
        msg += "🚀 <b>עולים:</b>\n"
        for r in ups:
            msg += f"• <b>{r['asset']['s']}</b>: {fp(r['asset'],r['quote']['price'])} ({fc(r['quote']['changePct'])})\n"
        msg += "\n"
    if dns:
        msg += "⚠️ <b>יורדים:</b>\n"
        for r in dns:
            msg += f"• <b>{r['asset']['s']}</b>: {fp(r['asset'],r['quote']['price'])} ({fc(r['quote']['changePct'])})\n"
        msg += "\n"
    if not ups and not dns:
        msg += "📊 השוק רגוע — אין תנועות משמעותיות\n\n"
    msg += f"📊 {len(results)} נכסים · {len(ups)} עולים · {len(dns)} יורדים\n<i>⬡ Intelligence Room</i>"
    return msg

def build_alert(asset: dict, q: dict, sig: dict) -> str:
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

# ═══════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Watchlist",        callback_data="watchlist"),
         InlineKeyboardButton("💹 קנייה/מכירה",      callback_data="signals")],
        [InlineKeyboardButton("🌅 תדריך בוקר",       callback_data="briefing"),
         InlineKeyboardButton("🔍 סריקה + התראות",   callback_data="scan")],
        [InlineKeyboardButton("👑 מנויים",            callback_data="subscribe"),
         InlineKeyboardButton("👥 חבר מביא חבר",     callback_data="referral")],
        [InlineKeyboardButton("ℹ️ עזרה",              callback_data="help")],
    ])

def kb_sub():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 ניסיון חינמי — 3 ימים", callback_data="plan_trial")],
        [InlineKeyboardButton("📅 מנוי חודשי — ₪300",      callback_data="plan_monthly")],
        [InlineKeyboardButton("🏆 מנוי שנתי — ₪3,000",     callback_data="plan_yearly")],
        [InlineKeyboardButton("🔙 חזרה",                    callback_data="menu")],
    ])

def kb_pay(plan_key: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ביט",           callback_data=f"pay_bit_{plan_key}")],
        [InlineKeyboardButton("💳 פייבוקס",       callback_data=f"pay_paybox_{plan_key}")],
        [InlineKeyboardButton("🏦 העברה בנקאית", callback_data=f"pay_bank_{plan_key}")],
        [InlineKeyboardButton("🔙 חזרה",          callback_data="subscribe")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 תפריט ראשי", callback_data="menu")]])

def kb_action(action: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 רענן",     callback_data=action),
         InlineKeyboardButton("🔙 תפריט",   callback_data="menu")]
    ])

def kb_no_sub():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 הצטרף עכשיו", callback_data="subscribe")],
        [InlineKeyboardButton("🔙 תפריט",       callback_data="menu")],
    ])

# ═══════════════════════════════════════════════════════
# ACCESS GUARD
# ═══════════════════════════════════════════════════════
async def guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE, is_callback=False) -> bool:
    """
    מחזיר True אם למשתמש יש גישה.
    אדמין תמיד מקבל True ללא בדיקות נוספות.
    """
    uid = update.effective_user.id

    # ADMIN FULL BYPASS
    if is_admin(uid):
        return True

    # חסום?
    if is_blocked(uid):
        msg = "🚫 הגישה שלך נחסמה. פנה לתמיכה."
        if is_callback:
            await update.callback_query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return False

    # מנוי?
    if has_active_sub(uid):
        return True

    # אין מנוי
    no_sub_msg = ("🔒 <b>תוכן זה זמין למנויים בלבד</b>\n\n"
                  "הצטרף ל-Intelligence Room:\n"
                  "🆓 ניסיון חינמי 3 ימים\n"
                  "📅 מנוי חודשי ₪300\n"
                  "🏆 מנוי שנתי ₪3,000")
    if is_callback:
        await update.callback_query.edit_message_text(
            no_sub_msg, parse_mode="HTML", reply_markup=kb_no_sub())
    else:
        await update.message.reply_text(
            no_sub_msg, parse_mode="HTML", reply_markup=kb_no_sub())
    return False

# ═══════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.first_name or "משתמש"

    if is_blocked(uid) and not is_admin(uid):
        await update.message.reply_text("🚫 הגישה שלך נחסמה.")
        return

    # טיפול בהפניה
    if ctx.args and ctx.args[0].startswith("REF"):
        referrer_id = ctx.args[0][3:]
        if str(referrer_id) != str(uid):
            count = add_referral(referrer_id, uid)
            if count > 0 and count % 2 == 0:
                add_subscription(int(referrer_id), "", "monthly", 30)
                try:
                    await ctx.bot.send_message(
                        chat_id=int(referrer_id),
                        text=(f"🎉 <b>מזל טוב!</b>\n\n"
                              f"צירפת 2 חברים — קיבלת חודש חינם!\n"
                              f"תוקף: {get_expiry_str(referrer_id)}\n\n"
                              f"<i>⬡ Intelligence Room</i>"),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    log.warning(f"referral notify failed: {e}")

    ensure_user(uid, uname)

    admin_badge = " 👑 אדמין" if is_admin(uid) else ""
    sub_status  = f"✅ מנוי פעיל: {get_expiry_str(uid)}" if has_active_sub(uid) else "❌ אין מנוי פעיל"

    await update.message.reply_text(
        f"⬡ <b>Intelligence Room</b>{admin_badge}\n\n"
        f"ברוך הבא! 👋\n"
        f"{sub_status}\n\n"
        f"בחר פעולה:",
        parse_mode="HTML",
        reply_markup=kb_main()
    )

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        record_attempt(uid)
        await update.message.reply_text("🚫 אין הרשאה.")
        return

    db     = load_db()
    users  = db["users"]
    pend   = db["pending"]
    now    = datetime.now()
    active = [u for u in users.values()
              if u.get("expiry") and datetime.fromisoformat(u["expiry"]) > now]

    msg = (f"👑 <b>לוח בקרה — מנהל</b>\n\n"
           f"👥 משתמשים: {len(users)}\n"
           f"✅ מנויים פעילים: {len(active)}\n"
           f"⏳ ממתינים: {len(pend)}\n\n")

    if pend:
        msg += "⏳ <b>ממתינים לאישור:</b>\n\n"
        for uid_p, p in pend.items():
            plan = PRICES.get(p["plan"], {})
            t    = datetime.fromisoformat(p["time"]).strftime("%d/%m %H:%M")
            msg += (f"👤 @{p.get('username','?')} (ID:{uid_p})\n"
                    f"📋 {plan.get('name','?')} — ₪{plan.get('price',0)} · {p.get('method','?')} · {t}\n"
                    f"✅ /approve_{uid_p}   ❌ /reject_{uid_p}   🚫 /block_{uid_p}\n\n")

    if active:
        msg += "✅ <b>מנויים פעילים (10 אחרונים):</b>\n"
        for u in list(active)[-10:]:
            exp = datetime.fromisoformat(u["expiry"]).strftime("%d/%m/%Y")
            msg += f"• @{u.get('username','?')} — {u.get('plan','?')} עד {exp}\n"

    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid_str = update.message.text.replace("/approve_", "").strip()
    db      = load_db()
    pend    = db["pending"].get(uid_str)
    if not pend:
        await update.message.reply_text("❌ לא נמצא.")
        return
    plan = PRICES[pend["plan"]]
    add_subscription(int(uid_str), pend.get("username",""), pend["plan"], plan["days"])
    remove_pending(uid_str)
    await update.message.reply_text(f"✅ אושר! @{pend.get('username','?')} — {plan['name']}")
    try:
        await ctx.bot.send_message(
            chat_id=int(uid_str),
            text=(f"✅ <b>המנוי שלך אושר!</b>\n\n"
                  f"תוכנית: <b>{plan['name']}</b>\n"
                  f"תוקף: <b>{get_expiry_str(uid_str)}</b>\n\n"
                  f"שלח /start להתחלה 🚀\n<i>⬡ Intelligence Room</i>"),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 פתח תפריט", callback_data="menu")]])
        )
    except Exception as e:
        log.warning(f"approve notify failed: {e}")

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid_str = update.message.text.replace("/reject_", "").strip()
    db      = load_db()
    pend    = db["pending"].get(uid_str)
    if not pend:
        await update.message.reply_text("❌ לא נמצא.")
        return
    remove_pending(uid_str)
    await update.message.reply_text(f"❌ נדחה — @{pend.get('username','?')}")
    try:
        await ctx.bot.send_message(
            chat_id=int(uid_str),
            text=("❌ <b>התשלום לא אושר</b>\n\n"
                  "שלח צילום מסך ברור ונסה שוב.\n<i>⬡ Intelligence Room</i>"),
            parse_mode="HTML",
            reply_markup=kb_no_sub()
        )
    except Exception as e:
        log.warning(f"reject notify failed: {e}")

async def cmd_block(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid_str = update.message.text.replace("/block_", "").strip()
    bl      = load_blocked()
    bl.setdefault("blocked", [])
    if uid_str not in bl["blocked"]:
        bl["blocked"].append(uid_str)
        save_blocked(bl)
        await update.message.reply_text(f"🚫 {uid_str} נחסם.")
    else:
        await update.message.reply_text(f"⚠️ {uid_str} כבר חסום.")

async def cmd_unblock(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    uid_str = update.message.text.replace("/unblock_", "").strip()
    bl      = load_blocked()
    if uid_str in bl.get("blocked", []):
        bl["blocked"].remove(uid_str)
        save_blocked(bl)
        await update.message.reply_text(f"✅ {uid_str} שוחרר.")
    else:
        await update.message.reply_text(f"⚠️ {uid_str} לא חסום.")

# ═══════════════════════════════════════════════════════
# CALLBACK HANDLER
# ═══════════════════════════════════════════════════════
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query
    await q.answer()
    uid   = q.from_user.id
    uname = q.from_user.username or q.from_user.first_name or "משתמש"
    cid   = q.message.chat_id
    data  = q.data

    # חסום? (אדמין אף פעם לא חסום)
    if is_blocked(uid) and not is_admin(uid):
        await q.answer("🚫 הגישה שלך נחסמה.", show_alert=True)
        return

    # ── תפריט ──
    if data == "menu":
        sub    = has_active_sub(uid)
        badge  = " 👑" if is_admin(uid) else ""
        status = f"✅ מנוי פעיל: {get_expiry_str(uid)}" if sub else "❌ אין מנוי"
        await q.edit_message_text(
            f"⬡ <b>Intelligence Room</b>{badge}\n\n{status}\n\nבחר פעולה:",
            parse_mode="HTML", reply_markup=kb_main()
        )
        return

    # ── עזרה ──
    if data == "help":
        await q.edit_message_text(
            "⬡ <b>פקודות:</b>\n\n"
            "/start — תפריט ראשי\n"
            "/watchlist — מחירים\n"
            "/signals — קנייה/מכירה\n"
            "/briefing — תדריך\n"
            "/scan — סריקה\n\n"
            "⚠️ <i>זו אינה המלצת השקעה.</i>",
            parse_mode="HTML", reply_markup=kb_back()
        )
        return

    # ── מנויים ──
    if data == "subscribe":
        sub = has_active_sub(uid)
        txt = (f"✅ <b>מנוי פעיל!</b>\n\nתוקף: {get_expiry_str(uid)}\n\nרוצה לחדש?"
               if sub else
               "👑 <b>Intelligence Room — מנויים</b>\n\n"
               "🆓 ניסיון חינמי — 3 ימים\n"
               "📅 מנוי חודשי — ₪300\n"
               "🏆 מנוי שנתי — ₪3,000 (חסכון ₪600)\n\n"
               "בחר תוכנית:")
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb_sub())
        return

    # ── בחירת תוכנית ──
    if data.startswith("plan_"):
        plan_key = data[5:]
        plan     = PRICES.get(plan_key)
        if not plan:
            return
        if plan_key == "trial":
            if is_trial_used(uid):
                await q.edit_message_text(
                    "❌ <b>כבר השתמשת בניסיון</b>\n\nשדרג למנוי:",
                    parse_mode="HTML", reply_markup=kb_sub()
                )
                return
            add_subscription(uid, uname, "trial", 3)
            try:
                await ctx.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🆓 ניסיון חינמי: @{uname} (ID:{uid})"
                )
            except: pass
            await q.edit_message_text(
                f"🎉 <b>הניסיון הופעל!</b>\n\n✅ תוקף: {get_expiry_str(uid)}\n\n<i>⬡ Intelligence Room</i>",
                parse_mode="HTML", reply_markup=kb_back()
            )
            return
        await q.edit_message_text(
            f"💳 <b>{plan['name']} — ₪{plan['price']}</b>\n\nבחר אמצעי תשלום:",
            parse_mode="HTML", reply_markup=kb_pay(plan_key)
        )
        return

    # ── תשלום ──
    if data.startswith("pay_"):
        parts    = data.split("_", 2)
        method   = parts[1]
        plan_key = parts[2]
        plan     = PRICES.get(plan_key)
        if not plan:
            return
        details = {
            "bit":    f"💳 <b>ביט</b>\nשלח ₪{plan['price']} ל:\n<b>{PAYMENT_INFO['bit']}</b>",
            "paybox": f"💳 <b>פייבוקס</b>\nשלח ₪{plan['price']} ל:\n<b>{PAYMENT_INFO['paybox']}</b>",
            "bank":   f"🏦 <b>העברה בנקאית</b>\n\n{PAYMENT_INFO['bank']}\n\nסכום: <b>₪{plan['price']}</b>",
        }
        add_pending(uid, uname, plan_key, method)
        await q.edit_message_text(
            f"📋 <b>הוראות תשלום</b>\n\n{details[method]}\n\n"
            f"✅ לאחר התשלום:\n1. צלם אישור תשלום\n2. שלח לבוט\n3. אישור תוך 24 שעות\n\n"
            f"<i>⬡ Intelligence Room</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 שלחתי — ממתין לאישור", callback_data=f"sent_{plan_key}")],
                [InlineKeyboardButton("🔙 חזרה", callback_data="subscribe")],
            ])
        )
        try:
            await ctx.bot.send_message(
                chat_id=ADMIN_ID,
                text=(f"⏳ <b>תשלום ממתין</b>\n\n"
                      f"@{uname} (ID:{uid})\n"
                      f"{plan['name']} — ₪{plan['price']} · {method}\n\n"
                      f"✅ /approve_{uid}\n❌ /reject_{uid}\n🚫 /block_{uid}"),
                parse_mode="HTML"
            )
        except Exception as e:
            log.warning(f"admin notify failed: {e}")
        return

    # ── אישור שליחה ──
    if data.startswith("sent_"):
        plan = PRICES.get(data[5:], {})
        await q.edit_message_text(
            f"⏳ <b>הבקשה התקבלה!</b>\n\n📋 {plan.get('name','')}\n⏰ אישור תוך 24 שעות\n\n<i>⬡ Intelligence Room</i>",
            parse_mode="HTML", reply_markup=kb_back()
        )
        return

    # ── חבר מביא חבר ──
    if data == "referral":
        db    = load_db()
        user  = db["users"].get(str(uid), {})
        code  = user.get("referral_code", f"REF{uid}")
        count = len(db.get("referrals", {}).get(str(uid), []))
        need  = 2 - (count % 2) if count % 2 != 0 else 2
        link  = f"https://t.me/{ctx.bot.username}?start={code}"
        await q.edit_message_text(
            f"👥 <b>חבר מביא חבר</b>\n\n"
            f"הקישור שלך:\n<code>{link}</code>\n\n"
            f"📊 צירפת: <b>{count}</b> חברים\n"
            f"🎁 עוד <b>{need}</b> לחודש חינם!\n\n"
            f"כל 2 חברים = חודש חינם!\n\n"
            f"<i>⬡ Intelligence Room</i>",
            parse_mode="HTML", reply_markup=kb_back()
        )
        return

    # ── פעולות שוק — דורשות גישה ──
    market_actions = {"watchlist", "signals", "briefing", "scan"}
    if data in market_actions:
        if not await guard(update, ctx, is_callback=True):
            return

        loading = {
            "watchlist": "📊 <b>טוען מחירים...</b>",
            "signals":   "💹 <b>מחשב המלצות...</b>",
            "briefing":  "🌅 <b>מכין תדריך...</b>",
            "scan":      "🔍 <b>סורק שוק...</b>",
        }
        loading_msg = await q.edit_message_text(loading[data], parse_mode="HTML")
        results     = await scan_all()

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
                    try:
                        await ctx.bot.send_message(
                            chat_id=cid,
                            text=build_alert(r["asset"], r["quote"], r["sig"]),
                            parse_mode="HTML"
                        )
                        sent += 1
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        log.warning(f"alert send failed: {e}")
            text = build_watchlist(results) + f"\n\n✅ סריקה הושלמה — {sent} התראות"
        else:
            text = "❌ שגיאה"

        try:
            await ctx.bot.edit_message_text(
                chat_id=cid,
                message_id=loading_msg.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=kb_action(data)
            )
        except Exception as e:
            log.error(f"edit_message_text failed: {e}")
        return

    log.warning(f"Unknown callback: {data} from {uid}")

# ═══════════════════════════════════════════════════════
# MESSAGE HANDLER — צילומי מסך + הודעות כלליות
# ═══════════════════════════════════════════════════════
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.first_name or "משתמש"

    if is_blocked(uid) and not is_admin(uid):
        await update.message.reply_text("🚫 הגישה שלך נחסמה.")
        return

    db   = load_db()
    pend = db["pending"].get(str(uid))

    if update.message.photo:
        if pend:
            plan = PRICES.get(pend["plan"], {})
            try:
                await ctx.bot.forward_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
                await ctx.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(f"📸 <b>אישור תשלום</b>\n\n"
                          f"@{uname} (ID:{uid})\n"
                          f"{plan.get('name','?')} — ₪{plan.get('price','?')} · {pend.get('method','?')}\n\n"
                          f"✅ /approve_{uid}\n❌ /reject_{uid}\n🚫 /block_{uid}"),
                    parse_mode="HTML"
                )
            except Exception as e:
                log.warning(f"forward failed: {e}")
            await update.message.reply_text(
                "✅ <b>צילום התקבל!</b>\n\n⏰ אישור תוך 24 שעות\n\n<i>⬡ Intelligence Room</i>",
                parse_mode="HTML", reply_markup=kb_back()
            )
        else:
            await update.message.reply_text(
                "📸 תמונה התקבלה, אך אין בקשת תשלום פעילה.\nשלח /start ובחר תוכנית.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 תפריט", callback_data="menu")]])
            )
    else:
        await update.message.reply_text(
            "שלח /start לפתיחת התפריט ⬡",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 פתח תפריט", callback_data="menu")]])
        )

# ═══════════════════════════════════════════════════════
# AUTO SCAN LOOP
# ═══════════════════════════════════════════════════════
async def auto_scan_loop(app: Application):
    await asyncio.sleep(120)  # המתן 2 דקות לאחר הפעלה
    while True:
        try:
            log.info("🔄 Auto scan starting...")
            results = await scan_all()
            db      = load_db()
            now     = datetime.now()

            # בנה רשימת נמענים: כל המנויים הפעילים + אדמין
            recipients = set()
            if ADMIN_ID:
                recipients.add(ADMIN_ID)
            for u in db["users"].values():
                try:
                    if u.get("expiry") and datetime.fromisoformat(u["expiry"]) > now:
                        recipients.add(int(u["user_id"]))
                except:
                    pass

            high_results = [r for r in results if r["sig"]["level"] == "HIGH"]
            log.info(f"Auto scan: {len(results)} assets, {len(high_results)} HIGH, {len(recipients)} recipients")

            for r in high_results:
                alert = build_alert(r["asset"], r["quote"], r["sig"])
                for chat_id in recipients:
                    try:
                        await app.bot.send_message(
                            chat_id=chat_id,
                            text=alert,
                            parse_mode="HTML"
                        )
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        log.warning(f"auto alert to {chat_id} failed: {e}")

        except Exception as e:
            log.error(f"auto_scan_loop error: {e}")

        await asyncio.sleep(30 * 60)  # כל 30 דקות

# ═══════════════════════════════════════════════════════
# POST INIT
# ═══════════════════════════════════════════════════════
async def post_init(application: Application):
    log.info("post_init called")
    if ADMIN_ID:
        try:
            await application.bot.send_message(
                chat_id=ADMIN_ID,
                text=(f"⬡ <b>Intelligence Room — הופעל!</b>\n\n"
                      f"✅ ADMIN_ID: {ADMIN_ID}\n"
                      f"✅ מנויים · הפניות · אבטחה\n"
                      f"✅ Yahoo Finance · כל 30 דקות\n\n"
                      f"/admin — לוח בקרה\n"
                      f"/block_ID · /unblock_ID"),
                parse_mode="HTML"
            )
        except Exception as e:
            log.error(f"post_init message failed: {e}")
    asyncio.create_task(auto_scan_loop(application))
    log.info("✅ auto_scan_loop started")

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
def main():
    ok = startup_diagnostics()
    if not ok:
        log.error("❌ Startup failed — check Railway Variables: TG_TOKEN, ADMIN_ID")
        return

    app = Application.builder().token(TG_TOKEN).post_init(post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("admin",   cmd_admin))

    # Admin action commands (regex-based)
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+"), cmd_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+"),  cmd_reject))
    app.add_handler(MessageHandler(filters.Regex(r"^/block_\d+"),   cmd_block))
    app.add_handler(MessageHandler(filters.Regex(r"^/unblock_\d+"), cmd_unblock))

    # Callback + messages
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

    log.info("✅ Bot polling started")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
