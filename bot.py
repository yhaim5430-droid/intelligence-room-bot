// ================================================================
// Intelligence Room Bot - FIXED & WORKING VERSION
// ================================================================
// @my_intelligencehay_bot
// Version: 2.1.0 - All bugs fixed!
// ================================================================

require('dotenv').config();
const { Telegraf } = require('telegraf');
const axios = require('axios');

// ================================================================
// CONFIGURATION
// ================================================================

const CONFIG = {
  BOT_TOKEN: process.env.BOT_TOKEN || '7754804245:AAEf5lCTTU3NB7qNnOa1-HKJXcpZLDOdseM',
  CHAT_ID: process.env.CHAT_ID || '6775881845',
  ALPHA_VANTAGE_KEY: process.env.ALPHA_VANTAGE_KEY || '40T4V3WC8TLYOELC',
  
  RATE_LIMIT_DELAY: 13000,
  CACHE_DURATION: 60000,
  
  THRESHOLDS: {
    BREAKOUT: 3.0,
    SHARP_DROP: -3.0,
    MOMENTUM: 1.5
  },
  
  SCAN_INTERVAL: 5 * 60 * 1000,
  
  WATCHLIST: {
    stocks: ['NVDA', 'AAPL', 'TSLA', 'META', 'AMD', 'MSFT'],
    crypto: ['BTC', 'ETH', 'SOL']
  }
};

// ================================================================
// STATE
// ================================================================

const STATE = {
  priceCache: new Map(),
  lastScanTime: null,
  scanIntervalId: null,
  alertsEnabled: {
    breakout: true,
    drop: true,
    momentum: true
  },
  isScanning: false,
  botReady: false,
  stats: {
    totalScans: 0,
    alertsSent: 0,
    apiCalls: 0
  }
};

// ================================================================
// INITIALIZE BOT
// ================================================================

console.log('\n╔════════════════════════════════════════╗');
console.log('║   Intelligence Room Bot - Starting    ║');
console.log('╚════════════════════════════════════════╝\n');

const bot = new Telegraf(CONFIG.BOT_TOKEN);

// ================================================================
// UTILITY FUNCTIONS
// ================================================================

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const formatChange = (change) => {
  const sign = change >= 0 ? '+' : '';
  const emoji = change >= 3 ? '🚀' : change >= 1.5 ? '📈' : change <= -3 ? '📉' : change < 0 ? '🔻' : '🟢';
  return `${emoji} ${sign}${change.toFixed(2)}%`;
};

const formatTime = (date = new Date()) => {
  return date.toLocaleString('he-IL', {
    timeZone: 'Asia/Jerusalem',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const log = (message, level = 'INFO') => {
  const timestamp = formatTime();
  const emoji = {
    INFO: 'ℹ️',
    SUCCESS: '✅',
    WARNING: '⚠️',
    ERROR: '❌',
    API: '🔌',
    COMMAND: '💬'
  }[level] || 'ℹ️';
  
  console.log(`[${timestamp}] ${emoji} ${message}`);
};

const sendMessage = async (chatId, message, options = {}) => {
  try {
    await bot.telegram.sendMessage(chatId, message, {
      parse_mode: 'HTML',
      disable_web_page_preview: true,
      ...options
    });
    log(`Message sent to ${chatId}`, 'SUCCESS');
    return true;
  } catch (error) {
    log(`Failed to send message: ${error.message}`, 'ERROR');
    return false;
  }
};

// ================================================================
// API FUNCTIONS
// ================================================================

const getStockPrice = async (symbol) => {
  const cacheKey = `stock_${symbol}`;
  const cached = STATE.priceCache.get(cacheKey);
  
  if (cached && (Date.now() - cached.timestamp < CONFIG.CACHE_DURATION)) {
    log(`Using cached data for ${symbol}`, 'INFO');
    return cached.data;
  }
  
  try {
    await sleep(CONFIG.RATE_LIMIT_DELAY);
    
    const url = `https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${symbol}&apikey=${CONFIG.ALPHA_VANTAGE_KEY}`;
    
    log(`Fetching ${symbol}...`, 'API');
    STATE.stats.apiCalls++;
    
    const response = await axios.get(url, { timeout: 10000 });
    const quote = response.data['Global Quote'];
    
    if (!quote || !quote['05. price']) {
      throw new Error('Invalid API response');
    }
    
    const data = {
      symbol: symbol,
      price: parseFloat(quote['05. price']),
      change: parseFloat(quote['09. change']),
      changePercent: parseFloat(quote['10. change percent'].replace('%', '')),
      volume: parseInt(quote['06. volume']),
      timestamp: new Date().toISOString()
    };
    
    STATE.priceCache.set(cacheKey, {
      data,
      timestamp: Date.now()
    });
    
    log(`✓ ${symbol}: $${data.price} (${formatChange(data.changePercent)})`, 'SUCCESS');
    return data;
    
  } catch (error) {
    log(`Error fetching ${symbol}: ${error.message}`, 'ERROR');
    
    if (cached) {
      log(`Using expired cache for ${symbol}`, 'WARNING');
      return cached.data;
    }
    
    return null;
  }
};

const getCryptoPrice = async (symbol) => {
  const cacheKey = `crypto_${symbol}`;
  const cached = STATE.priceCache.get(cacheKey);
  
  if (cached && (Date.now() - cached.timestamp < CONFIG.CACHE_DURATION)) {
    log(`Using cached data for ${symbol}`, 'INFO');
    return cached.data;
  }
  
  try {
    await sleep(CONFIG.RATE_LIMIT_DELAY);
    
    const url = `https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=${symbol}&to_currency=USD&apikey=${CONFIG.ALPHA_VANTAGE_KEY}`;
    
    log(`Fetching ${symbol}...`, 'API');
    STATE.stats.apiCalls++;
    
    const response = await axios.get(url, { timeout: 10000 });
    const rate = response.data['Realtime Currency Exchange Rate'];
    
    if (!rate || !rate['5. Exchange Rate']) {
      throw new Error('Invalid API response');
    }
    
    const price = parseFloat(rate['5. Exchange Rate']);
    
    let changePercent = 0;
    if (cached && cached.data.price) {
      changePercent = ((price - cached.data.price) / cached.data.price) * 100;
    }
    
    const data = {
      symbol: symbol,
      price: price,
      changePercent: changePercent,
      timestamp: new Date().toISOString()
    };
    
    STATE.priceCache.set(cacheKey, {
      data,
      timestamp: Date.now()
    });
    
    log(`✓ ${symbol}: $${data.price.toFixed(2)} (${formatChange(data.changePercent)})`, 'SUCCESS');
    return data;
    
  } catch (error) {
    log(`Error fetching ${symbol}: ${error.message}`, 'ERROR');
    
    if (cached) {
      log(`Using expired cache for ${symbol}`, 'WARNING');
      return cached.data;
    }
    
    return null;
  }
};

// ================================================================
// ALERT LOGIC
// ================================================================

const checkAlerts = (asset) => {
  const alerts = [];
  const change = asset.changePercent;
  
  if (STATE.alertsEnabled.breakout && change >= CONFIG.THRESHOLDS.BREAKOUT) {
    alerts.push({
      type: 'BREAKOUT',
      message: `<b>🚀 BREAKOUT ALERT!</b>\n${asset.symbol} surged ${formatChange(change)}\nPrice: $${asset.price.toFixed(2)}`
    });
  }
  
  if (STATE.alertsEnabled.drop && change <= CONFIG.THRESHOLDS.SHARP_DROP) {
    alerts.push({
      type: 'DROP',
      message: `<b>📉 SHARP DROP ALERT!</b>\n${asset.symbol} fell ${formatChange(change)}\nPrice: $${asset.price.toFixed(2)}`
    });
  }
  
  if (STATE.alertsEnabled.momentum && change >= CONFIG.THRESHOLDS.MOMENTUM && change < CONFIG.THRESHOLDS.BREAKOUT) {
    alerts.push({
      type: 'MOMENTUM',
      message: `<b>📈 MOMENTUM ALERT!</b>\n${asset.symbol} up ${formatChange(change)}\nPrice: $${asset.price.toFixed(2)}`
    });
  }
  
  return alerts;
};

// ================================================================
// SCANNING
// ================================================================

const performScan = async (manual = false, replyTo = null) => {
  if (STATE.isScanning) {
    log('Scan already in progress', 'WARNING');
    if (replyTo) {
      await replyTo.reply('⚠️ Scan already in progress...');
    }
    return;
  }
  
  STATE.isScanning = true;
  STATE.stats.totalScans++;
  
  const scanStart = Date.now();
  log(`\n${'='.repeat(50)}\n🔍 Starting ${manual ? 'MANUAL' : 'AUTO'} scan #${STATE.stats.totalScans}\n${'='.repeat(50)}`, 'INFO');
  
  const results = {
    stocks: [],
    crypto: [],
    alerts: [],
    errors: 0
  };
  
  try {
    // Scan stocks
    for (const symbol of CONFIG.WATCHLIST.stocks) {
      const data = await getStockPrice(symbol);
      if (data) {
        results.stocks.push(data);
        const alerts = checkAlerts(data);
        results.alerts.push(...alerts);
      } else {
        results.errors++;
      }
    }
    
    // Scan crypto
    for (const symbol of CONFIG.WATCHLIST.crypto) {
      const data = await getCryptoPrice(symbol);
      if (data) {
        results.crypto.push(data);
        const alerts = checkAlerts(data);
        results.alerts.push(...alerts);
      } else {
        results.errors++;
      }
    }
    
    STATE.lastScanTime = new Date();
    
    // Send alerts
    for (const alert of results.alerts) {
      await sendMessage(CONFIG.CHAT_ID, alert.message);
      STATE.stats.alertsSent++;
      await sleep(1000);
    }
    
    // Send summary if manual
    if (manual && replyTo) {
      const summary = formatScanSummary(results);
      await replyTo.reply(summary, { parse_mode: 'HTML' });
    }
    
    const duration = ((Date.now() - scanStart) / 1000).toFixed(1);
    log(`✓ Scan completed in ${duration}s | Alerts: ${results.alerts.length} | Errors: ${results.errors}`, 'SUCCESS');
    
  } catch (error) {
    log(`Scan failed: ${error.message}`, 'ERROR');
    if (replyTo) {
      await replyTo.reply(`❌ Scan failed: ${error.message}`);
    }
  } finally {
    STATE.isScanning = false;
    log(`${'='.repeat(50)}\n`, 'INFO');
  }
};

const formatScanSummary = (results) => {
  let message = `<b>📊 SCAN SUMMARY</b>\n`;
  message += `<b>Time:</b> ${formatTime()}\n\n`;
  
  if (results.stocks.length > 0) {
    message += `<b>📈 STOCKS</b>\n`;
    results.stocks.forEach(s => {
      message += `• ${s.symbol}: $${s.price.toFixed(2)} ${formatChange(s.changePercent)}\n`;
    });
    message += '\n';
  }
  
  if (results.crypto.length > 0) {
    message += `<b>₿ CRYPTO</b>\n`;
    results.crypto.forEach(c => {
      message += `• ${c.symbol}: $${c.price.toFixed(2)} ${formatChange(c.changePercent)}\n`;
    });
    message += '\n';
  }
  
  message += `<b>Alerts:</b> ${results.alerts.length}\n`;
  message += `<b>Errors:</b> ${results.errors}`;
  
  return message;
};

// ================================================================
// BOT COMMANDS - FIXED
// ================================================================

// Start command with keyboard buttons
bot.start(async (ctx) => {
  log(`User ${ctx.from.id} (${ctx.from.username || 'unknown'}) sent /start`, 'COMMAND');
  
  const message = `🤖 <b>Intelligence Room Bot</b>
ברוך הבא למערכת ניטור השווקים המקצועית שלך!

<b>🎯 נכסים במעקב:</b>
📈 מניות: ${CONFIG.WATCHLIST.stocks.join(', ')}
₿ קריפטו: ${CONFIG.WATCHLIST.crypto.join(', ')}

<b>⚙️ סף התראות:</b>
🚀 פריצה: +${CONFIG.THRESHOLDS.BREAKOUT}%
📉 ירידה חדה: ${CONFIG.THRESHOLDS.SHARP_DROP}%
📈 מומנטום: +${CONFIG.THRESHOLDS.MOMENTUM}%

לחץ על אחד הכפתורים למטה! 👇`;
  
  // Create keyboard with buttons
  const keyboard = {
    keyboard: [
      [{ text: '🔍 סריקה מיידית' }, { text: '🌅 תדריך בוקר' }],
      [{ text: '📊 סטטוס הבוט' }, { text: '👀 רשימת נכסים' }],
      [{ text: '🔔 הגדרות התראות' }, { text: '⏸ עצור סריקות' }],
      [{ text: '❓ עזרה' }]
    ],
    resize_keyboard: true,
    one_time_keyboard: false
  };
  
  await ctx.reply(message, { 
    parse_mode: 'HTML',
    reply_markup: keyboard
  });
});

// Scan command
bot.command('scan', async (ctx) => {
  log(`User ${ctx.from.id} requested manual scan`, 'COMMAND');
  await ctx.reply('🔍 <b>מתחיל סריקה ידנית...</b>', { parse_mode: 'HTML' });
  await performScan(true, ctx);
});

// Briefing command
bot.command('briefing', async (ctx) => {
  log(`User ${ctx.from.id} requested briefing`, 'COMMAND');
  await ctx.reply('🌅 <b>מכין תדריך בוקר...</b>', { parse_mode: 'HTML' });
  await performScan(true, ctx);
});

// Status command
bot.command('status', async (ctx) => {
  log(`User ${ctx.from.id} requested status`, 'COMMAND');
  
  const uptime = process.uptime();
  const hours = Math.floor(uptime / 3600);
  const minutes = Math.floor((uptime % 3600) / 60);
  
  const message = `<b>🤖 מצב הבוט</b>

<b>⏱ זמן הפעלה:</b> ${hours}h ${minutes}m
<b>📊 סטטיסטיקות:</b>
• סריקות כוללות: ${STATE.stats.totalScans}
• התראות שנשלחו: ${STATE.stats.alertsSent}
• קריאות API: ${STATE.stats.apiCalls}
• גודל Cache: ${STATE.priceCache.size} פריטים

<b>🔔 התראות פעילות:</b>
• פריצה: ${STATE.alertsEnabled.breakout ? '✅' : '❌'}
• ירידה חדה: ${STATE.alertsEnabled.drop ? '✅' : '❌'}
• מומנטום: ${STATE.alertsEnabled.momentum ? '✅' : '❌'}

<b>⏰ סריקה אחרונה:</b> ${STATE.lastScanTime ? formatTime(STATE.lastScanTime) : 'אף פעם'}
<b>🔄 סריקה אוטומטית:</b> ${STATE.scanIntervalId ? '✅ פעיל' : '❌ מופסק'}`;
  
  await ctx.reply(message, { parse_mode: 'HTML' });
});

// Toggle command
bot.command('toggle', async (ctx) => {
  log(`User ${ctx.from.id} used toggle command`, 'COMMAND');
  
  const args = ctx.message.text.split(' ').slice(1);
  
  if (args.length === 0) {
    const message = `<b>🔔 הפעלה/כיבוי התראות</b>

מצב נוכחי:
• פריצה: ${STATE.alertsEnabled.breakout ? '✅' : '❌'}
• ירידה: ${STATE.alertsEnabled.drop ? '✅' : '❌'}
• מומנטום: ${STATE.alertsEnabled.momentum ? '✅' : '❌'}

שימוש:
/toggle breakout
/toggle drop
/toggle momentum
/toggle all`;
    await ctx.reply(message, { parse_mode: 'HTML' });
    return;
  }
  
  const type = args[0].toLowerCase();
  
  if (type === 'all') {
    const newState = !STATE.alertsEnabled.breakout;
    STATE.alertsEnabled.breakout = newState;
    STATE.alertsEnabled.drop = newState;
    STATE.alertsEnabled.momentum = newState;
    await ctx.reply(`כל ההתראות ${newState ? 'הופעלו ✅' : 'כובו ❌'}`, { parse_mode: 'HTML' });
  } else if (STATE.alertsEnabled.hasOwnProperty(type)) {
    STATE.alertsEnabled[type] = !STATE.alertsEnabled[type];
    await ctx.reply(`התראות ${type} ${STATE.alertsEnabled[type] ? 'הופעלו ✅' : 'כובו ❌'}`, { parse_mode: 'HTML' });
  } else {
    await ctx.reply('❌ סוג התראה לא תקין. השתמש: breakout, drop, momentum, או all');
  }
});

// Watchlist command
bot.command('watchlist', async (ctx) => {
  log(`User ${ctx.from.id} requested watchlist`, 'COMMAND');
  
  const message = `<b>👀 רשימת נכסים</b>

<b>📈 מניות (${CONFIG.WATCHLIST.stocks.length}):</b>
${CONFIG.WATCHLIST.stocks.map(s => `• ${s}`).join('\n')}

<b>₿ קריפטו (${CONFIG.WATCHLIST.crypto.length}):</b>
${CONFIG.WATCHLIST.crypto.map(c => `• ${c}`).join('\n')}

<b>סה"כ נכסים:</b> ${CONFIG.WATCHLIST.stocks.length + CONFIG.WATCHLIST.crypto.length}`;
  
  await ctx.reply(message, { parse_mode: 'HTML' });
});

// Stop command
bot.command('stop', async (ctx) => {
  log(`User ${ctx.from.id} requested stop`, 'COMMAND');
  
  if (STATE.scanIntervalId) {
    clearInterval(STATE.scanIntervalId);
    STATE.scanIntervalId = null;
    await ctx.reply('⏸ <b>סריקה אוטומטית הופסקה</b>', { parse_mode: 'HTML' });
    log('Auto-scan stopped by user', 'WARNING');
  } else {
    await ctx.reply('ℹ️ הסריקה האוטומטית לא פועלת');
  }
});

// Help command
bot.help((ctx) => {
  ctx.reply('שלח /start כדי לראות את כל הפקודות');
});

// Handle all text messages (for debugging and button clicks)
bot.on('text', (ctx) => {
  const text = ctx.message.text;
  log(`Received text: "${text}" from ${ctx.from.id}`, 'INFO');
  
  // Handle button clicks
  if (text === '🔍 סריקה מיידית') {
    ctx.reply('🔍 <b>מתחיל סריקה ידנית...</b>', { parse_mode: 'HTML' });
    performScan(true, ctx);
  }
  else if (text === '🌅 תדריך בוקר') {
    ctx.reply('🌅 <b>מכין תדריך בוקר...</b>', { parse_mode: 'HTML' });
    performScan(true, ctx);
  }
  else if (text === '📊 סטטוס הבוט') {
    const uptime = process.uptime();
    const hours = Math.floor(uptime / 3600);
    const minutes = Math.floor((uptime % 3600) / 60);
    
    const message = `<b>🤖 מצב הבוט</b>

<b>⏱ זמן הפעלה:</b> ${hours}h ${minutes}m
<b>📊 סטטיסטיקות:</b>
• סריקות כוללות: ${STATE.stats.totalScans}
• התראות שנשלחו: ${STATE.stats.alertsSent}
• קריאות API: ${STATE.stats.apiCalls}
• גודל Cache: ${STATE.priceCache.size} פריטים

<b>🔔 התראות פעילות:</b>
• פריצה: ${STATE.alertsEnabled.breakout ? '✅' : '❌'}
• ירידה חדה: ${STATE.alertsEnabled.drop ? '✅' : '❌'}
• מומנטום: ${STATE.alertsEnabled.momentum ? '✅' : '❌'}

<b>⏰ סריקה אחרונה:</b> ${STATE.lastScanTime ? formatTime(STATE.lastScanTime) : 'אף פעם'}
<b>🔄 סריקה אוטומטית:</b> ${STATE.scanIntervalId ? '✅ פעיל' : '❌ מופסק'}`;
    
    ctx.reply(message, { parse_mode: 'HTML' });
  }
  else if (text === '👀 רשימת נכסים') {
    const message = `<b>👀 רשימת נכסים</b>

<b>📈 מניות (${CONFIG.WATCHLIST.stocks.length}):</b>
${CONFIG.WATCHLIST.stocks.map(s => `• ${s}`).join('\n')}

<b>₿ קריפטו (${CONFIG.WATCHLIST.crypto.length}):</b>
${CONFIG.WATCHLIST.crypto.map(c => `• ${c}`).join('\n')}

<b>סה"כ נכסים:</b> ${CONFIG.WATCHLIST.stocks.length + CONFIG.WATCHLIST.crypto.length}`;
    
    ctx.reply(message, { parse_mode: 'HTML' });
  }
  else if (text === '🔔 הגדרות התראות') {
    const keyboard = {
      keyboard: [
        [{ text: '🚀 פריצה ON/OFF' }, { text: '📉 ירידה ON/OFF' }],
        [{ text: '📈 מומנטום ON/OFF' }, { text: '🔄 הכל ON/OFF' }],
        [{ text: '🔙 חזור לתפריט' }]
      ],
      resize_keyboard: true
    };
    
    const message = `<b>🔔 הגדרות התראות</b>

מצב נוכחי:
• 🚀 פריצה (+3%): ${STATE.alertsEnabled.breakout ? '✅' : '❌'}
• 📉 ירידה (-3%): ${STATE.alertsEnabled.drop ? '✅' : '❌'}
• 📈 מומנטום (+1.5%): ${STATE.alertsEnabled.momentum ? '✅' : '❌'}

לחץ על כפתור כדי להחליף מצב:`;
    
    ctx.reply(message, { 
      parse_mode: 'HTML',
      reply_markup: keyboard
    });
  }
  else if (text === '🚀 פריצה ON/OFF') {
    STATE.alertsEnabled.breakout = !STATE.alertsEnabled.breakout;
    ctx.reply(`🚀 התראות פריצה ${STATE.alertsEnabled.breakout ? 'הופעלו ✅' : 'כובו ❌'}`, { parse_mode: 'HTML' });
  }
  else if (text === '📉 ירידה ON/OFF') {
    STATE.alertsEnabled.drop = !STATE.alertsEnabled.drop;
    ctx.reply(`📉 התראות ירידה ${STATE.alertsEnabled.drop ? 'הופעלו ✅' : 'כובו ❌'}`, { parse_mode: 'HTML' });
  }
  else if (text === '📈 מומנטום ON/OFF') {
    STATE.alertsEnabled.momentum = !STATE.alertsEnabled.momentum;
    ctx.reply(`📈 התראות מומנטום ${STATE.alertsEnabled.momentum ? 'הופעלו ✅' : 'כובו ❌'}`, { parse_mode: 'HTML' });
  }
  else if (text === '🔄 הכל ON/OFF') {
    const newState = !STATE.alertsEnabled.breakout;
    STATE.alertsEnabled.breakout = newState;
    STATE.alertsEnabled.drop = newState;
    STATE.alertsEnabled.momentum = newState;
    ctx.reply(`כל ההתראות ${newState ? 'הופעלו ✅' : 'כובו ❌'}`, { parse_mode: 'HTML' });
  }
  else if (text === '⏸ עצור סריקות') {
    if (STATE.scanIntervalId) {
      clearInterval(STATE.scanIntervalId);
      STATE.scanIntervalId = null;
      ctx.reply('⏸ <b>סריקה אוטומטית הופסקה</b>\n\nכדי להפעיל מחדש, הפעל מחדש את הבוט.', { parse_mode: 'HTML' });
      log('Auto-scan stopped by user', 'WARNING');
    } else {
      ctx.reply('ℹ️ הסריקה האוטומטית לא פועלת');
    }
  }
  else if (text === '🔙 חזור לתפריט' || text === '❓ עזרה') {
    // Return main menu
    const keyboard = {
      keyboard: [
        [{ text: '🔍 סריקה מיידית' }, { text: '🌅 תדריך בוקר' }],
        [{ text: '📊 סטטוס הבוט' }, { text: '👀 רשימת נכסים' }],
        [{ text: '🔔 הגדרות התראות' }, { text: '⏸ עצור סריקות' }],
        [{ text: '❓ עזרה' }]
      ],
      resize_keyboard: true
    };
    
    const message = `<b>📋 תפריט ראשי</b>

בחר פעולה מהכפתורים למטה:

🔍 <b>סריקה מיידית</b> - סרוק את כל הנכסים עכשיו
🌅 <b>תדריך בוקר</b> - קבל סיכום מקיף
📊 <b>סטטוס הבוט</b> - מידע על הבוט
👀 <b>רשימת נכסים</b> - ראה מה במעקב
🔔 <b>הגדרות התראות</b> - נהל התראות
⏸ <b>עצור סריקות</b> - הפסק סריקה אוטומטית

גם אפשר לשלוח פקודות:
/start, /scan, /status, /watchlist`;
    
    ctx.reply(message, { 
      parse_mode: 'HTML',
      reply_markup: keyboard
    });
  }
});

// ================================================================
// ERROR HANDLING
// ================================================================

bot.catch((err, ctx) => {
  log(`Bot error for ${ctx.updateType}: ${err.message}`, 'ERROR');
  console.error(err);
  
  if (ctx && ctx.reply) {
    ctx.reply('❌ אירעה שגיאה. אנא נסה שוב.');
  }
});

process.on('unhandledRejection', (reason, promise) => {
  log(`Unhandled Rejection: ${reason}`, 'ERROR');
  console.error(reason);
});

process.on('uncaughtException', (error) => {
  log(`Uncaught Exception: ${error.message}`, 'ERROR');
  console.error(error);
});

// ================================================================
// STARTUP
// ================================================================

const startBot = async () => {
  try {
    log('Validating configuration...', 'INFO');
    
    if (!CONFIG.BOT_TOKEN) {
      throw new Error('BOT_TOKEN is missing!');
    }
    
    if (!CONFIG.CHAT_ID) {
      throw new Error('CHAT_ID is missing!');
    }
    
    if (!CONFIG.ALPHA_VANTAGE_KEY) {
      throw new Error('ALPHA_VANTAGE_KEY is missing!');
    }
    
    log('Starting bot...', 'INFO');
    
    // Test bot token
    const botInfo = await bot.telegram.getMe();
    log(`Bot connected: @${botInfo.username}`, 'SUCCESS');
    
    // Launch bot
    await bot.launch();
    STATE.botReady = true;
    log('Bot launched successfully!', 'SUCCESS');
    
    // Send startup message
    await sendMessage(CONFIG.CHAT_ID, `🚀 <b>Intelligence Room Bot התחיל!</b>

<b>סטטוס:</b> ✅ מחובר
<b>זמן:</b> ${formatTime()}
<b>נכסים:</b> ${CONFIG.WATCHLIST.stocks.length + CONFIG.WATCHLIST.crypto.length} נכסים במעקב

מוכן לנטר שווקים!
שלח /start לתפריט פקודות.`);
    
    // Start auto-scan
    log(`Starting auto-scan (every ${CONFIG.SCAN_INTERVAL / 60000} minutes)`, 'INFO');
    STATE.scanIntervalId = setInterval(() => {
      performScan(false);
    }, CONFIG.SCAN_INTERVAL);
    
    // First scan after 10 seconds
    setTimeout(() => {
      log('Running first scan...', 'INFO');
      performScan(false);
    }, 10000);
    
    log('\n✅ Bot is ready and waiting for commands!\n', 'SUCCESS');
    
  } catch (error) {
    log(`Failed to start bot: ${error.message}`, 'ERROR');
    console.error(error);
    process.exit(1);
  }
};

// ================================================================
// GRACEFUL SHUTDOWN
// ================================================================

const shutdown = async () => {
  log('\n🛑 Shutting down...', 'WARNING');
  
  if (STATE.scanIntervalId) {
    clearInterval(STATE.scanIntervalId);
  }
  
  if (STATE.botReady) {
    await sendMessage(CONFIG.CHAT_ID, `⏸ <b>Intelligence Room Bot נעצר</b>

<b>זמן:</b> ${formatTime()}
<b>סריקות כוללות:</b> ${STATE.stats.totalScans}
<b>התראות:</b> ${STATE.stats.alertsSent}

הבוט לא מחובר.`);
  }
  
  bot.stop('SIGINT');
  process.exit(0);
};

process.once('SIGINT', shutdown);
process.once('SIGTERM', shutdown);

// ================================================================
// START
// ================================================================

startBot();
