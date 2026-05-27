"""
⬡ Intelligence Room — Telegram Trading Bot
Production Ready | Railway | python-telegram-bot v20+
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
log = logging.getLogger("IntelligenceRoom")

# ═══════════════════════════════════════════════════════
# CONFIG — נטען מ-ENV בלבד
# ═══════════════════════════════════════════════════════
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
ADMIN_ID = None  # נטען ב-main()

PAYMENT = {
    "bit":    "050-XXXXXXX",
    "paybox": "050-XXXXXXX",
    "bank": (
        "🏦 בנק הבינלאומי הראשון לישראל\n"
        "סניף: 062 — קרית גת\n"
        "חשבון: 259794\n"
        "מזהה: 034653667"
    ),
}

PLANS = {
    "trial":   {"name": "ניסיון חינמי", "price": 0,    "days": 3},
    "monthly": {"name": "מנוי חודשי",   "price": 300,  "days": 30},
    "yearly":  {"name": "מנוי שנתי",    "price": 3000, "days": 365},
}

ASSETS = [
    # ── מניות טכנולוגיה ──
    {"s": "NVDA",    "n": "NVIDIA",          "t": "stock",     "cat": "מניות"},
    {"s": "AAPL",    "n": "Apple",           "t": "stock",     "cat": "מניות"},
    {"s": "MSFT",    "n": "Microsoft",       "t": "stock",     "cat": "מניות"},
    {"s": "GOOGL",   "n": "Alphabet",        "t": "stock",     "cat": "מניות"},
    {"s": "META",    "n": "Meta",            "t": "stock",     "cat": "מניות"},
    {"s": "AMZN",    "n": "Amazon",          "t": "stock",     "cat": "מניות"},
    {"s": "TSLA",    "n": "Tesla",           "t": "stock",     "cat": "מניות"},
    {"s": "AMD",     "n": "AMD",             "t": "stock",     "cat": "מניות"},
    {"s": "INTC",    "n": "Intel",           "t": "stock",     "cat": "מניות"},
    {"s": "ORCL",    "n": "Oracle",          "t": "stock",     "cat": "מניות"},
    {"s": "CRM",     "n": "Salesforce",      "t": "stock",     "cat": "מניות"},
    {"s": "NFLX",    "n": "Netflix",         "t": "stock",     "cat": "מניות"},
    {"s": "UBER",    "n": "Uber",            "t": "stock",     "cat": "מניות"},
    {"s": "PLTR",    "n": "Palantir",        "t": "stock",     "cat": "מניות"},
    {"s": "SOFI",    "n": "SoFi",            "t": "stock",     "cat": "מניות"},
    {"s": "COIN",    "n": "Coinbase",        "t": "stock",     "cat": "מניות"},
    {"s": "MSTR",    "n": "MicroStrategy",   "t": "stock",     "cat": "מניות"},
    {"s": "ARM",     "n": "ARM Holdings",    "t": "stock",     "cat": "מניות"},
    {"s": "AVGO",    "n": "Broadcom",        "t": "stock",     "cat": "מניות"},
    {"s": "JPM",     "n": "JPMorgan",        "t": "stock",     "cat": "מניות"},
    {"s": "BAC",     "n": "Bank of America", "t": "stock",     "cat": "מניות"},
    {"s": "GS",      "n": "Goldman Sachs",   "t": "stock",     "cat": "מניות"},
    {"s": "V",       "n": "Visa",            "t": "stock",     "cat": "מניות"},
    {"s": "JNJ",     "n": "Johnson & Johnson","t": "stock",    "cat": "מניות"},
    {"s": "PFE",     "n": "Pfizer",          "t": "stock",     "cat": "מניות"},
    {"s": "WMT",     "n": "Walmart",         "t": "stock",     "cat": "מניות"},
    {"s": "SMCI",    "n": "SuperMicro",      "t": "stock",     "cat": "מניות"},
    # ── קריפטו ──
    {"s": "BTC-USD", "n": "Bitcoin",         "t": "crypto",    "cat": "קריפטו"},
    {"s": "ETH-USD", "n": "Ethereum",        "t": "crypto",    "cat": "קריפטו"},
    {"s": "SOL-USD", "n": "Solana",          "t": "crypto",    "cat": "קריפטו"},
    {"s": "BNB-USD", "n": "BNB",             "t": "crypto",    "cat": "קריפטו"},
    {"s": "XRP-USD", "n": "XRP",             "t": "crypto",    "cat": "קריפטו"},
    {"s": "ADA-USD", "n": "Cardano",         "t": "crypto",    "cat": "קריפטו"},
    {"s": "AVAX-USD","n": "Avalanche",       "t": "crypto",    "cat": "קריפטו"},
    {"s": "DOGE-USD","n": "Dogecoin",        "t": "crypto",    "cat": "קריפטו"},
    {"s": "LINK-USD","n": "Chainlink",       "t": "crypto",    "cat": "קריפטו"},
    {"s": "DOT-USD", "n": "Polkadot",        "t": "crypto",    "cat": "קריפטו"},
    {"s": "UNI-USD", "n": "Uniswap",         "t": "crypto",    "cat": "קריפטו"},
    # ── סחורות ──
    {"s": "GC=F",    "n": "זהב",             "t": "commodity", "cat": "סחורות"},
    {"s": "SI=F",    "n": "כסף",             "t": "commodity", "cat": "סחורות"},
    {"s": "CL=F",    "n": "נפט WTI",         "t": "commodity", "cat": "סחורות"},
    {"s": "BZ=F",    "n": "נפט Brent",       "t": "commodity", "cat": "סחורות"},
    {"s": "NG=F",    "n": "גז טבעי",         "t": "commodity", "cat": "סחורות"},
    {"s": "HG=F",    "n": "נחושת",           "t": "commodity", "cat": "סחורות"},
    {"s": "PL=F",    "n": "פלטינה",          "t": "commodity", "cat": "סחורות"},
    {"s": "ZW=F",    "n": "חיטה",            "t": "commodity", "cat": "סחורות"},
    {"s": "ZC=F",    "n": "תירס",            "t": "commodity", "cat": "סחורות"},
    # ── פורקס ──
    {"s": "EURUSD=X","n": "EUR/USD",         "t": "forex",     "cat": "פורקס"},
    {"s": "GBPUSD=X","n": "GBP/USD",         "t": "forex",     "cat": "פורקס"},
    {"s": "USDJPY=X","n": "USD/JPY",         "t": "forex",     "cat": "פורקס"},
    {"s": "USDILS=X","n": "USD/ILS",         "t": "forex",     "cat": "פורקס"},
    {"s": "AUDUSD=X","n": "AUD/USD",         "t": "forex",     "cat": "פורקס"},
    {"s": "USDCAD=X","n": "USD/CAD",         "t": "forex",     "cat": "פורקס"},
    {"s": "USDCHF=X","n": "USD/CHF",         "t": "forex",     "cat": "פורקס"},
    # ── ETF ──
    {"s": "SPY",     "n": "S&P 500 ETF",     "t": "etf",       "cat": "ETF"},
    {"s": "QQQ",     "n": "Nasdaq ETF",      "t": "etf",       "cat": "ETF"},
    {"s": "DIA",     "n": "Dow Jones ETF",   "t": "etf",       "cat": "ETF"},
    {"s": "IWM",     "n": "Russell 2000",    "t": "etf",       "cat": "ETF"},
    {"s": "GLD",     "n": "Gold ETF",        "t": "etf",       "cat": "ETF"},
    {"s": "USO",     "n": "Oil ETF",         "t": "etf",       "cat": "ETF"},
    {"s": "TLT",     "n": "Bonds ETF",       "t": "etf",       "cat": "ETF"},
    # ── ישראל ──
    {"s": "TEVA",    "n": "טבע",             "t": "stock",     "cat": "ישראל"},
    {"s": "CHKP",    "n": "Check Point",     "t": "stock",     "cat": "ישראל"},
    {"s": "NICE",    "n": "NICE Systems",    "t": "stock",     "cat": "ישראל"},
    {"s": "CYBR",    "n": "CyberArk",        "t": "stock",     "cat": "ישראל"},
    {"s": "WIX",     "n": "Wix",             "t": "stock",     "cat": "ישראל"},
    {"s": "MNDY",    "n": "Monday.com",      "t": "stock",     "cat": "ישראל"},
    {"s": "GLBE",    "n": "Global-E",        "t": "stock",     "cat": "ישראל"},
]

# ── קטגוריות לתפריט ──
CATEGORIES = ["מניות", "קריפטו", "סחורות", "פורקס", "ETF", "ישראל"]

# ═══════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════
def db_load():
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"users": {}, "pending": {}, "referrals": {}}

def db_save(data):
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def bl_load():
    try:
        with open("blocked.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"blocked": [], "attempts": {}}

def bl_save(data):
    with open("blocked.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════
def is_admin(uid: int) -> bool:
    return ADMIN_ID is not None and int(uid) == int(ADMIN_ID)

def is_blocked(uid: int) -> bool:
    if is_admin(uid):
        return False
    return str(uid) in bl_load().get("blocked", [])

def has_sub(uid: int) -> bool:
    if is_admin(uid):
        return True
    db   = db_load()
    user = db["users"].get(str(uid))
    if not user or not user.get("expiry"):
        return False
    try:
        return datetime.fromisoformat(user["expiry"]) > datetime.now()
    except:
        return False

def trial_used(uid: int) -> bool:
    return db_load()["users"].get(str(uid), {}).get("trial_used", False)

def expiry_str(uid) -> str:
    if is_admin(uid):
        return "∞ אדמין"
    user = db_load()["users"].get(str(uid))
    if not user or not user.get("expiry"):
        return "אין מנוי"
    try:
        exp  = datetime.fromisoformat(user["expiry"])
        days = max(0, (exp - datetime.now()).days)
        return f"{exp.strftime('%d/%m/%Y')} ({days} ימים)"
    except:
        return "שגיאה"

def ensure_user(uid: int, uname: str):
    db = db_load()
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
        db_save(db)

def add_sub(uid: int, uname: str, plan_key: str, days: int):
    db  = db_load()
    uid_s = str(uid)
    now = datetime.now()
    usr = db["users"].get(uid_s, {})
    cur = usr.get("expiry")
    base = now
    if cur:
        try:
            p = datetime.fromisoformat(cur)
            if p > now:
                base = p
        except:
            pass
    exp = base + timedelta(days=days)
    db["users"][uid_s] = {
        **usr,
        "user_id":    uid,
        "username":   uname or usr.get("username", ""),
        "plan":       plan_key,
        "expiry":     exp.isoformat(),
        "trial_used": True if plan_key == "trial" else usr.get("trial_used", False),
        "approved_at": now.isoformat(),
    }
    db_save(db)
    log.info(f"SUB: {uid} plan={plan_key} until={exp.strftime('%d/%m/%Y')}")

def add_pending(uid: int, uname: str, plan_key: str, method: str):
    db = db_load()
    db["pending"][str(uid)] = {
        "user_id":  uid,
        "username": uname,
        "plan":     plan_key,
        "method":   method,
        "time":     datetime.now().isoformat(),
        "token":    secrets.token_hex(8),
    }
    db_save(db)

def rm_pending(uid):
    db = db_load()
    db["pending"].pop(str(uid), None)
    db_save(db)

def add_referral(ref_id, new_id) -> int:
    db = db_load()
    rid = str(ref_id)
    db.setdefault("referrals", {}).setdefault(rid, [])
    if str(new_id) not in db["referrals"][rid]:
        db["referrals"][rid].append(str(new_id))
        count = len(db["referrals"][rid])
        db["users"].setdefault(rid, {})["referrals_count"] = count
        db_save(db)
        return count
    return len(db["referrals"].get(rid, []))

def block_user(uid_s: str):
    bl = bl_load()
    bl.setdefault("blocked", [])
    if uid_s not in bl["blocked"]:
        bl["blocked"].append(uid_s)
        bl_save(bl)

def unblock_user(uid_s: str):
    bl = bl_load()
    if uid_s in bl.get("blocked", []):
        bl["blocked"].remove(uid_s)
        bl_save(bl)

# ═══════════════════════════════════════════════════════
# MARKET DATA
# ═══════════════════════════════════════════════════════
_cache: dict = {}

async def fetch(session: aiohttp.ClientSession, symbol: str) -> dict | None:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        hdr = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        async with session.get(url, headers=hdr, params={"interval":"1d","range":"5d"},
                               timeout=aiohttp.ClientTimeout(total=15)) as r:
            d      = await r.json(content_type=None)
            res    = d["chart"]["result"][0]
            meta   = res["meta"]
            closes = [c for c in res.get("indicators",{}).get("quote",[{}])[0].get("close",[]) if c]
            price  = float(meta.get("regularMarketPrice", 0))
            prev   = float(meta.get("chartPreviousClose", price) or price)
            chg    = round((price-prev)/prev*100, 2) if prev else 0.0
            h5     = max(closes[-5:]) if len(closes)>=5 else price*1.05
            l5     = min(closes[-5:]) if len(closes)>=5 else price*0.95
            return {"price":price,"changePct":chg,"volume":int(meta.get("regularMarketVolume",0)),
                    "prev":prev,"high_5d":round(h5,2),"low_5d":round(l5,2)}
    except Exception as e:
        log.warning(f"fetch {symbol}: {e}")
        return None

async def scan() -> list:
    global _cache
    async with aiohttp.ClientSession() as session:
        qs = await asyncio.gather(*[fetch(session, a["s"]) for a in ASSETS])
    results = []
    for asset, q in zip(ASSETS, qs):
        if q:
            _cache[asset["s"]] = q
        elif asset["s"] in _cache:
            q = _cache[asset["s"]]
        if q:
            results.append({"asset":asset, "quote":q, "sig":signal(q)})
    log.info(f"scan: {len(results)}/{len(ASSETS)}")
    return results

def signal(q: dict) -> dict:
    c=q["changePct"]; p=q["price"]; h=q["high_5d"]; l=q["low_5d"]
    r=max(h-l, p*0.01)
    if c>4:  return dict(action="BUY",       conf=min(90,70+c*2),      emoji="🚀",level="HIGH",reason="פריצת מומנטום חזקה",  entry=round(p,2),        target=round(p*1.08,2),stop=round(p*0.96,2))
    if c>2:  return dict(action="BUY",       conf=65,                  emoji="📈",level="HIGH",reason="מומנטום חיובי",        entry=round(p,2),        target=round(p*1.05,2),stop=round(p*0.97,2))
    if c>0.5:return dict(action="WATCH",     conf=55,                  emoji="✅",level="MED", reason="עלייה מתונה — המתן",  entry=round(l+r*0.3,2),  target=round(h,2),     stop=round(l*0.98,2))
    if c<-4: return dict(action="SELL/SHORT",conf=min(90,70+abs(c)*2), emoji="🔴",level="HIGH",reason="ירידה חדה — סכנה",    entry=round(p,2),        target=round(p*0.92,2),stop=round(p*1.04,2))
    if c<-2: return dict(action="CAUTION",   conf=60,                  emoji="⚠️",level="HIGH",reason="לחץ מוכרים — המתן",  entry=round(l,2),        target=round(p*0.97,2),stop=round(p*1.03,2))
    return       dict(action="NEUTRAL",      conf=45,                  emoji="⬜",level="LOW", reason="אין כיוון ברור",     entry=round(l+r*0.4,2),  target=round(h*0.99,2),stop=round(l*0.97,2))

def fp(a,p): return f"${p:,.2f}" if (a["t"]=="crypto" or p>1000) else f"${p:.2f}"
def fc(c):   return f"{'+' if c>=0 else ''}{c:.2f}%"

# ═══════════════════════════════════════════════════════
# MESSAGE BUILDERS
# ═══════════════════════════════════════════════════════
def msg_watchlist(results):
    if not results: return "❌ <b>אין נתונים</b>\n\nנסה שוב."
    t = datetime.now().strftime("%H:%M:%S")
    lines = [f"📊 <b>WATCHLIST — Intelligence Room</b>\n🕐 {t}\n"]
    for r in results:
        a,q,s=r["asset"],r["quote"],r["sig"]
        lines.append(f"{s['emoji']} <b>{a['s']}</b>  {fp(a,q['price'])}  <b>{fc(q['changePct'])}</b>\n    └ {s['action']} · {int(s['conf'])}% ביטחון")
    lines.append("\n📡 Yahoo Finance · <i>⬡ Intelligence Room</i>")
    return "\n".join(lines)

def msg_signals(results):
    if not results: return "❌ אין נתונים."
    buys=[r for r in results if r["sig"]["action"]=="BUY"]
    sells=[r for r in results if "SELL" in r["sig"]["action"]]
    caution=[r for r in results if r["sig"]["action"]=="CAUTION"]
    watch=[r for r in results if r["sig"]["action"] in ("WATCH","NEUTRAL")]
    t=datetime.now().strftime("%d/%m/%Y %H:%M")
    m=f"💹 <b>המלצות מסחר — Intelligence Room</b>\n📅 {t}\n{'━'*20}\n\n"
    if buys:
        m+="🟢 <b>קנייה — BUY</b>\n\n"
        for r in buys:
            a,q,s=r["asset"],r["quote"],r["sig"]
            m+=(f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                f"💰 {fp(a,q['price'])} ({fc(q['changePct'])})\n"
                f"📥 כניסה: <b>{fp(a,s['entry'])}</b>\n"
                f"🎯 יעד:   <b>{fp(a,s['target'])}</b>\n"
                f"🛑 סטופ:  <b>{fp(a,s['stop'])}</b>\n"
                f"📊 {int(s['conf'])}% · {s['reason']}\n\n")
    if sells:
        m+="🔴 <b>מכירה — SELL</b>\n\n"
        for r in sells:
            a,q,s=r["asset"],r["quote"],r["sig"]
            m+=(f"🏷 <b>{a['s']}</b> — {a['n']}\n"
                f"💰 {fp(a,q['price'])} ({fc(q['changePct'])})\n"
                f"📤 כניסה שורט: <b>{fp(a,s['entry'])}</b>\n"
                f"🎯 יעד:        <b>{fp(a,s['target'])}</b>\n"
                f"🛑 סטופ:       <b>{fp(a,s['stop'])}</b>\n"
                f"📊 {int(s['conf'])}% · {s['reason']}\n\n")
    if caution:
        m+="⚠️ <b>זהירות:</b>\n"
        for r in caution:
            a,q,s=r["asset"],r["quote"],r["sig"]
            m+=f"• <b>{a['s']}</b> {fp(a,q['price'])} ({fc(q['changePct'])}) — {s['reason']}\n"
        m+="\n"
    if watch:
        m+="⬜ <b>המתנה:</b>\n"
        for r in watch:
            a,q=r["asset"],r["quote"]
            m+=f"• <b>{a['s']}</b> {fp(a,q['price'])} ({fc(q['changePct'])})\n"
        m+="\n"
    m+=(f"{'━'*20}\n📊 {len(buys)} קנייה · {len(sells)} מכירה · {len(caution)} זהירות\n"
        f"⚠️ <i>זו אינה המלצת השקעה. סחר באחריותך.</i>\n<i>⬡ Intelligence Room</i>")
    return m

def msg_briefing(results):
    t=datetime.now().strftime("%d/%m/%Y %H:%M")
    ups=[r for r in results if r["quote"]["changePct"]>1]
    dns=[r for r in results if r["quote"]["changePct"]<-1]
    m=f"🌅 <b>תדריך — Intelligence Room</b>\n📅 {t}\n\n"
    if ups:
        m+="🚀 <b>עולים:</b>\n"
        for r in ups: m+=f"• <b>{r['asset']['s']}</b>: {fp(r['asset'],r['quote']['price'])} ({fc(r['quote']['changePct'])})\n"
        m+="\n"
    if dns:
        m+="⚠️ <b>יורדים:</b>\n"
        for r in dns: m+=f"• <b>{r['asset']['s']}</b>: {fp(r['asset'],r['quote']['price'])} ({fc(r['quote']['changePct'])})\n"
        m+="\n"
    if not ups and not dns: m+="📊 השוק רגוע — אין תנועות משמעותיות\n\n"
    m+=f"📊 {len(results)} נכסים · {len(ups)} עולים · {len(dns)} יורדים\n<i>⬡ Intelligence Room</i>"
    return m

def msg_alert(a,q,s):
    return (f"{s['emoji']} <b>INTELLIGENCE ROOM ALERT</b>\n\n"
            f"🏷 <b>{a['s']}</b> — {a['n']}\n"
            f"💰 מחיר: <b>{fp(a,q['price'])}</b>\n"
            f"📊 שינוי: <b>{fc(q['changePct'])}</b>\n"
            f"📥 כניסה: <b>{fp(a,s['entry'])}</b>\n"
            f"🎯 יעד:   <b>{fp(a,s['target'])}</b>\n"
            f"🛑 סטופ:  <b>{fp(a,s['stop'])}</b>\n"
            f"📡 {s['action']} · {int(s['conf'])}%\n"
            f"🕐 {datetime.now().strftime('%H:%M')}\n\n"
            f"<i>⬡ Intelligence Room · AI Trading</i>")

# ═══════════════════════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════════════════════
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Watchlist",             callback_data="watchlist"),
         InlineKeyboardButton("💹 קנייה/מכירה",           callback_data="signals")],
        [InlineKeyboardButton("🌅 תדריך בוקר",            callback_data="briefing"),
         InlineKeyboardButton("🔍 סריקה",                 callback_data="scan_menu")],
        [InlineKeyboardButton("👑 מנויים",                 callback_data="subscribe"),
         InlineKeyboardButton("👥 חבר מביא חבר",          callback_data="referral")],
        [InlineKeyboardButton("ℹ️ עזרה",                   callback_data="help")],
    ])

def kb_scan_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 סרוק הכל (65 נכסים)",  callback_data="scan_all")],
        [InlineKeyboardButton("📈 מניות",                  callback_data="scan_cat_מניות"),
         InlineKeyboardButton("₿ קריפטו",                 callback_data="scan_cat_קריפטו")],
        [InlineKeyboardButton("🏅 סחורות",                 callback_data="scan_cat_סחורות"),
         InlineKeyboardButton("💱 פורקס",                  callback_data="scan_cat_פורקס")],
        [InlineKeyboardButton("📦 ETF",                    callback_data="scan_cat_ETF"),
         InlineKeyboardButton("🇮🇱 ישראל",                 callback_data="scan_cat_ישראל")],
        [InlineKeyboardButton("🔙 חזרה",                   callback_data="menu")],
    ])

def kb_sub():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆓 ניסיון חינמי — 3 ימים", callback_data="plan_trial")],
        [InlineKeyboardButton("📅 מנוי חודשי — ₪300",      callback_data="plan_monthly")],
        [InlineKeyboardButton("🏆 מנוי שנתי — ₪3,000",     callback_data="plan_yearly")],
        [InlineKeyboardButton("🔙 חזרה",                    callback_data="menu")],
    ])

def kb_pay(pk):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ביט",           callback_data=f"pay_bit_{pk}")],
        [InlineKeyboardButton("💳 פייבוקס",       callback_data=f"pay_paybox_{pk}")],
        [InlineKeyboardButton("🏦 העברה בנקאית", callback_data=f"pay_bank_{pk}")],
        [InlineKeyboardButton("🔙 חזרה",          callback_data="subscribe")],
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 תפריט ראשי", callback_data="menu")]])

def kb_action(a):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 רענן",   callback_data=a),
         InlineKeyboardButton("🔙 תפריט", callback_data="menu")]
    ])

def kb_nosub():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 הצטרף עכשיו", callback_data="subscribe")],
        [InlineKeyboardButton("🔙 תפריט",       callback_data="menu")],
    ])

# ═══════════════════════════════════════════════════════
# GUARD
# ═══════════════════════════════════════════════════════
async def guard(update: Update, cb=False) -> bool:
    uid = update.effective_user.id
    if is_admin(uid): return True
    if is_blocked(uid):
        m = "🚫 הגישה שלך נחסמה."
        if cb: await update.callback_query.answer(m, show_alert=True)
        else:  await update.message.reply_text(m)
        return False
    if has_sub(uid): return True
    m = ("🔒 <b>תוכן זה זמין למנויים בלבד</b>\n\n"
         "🆓 ניסיון חינמי 3 ימים\n📅 חודשי ₪300\n🏆 שנתי ₪3,000")
    if cb: await update.callback_query.edit_message_text(m, parse_mode="HTML", reply_markup=kb_nosub())
    else:  await update.message.reply_text(m, parse_mode="HTML", reply_markup=kb_nosub())
    return False

# ═══════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.first_name or "משתמש"
    if is_blocked(uid) and not is_admin(uid):
        await update.message.reply_text("🚫 הגישה שלך נחסמה.")
        return
    if ctx.args and ctx.args[0].startswith("REF"):
        ref_id = ctx.args[0][3:]
        if ref_id != str(uid):
            count = add_referral(ref_id, uid)
            if count > 0 and count % 2 == 0:
                add_sub(int(ref_id), "", "monthly", 30)
                try:
                    await ctx.bot.send_message(
                        chat_id=int(ref_id),
                        text=f"🎉 <b>מזל טוב!</b>\n\nצירפת 2 חברים — קיבלת חודש חינם!\nתוקף: {expiry_str(ref_id)}\n\n<i>⬡ Intelligence Room</i>",
                        parse_mode="HTML")
                except: pass
    ensure_user(uid, uname)
    badge  = " 👑" if is_admin(uid) else ""
    status = f"✅ מנוי פעיל: {expiry_str(uid)}" if has_sub(uid) else "❌ אין מנוי פעיל"
    await update.message.reply_text(
        f"⬡ <b>Intelligence Room</b>{badge}\n\nברוך הבא! 👋\n{status}\n\nבחר פעולה:",
        parse_mode="HTML", reply_markup=kb_main()
    )

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    db     = db_load()
    now    = datetime.now()
    active = [u for u in db["users"].values()
              if u.get("expiry") and datetime.fromisoformat(u["expiry"]) > now]
    pend   = db["pending"]
    m = (f"👑 <b>לוח בקרה</b>\n\n"
         f"👥 משתמשים: {len(db['users'])}\n"
         f"✅ פעילים: {len(active)}\n"
         f"⏳ ממתינים: {len(pend)}\n\n")
    if pend:
        m += "⏳ <b>ממתינים לאישור:</b>\n\n"
        for uid_s, p in pend.items():
            plan = PLANS.get(p["plan"], {})
            t    = datetime.fromisoformat(p["time"]).strftime("%d/%m %H:%M")
            m += (f"👤 @{p.get('username','?')} (ID:{uid_s})\n"
                  f"📋 {plan.get('name','?')} ₪{plan.get('price',0)} · {p.get('method','?')} · {t}\n"
                  f"✅ /approve_{uid_s}   ❌ /reject_{uid_s}   🚫 /block_{uid_s}\n\n")
    if active:
        m += "✅ <b>מנויים (10 אחרונים):</b>\n"
        for u in list(active)[-10:]:
            exp = datetime.fromisoformat(u["expiry"]).strftime("%d/%m/%Y")
            m += f"• @{u.get('username','?')} — {u.get('plan','?')} עד {exp}\n"
    await update.message.reply_text(m, parse_mode="HTML")

async def cmd_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid_s = update.message.text.replace("/approve_","").strip()
    db    = db_load()
    p     = db["pending"].get(uid_s)
    if not p: await update.message.reply_text("❌ לא נמצא."); return
    plan = PLANS[p["plan"]]
    add_sub(int(uid_s), p.get("username",""), p["plan"], plan["days"])
    rm_pending(uid_s)
    await update.message.reply_text(f"✅ אושר! @{p.get('username','?')} — {plan['name']}")
    try:
        await ctx.bot.send_message(
            chat_id=int(uid_s),
            text=(f"✅ <b>המנוי אושר!</b>\n\nתוכנית: <b>{plan['name']}</b>\nתוקף: <b>{expiry_str(uid_s)}</b>\n\nשלח /start 🚀\n<i>⬡ Intelligence Room</i>"),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 פתח תפריט", callback_data="menu")]]))
    except Exception as e: log.warning(f"approve notify: {e}")

async def cmd_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid_s = update.message.text.replace("/reject_","").strip()
    db    = db_load()
    p     = db["pending"].get(uid_s)
    if not p: await update.message.reply_text("❌ לא נמצא."); return
    rm_pending(uid_s)
    await update.message.reply_text(f"❌ נדחה — @{p.get('username','?')}")
    try:
        await ctx.bot.send_message(
            chat_id=int(uid_s),
            text="❌ <b>התשלום לא אושר</b>\n\nשלח צילום מסך ברור ונסה שוב.\n<i>⬡ Intelligence Room</i>",
            parse_mode="HTML", reply_markup=kb_nosub())
    except Exception as e: log.warning(f"reject notify: {e}")

async def cmd_block(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid_s = update.message.text.replace("/block_","").strip()
    block_user(uid_s)
    await update.message.reply_text(f"🚫 {uid_s} נחסם.")

async def cmd_unblock(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid_s = update.message.text.replace("/unblock_","").strip()
    unblock_user(uid_s)
    await update.message.reply_text(f"✅ {uid_s} שוחרר.")

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

    if is_blocked(uid) and not is_admin(uid):
        await q.answer("🚫 הגישה שלך נחסמה.", show_alert=True)
        return

    # ── תפריט ──
    if data == "menu":
        badge  = " 👑" if is_admin(uid) else ""
        status = f"✅ מנוי פעיל: {expiry_str(uid)}" if has_sub(uid) else "❌ אין מנוי"
        await q.edit_message_text(
            f"⬡ <b>Intelligence Room</b>{badge}\n\n{status}\n\nבחר פעולה:",
            parse_mode="HTML", reply_markup=kb_main())
        return

    # ── עזרה ──
    if data == "help":
        await q.edit_message_text(
            "⬡ <b>פקודות:</b>\n\n/start — תפריט\n/watchlist — מחירים\n/signals — קנייה/מכירה\n/briefing — תדריך\n/scan — סריקה\n\n⚠️ <i>זו אינה המלצת השקעה.</i>",
            parse_mode="HTML", reply_markup=kb_back())
        return

    # ── מנויים ──
    if data == "subscribe":
        txt = (f"✅ <b>מנוי פעיל!</b>\n\nתוקף: {expiry_str(uid)}\n\nרוצה לחדש?" if has_sub(uid) else
               "👑 <b>Intelligence Room — מנויים</b>\n\n🆓 ניסיון חינמי — 3 ימים\n📅 מנוי חודשי — ₪300\n🏆 מנוי שנתי — ₪3,000\n\nבחר תוכנית:")
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=kb_sub())
        return

    # ── בחירת תוכנית ──
    if data.startswith("plan_"):
        pk   = data[5:]
        plan = PLANS.get(pk)
        if not plan: return
        if pk == "trial":
            if trial_used(uid):
                await q.edit_message_text("❌ <b>כבר השתמשת בניסיון</b>\n\nשדרג למנוי:", parse_mode="HTML", reply_markup=kb_sub())
                return
            add_sub(uid, uname, "trial", 3)
            try: await ctx.bot.send_message(chat_id=ADMIN_ID, text=f"🆓 ניסיון: @{uname} (ID:{uid})")
            except: pass
            await q.edit_message_text(
                f"🎉 <b>הניסיון הופעל!</b>\n\n✅ תוקף: {expiry_str(uid)}\n\n<i>⬡ Intelligence Room</i>",
                parse_mode="HTML", reply_markup=kb_back())
            return
        await q.edit_message_text(
            f"💳 <b>{plan['name']} — ₪{plan['price']}</b>\n\nבחר אמצעי תשלום:",
            parse_mode="HTML", reply_markup=kb_pay(pk))
        return

    # ── תשלום ──
    if data.startswith("pay_"):
        parts  = data.split("_", 2)
        method = parts[1]
        pk     = parts[2]
        plan   = PLANS.get(pk)
        if not plan: return
        details = {
            "bit":    f"💳 <b>ביט</b>\nשלח ₪{plan['price']} ל:\n<b>{PAYMENT['bit']}</b>",
            "paybox": f"💳 <b>פייבוקס</b>\nשלח ₪{plan['price']} ל:\n<b>{PAYMENT['paybox']}</b>",
            "bank":   f"🏦 <b>העברה בנקאית</b>\n\n{PAYMENT['bank']}\n\nסכום: <b>₪{plan['price']}</b>",
        }
        add_pending(uid, uname, pk, method)
        await q.edit_message_text(
            f"📋 <b>הוראות תשלום</b>\n\n{details[method]}\n\n"
            f"✅ לאחר התשלום:\n1. צלם אישור\n2. שלח לבוט\n3. אישור תוך 24 שעות\n\n<i>⬡ Intelligence Room</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 שלחתי — ממתין לאישור", callback_data=f"sent_{pk}")],
                [InlineKeyboardButton("🔙 חזרה", callback_data="subscribe")],
            ]))
        try:
            await ctx.bot.send_message(
                chat_id=ADMIN_ID,
                text=(f"⏳ <b>תשלום ממתין</b>\n\n@{uname} (ID:{uid})\n"
                      f"{plan['name']} ₪{plan['price']} · {method}\n\n"
                      f"✅ /approve_{uid}\n❌ /reject_{uid}\n🚫 /block_{uid}"),
                parse_mode="HTML")
        except Exception as e: log.warning(f"admin notify: {e}")
        return

    # ── אישור שליחה ──
    if data.startswith("sent_"):
        plan = PLANS.get(data[5:], {})
        await q.edit_message_text(
            f"⏳ <b>הבקשה התקבלה!</b>\n\n📋 {plan.get('name','')}\n⏰ אישור תוך 24 שעות\n\n<i>⬡ Intelligence Room</i>",
            parse_mode="HTML", reply_markup=kb_back())
        return

    # ── חבר מביא חבר ──
    if data == "referral":
        db    = db_load()
        user  = db["users"].get(str(uid), {})
        code  = user.get("referral_code", f"REF{uid}")
        count = len(db.get("referrals", {}).get(str(uid), []))
        need  = 2 - (count % 2) if count % 2 != 0 else 2
        link  = f"https://t.me/{ctx.bot.username}?start={code}"
        await q.edit_message_text(
            f"👥 <b>חבר מביא חבר</b>\n\nהקישור שלך:\n<code>{link}</code>\n\n"
            f"📊 צירפת: <b>{count}</b> חברים\n🎁 עוד <b>{need}</b> לחודש חינם!\n\n"
            f"כל 2 חברים = חודש חינם!\n\n<i>⬡ Intelligence Room</i>",
            parse_mode="HTML", reply_markup=kb_back())
        return

    # ── פעולות שוק ──
    if data in ("watchlist", "signals", "briefing", "scan"):
        if not await guard(update, cb=True):
            return
        loading = {"watchlist":"📊 <b>טוען...</b>","signals":"💹 <b>מחשב...</b>",
                   "briefing":"🌅 <b>מכין...</b>","scan":"🔍 <b>סורק...</b>"}
        lm = await q.edit_message_text(loading[data], parse_mode="HTML")
        results = await scan()

        if   data == "watchlist": text = msg_watchlist(results)
        elif data == "signals":   text = msg_signals(results)
        elif data == "briefing":  text = msg_briefing(results)
        elif data == "scan":
            sent = 0
            for r in results:
                if r["sig"]["level"] == "HIGH":
                    try:
                        await ctx.bot.send_message(cid, msg_alert(r["asset"],r["quote"],r["sig"]), parse_mode="HTML")
                        sent += 1
                        await asyncio.sleep(0.5)
                    except Exception as e: log.warning(f"alert: {e}")
            text = msg_watchlist(results) + f"\n\n✅ סריקה הושלמה — {sent} התראות"

        try:
            await ctx.bot.edit_message_text(
                chat_id=cid, message_id=lm.message_id,
                text=text, parse_mode="HTML", reply_markup=kb_action(data))
        except Exception as e: log.error(f"edit: {e}")
        return

    # ── תפריט סריקה ──
    if data == "scan_menu":
        await q.edit_message_text(
            "🔍 <b>בחר קטגוריה לסריקה:</b>\n\n📈 מניות\n₿ קריפטו\n🏅 סחורות\n💱 פורקס\n📦 ETF\n🇮🇱 ישראל\n🔍 הכל",
            parse_mode="HTML", reply_markup=kb_scan_menu()
        )
        return

    log.warning(f"unknown callback: {data}")

# ═══════════════════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════════════════
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.first_name or "משתמש"
    if is_blocked(uid) and not is_admin(uid):
        await update.message.reply_text("🚫 הגישה שלך נחסמה.")
        return
    db   = db_load()
    pend = db["pending"].get(str(uid))
    if update.message.photo:
        if pend:
            plan = PLANS.get(pend["plan"], {})
            try:
                await ctx.bot.forward_message(ADMIN_ID, update.message.chat_id, update.message.message_id)
                await ctx.bot.send_message(
                    ADMIN_ID,
                    f"📸 <b>אישור תשלום</b>\n\n@{uname} (ID:{uid})\n{plan.get('name','?')} ₪{plan.get('price','?')} · {pend.get('method','?')}\n\n✅ /approve_{uid}\n❌ /reject_{uid}\n🚫 /block_{uid}",
                    parse_mode="HTML")
            except Exception as e: log.warning(f"fwd: {e}")
            await update.message.reply_text(
                "✅ <b>צילום התקבל!</b>\n\n⏰ אישור תוך 24 שעות\n\n<i>⬡ Intelligence Room</i>",
                parse_mode="HTML", reply_markup=kb_back())
        else:
            await update.message.reply_text(
                "📸 אין בקשת תשלום פעילה.\nשלח /start ובחר תוכנית.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 תפריט", callback_data="menu")]]))
    else:
        await update.message.reply_text(
            "שלח /start לפתיחת התפריט ⬡",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 פתח תפריט", callback_data="menu")]]))

# ═══════════════════════════════════════════════════════
# AUTO SCAN
# ═══════════════════════════════════════════════════════
async def auto_scan(app: Application):
    await asyncio.sleep(120)
    while True:
        try:
            log.info("🔄 auto scan...")
            results = await scan()
            db      = db_load()
            now     = datetime.now()
            rcpts   = {ADMIN_ID} if ADMIN_ID else set()
            for u in db["users"].values():
                try:
                    if u.get("expiry") and datetime.fromisoformat(u["expiry"]) > now:
                        rcpts.add(int(u["user_id"]))
                except: pass
            high = [r for r in results if r["sig"]["level"] == "HIGH"]
            log.info(f"auto: {len(high)} alerts → {len(rcpts)} users")
            for r in high:
                alert = msg_alert(r["asset"], r["quote"], r["sig"])
                for cid in rcpts:
                    try:
                        await app.bot.send_message(cid, alert, parse_mode="HTML")
                        await asyncio.sleep(0.3)
                    except Exception as e: log.warning(f"auto alert {cid}: {e}")
        except Exception as e:
            log.error(f"auto_scan error: {e}")
        await asyncio.sleep(30 * 60)

# ═══════════════════════════════════════════════════════
# POST INIT
# ═══════════════════════════════════════════════════════
async def post_init(app: Application):
    if ADMIN_ID:
        try:
            await app.bot.send_message(
                ADMIN_ID,
                f"⬡ <b>Intelligence Room — הופעל!</b>\n\n✅ ADMIN_ID: {ADMIN_ID}\n✅ מנויים · הפניות · אבטחה\n✅ Yahoo Finance · כל 30 דקות\n\n/admin — לוח בקרה",
                parse_mode="HTML")
        except Exception as e: log.error(f"post_init msg: {e}")
    asyncio.create_task(auto_scan(app))
    log.info("✅ auto_scan started")

# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
def main():
    global ADMIN_ID

    # טעינת ADMIN_ID
    raw = os.environ.get("ADMIN_ID", "").strip()
    if not raw:
        log.error("❌ ADMIN_ID חסר! הוסף ב-Railway Variables")
    else:
        try:
            ADMIN_ID = int(raw)
            log.info(f"✅ ADMIN_ID: {ADMIN_ID}")
        except ValueError:
            log.error(f"❌ ADMIN_ID לא תקין: '{raw}'")

    if not TG_TOKEN:
        log.error("❌ TG_TOKEN חסר!")
        return

    log.info(f"✅ TG_TOKEN: {TG_TOKEN[:10]}...")
    log.info("🚀 מפעיל Intelligence Room Bot...")

    # מחיקת webhook ישן — מונע 409 Conflict
    import httpx
    try:
        httpx.post(f"https://api.telegram.org/bot{TG_TOKEN}/deleteWebhook",json={"drop_pending_updates":True},timeout=10)
        log.info("✅ Webhook נמחק")
    except Exception as e:
        log.warning(f"deleteWebhook: {e}")

    app = Application.builder().token(TG_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+"), cmd_approve))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+"),  cmd_reject))
    app.add_handler(MessageHandler(filters.Regex(r"^/block_\d+"),   cmd_block))
    app.add_handler(MessageHandler(filters.Regex(r"^/unblock_\d+"), cmd_unblock))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

    log.info("✅ Bot polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
