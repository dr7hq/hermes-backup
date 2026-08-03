#!/usr/bin/env python3
"""ربات استخراج اطلاعات لینک و ویدئو - با لاگ کاربران"""

import os, re, json, logging, urllib.request, sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8633608471:AAHmqmb4u5sHGE1GyTsxvOIzJps-voyyFBM"
logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Database for user stats
DB_PATH = "/data/workspace/summarizer_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            start_count INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_type TEXT,
            content_preview TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_user(user_id, username, first_name, msg_type="start", content=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Update or insert user stats
    c.execute("SELECT user_id FROM user_stats WHERE user_id = ?", (user_id,))
    if c.fetchone():
        if msg_type == "start":
            c.execute("UPDATE user_stats SET start_count = start_count + 1, last_seen = CURRENT_TIMESTAMP, username = ?, first_name = ? WHERE user_id = ?",
                     (username, first_name, user_id))
        else:
            c.execute("UPDATE user_stats SET message_count = message_count + 1, last_seen = CURRENT_TIMESTAMP, username = ?, first_name = ? WHERE user_id = ?",
                     (username, first_name, user_id))
    else:
        c.execute("INSERT INTO user_stats (user_id, username, first_name, start_count, message_count) VALUES (?, ?, ?, ?, ?)",
                 (user_id, username, first_name, 1 if msg_type == "start" else 0, 0 if msg_type == "start" else 1))
    
    # Log message
    c.execute("INSERT INTO message_log (user_id, message_type, content_preview) VALUES (?, ?, ?)",
             (user_id, msg_type, content[:100]))
    
    conn.commit()
    conn.close()


def extract_youtube(url):
    vid = None
    m = re.search(r'(?:youtube\.com/watch\?.*?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})', url)
    if m: vid = m.group(1)
    if not vid: vid = url.strip()
    if len(vid) != 11: return None

    info = {"title":"","channel":"","description":"","duration":"","chapters":[]}

    # oEmbed
    try:
        req = urllib.request.Request(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json", headers={"User-Agent":"Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        oe = json.loads(resp.read())
        info["title"] = oe.get("title","")
        info["channel"] = oe.get("author_name","")
    except: pass

    # scraping
    try:
        req = urllib.request.Request(f"https://www.youtube.com/watch?v={vid}", headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="ignore")

        # description
        dm = re.search(r'"attributedDescription":\{"content":"(.*?)"', html)
        if dm:
            info["description"] = dm.group(1).replace("\\n","\n").replace("\\t","\t")[:3000]

        # duration
        dur = re.search(r'"lengthSeconds":"(\d+)"', html)
        if dur:
            s = int(dur.group(1))
            info["duration"] = f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}" if s>=3600 else f"{s//60}:{s%60:02d}"

        # chapters
        for title, ms in re.findall(r'"chapterRenderer":\{"title":\{"simpleText":"(.*?)"\},"timeRangeStartMillis":(\d+)', html):
            s = int(ms)//1000
            info["chapters"].append({"title":title,"time":f"{s//60}:{s%60:02d}"})
    except Exception as e:
        logger.error(f"scraping: {e}")

    # output
    out = f"📹 عنوان: {info['title']}\n👤 کانال: {info['channel']}"
    if info["duration"]: out += f"\n⏱️ مدت: {info['duration']}"
    if info["description"]: out += f"\n\n📝 توضیحات:\n{info['description']}"
    if info["chapters"]:
        out += "\n\n📂 فصل‌ها:\n" + "\n".join([f"• {c['time']} - {c['title']}" for c in info["chapters"][:30]])
    return out


def extract_web(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="ignore")
        text = re.sub(r"<script[^>]*>.*?</script>","",html,flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>","",text,flags=re.DOTALL)
        text = re.sub(r"<[^>]+>"," ",text)
        return re.sub(r"\s+"," ",text).strip()[:5000]
    except: return None


async def start(update, context):
    user = update.effective_user
    log_user(user.id, user.username, user.first_name, "start")
    
    await update.message.reply_text(
        "🤖 ربات استخراج لینک و ویدئو\n\n"
        "📌 لینک بفرست تا اطلاعاتشو استخراج کنم:\n"
        "• یوتیوب: عنوان + کانال + توضیحات + فصل‌ها\n"
        "• وبسایت: محتوای صفحه"
    )


async def handle_msg(update, context):
    user = update.effective_user
    text = update.message.text.strip()
    
    log_user(user.id, user.username, user.first_name, "message", text)
    
    if "youtube.com" in text or "youtu.be" in text:
        await update.message.reply_text("⏳ در حال استخراج اطلاعات ویدئو...")
        content = extract_youtube(text)
        if content:
            await update.message.reply_text(content)
        else:
            await update.message.reply_text("❌ نتونستم اطلاعات ویدئو رو استخراج کنم.")

    elif text.startswith("http"):
        await update.message.reply_text("⏳ در حال استخراج محتوای صفحه...")
        content = extract_web(text)
        if content:
            await update.message.reply_text(f"📎 محتوای صفحه:\n{'='*30}\n\n{content}")
        else:
            await update.message.reply_text("❌ نتونستم محتوا رو بخونم.")

    else:
        await update.message.reply_text("❌ لطفاً یه لینک بفرست (یوتیوب یا وبسایت).")


def main():
    init_db()
    print("🤖 ربات استخراج روشن شد!")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
