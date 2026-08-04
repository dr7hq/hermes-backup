#!/usr/bin/env python3
"""ربات استخراج و خلاصه‌سازی لینک/ویدیو - با Nemotron 3 Ultra (رایگان)"""

import os, re, json, logging, urllib.request, sqlite3, subprocess, tempfile
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ============================================
# CONFIGURATION - Nemotron 3 Ultra (FREE)
# ============================================
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DB_PATH = "/data/workspace/summarizer_bot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# ============================================
# MESSAGE TRUNCATION (Telegram limit: 4096 chars)
# ============================================
def truncate_message(text, max_len=4000):
    """کوتاه کردن پیام برای تلگرام"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n... (ادامه محتوا کوتاه شد)"


# ============================================
# DATABASE
# ============================================
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS video_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            video_id TEXT,
            video_url TEXT,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_user(user_id, username, first_name, msg_type="start", content=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
    c.execute("INSERT INTO message_log (user_id, message_type, content_preview) VALUES (?, ?, ?)",
             (user_id, msg_type, content[:100]))
    conn.commit()
    conn.close()

def save_summary(user_id, video_id, video_url, summary):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO video_summaries (user_id, video_id, video_url, summary) VALUES (?, ?, ?, ?)",
             (user_id, video_id, video_url, summary))
    conn.commit()
    conn.close()

# ============================================
# YOUTUBE EXTRACTION
# ============================================
def extract_video_id(url):
    """Extract 11-char video ID from YouTube URL"""
    patterns = [
        r'(?:youtube\.com/watch\?.*?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*?v=([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None

def get_youtube_info(video_id):
    """Get video info via oEmbed and scraping"""
    info = {"title": "", "channel": "", "description": "", "duration": "", "chapters": []}
    
    # oEmbed for title + channel
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        oe = json.loads(resp.read())
        info["title"] = oe.get("title", "")
        info["channel"] = oe.get("author_name", "")
    except Exception as e:
        logger.warning(f"oEmbed failed: {e}")
    
    # Scraping for description, duration, chapters
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="ignore")
        
        # Description
        dm = re.search(r'"attributedDescription":\{"content":"(.*?)"', html)
        if dm:
            info["description"] = dm.group(1).replace("\\n", "\n").replace("\\t", "\t")[:5000]
        
        # Duration
        dur = re.search(r'"lengthSeconds":"(\d+)"', html)
        if dur:
            s = int(dur.group(1))
            info["duration"] = f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}" if s >= 3600 else f"{s//60}:{s%60:02d}"
        
        # Chapters
        for title, ms in re.findall(r'"chapterRenderer":\{"title":\{"simpleText":"(.*?)"\},"timeRangeStartMillis":(\d+)', html):
            s = int(ms) // 1000
            info["chapters"].append({"title": title, "time": f"{s//60}:{s%60:02d}"})
    except Exception as e:
        logger.warning(f"Scraping failed: {e}")
    
    return info

def get_youtube_transcript(video_id):
    """Get transcript using yt-dlp"""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-sub",
                "--sub-lang", "en,fa,ar",
                "--sub-format", "vtt",
                "--no-playlist",
                "-o", f"{tmpdir}/%(id)s.%(ext)s",
                f"https://www.youtube.com/watch?v={video_id}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Find subtitle file
                for lang in ["en", "fa", "ar", "en-US"]:
                    sub_file = f"{tmpdir}/{video_id}.{lang}.vtt"
                    if os.path.exists(sub_file):
                        with open(sub_file, "r", encoding="utf-8") as f:
                            content = f.read()
                        # Parse VTT
                        lines = []
                        for line in content.split("\n"):
                            line = line.strip()
                            if line and not line.startswith("WEBVTT") and not "-->" in line and not line.isdigit():
                                lines.append(line)
                        return " ".join(lines)[:10000]
    except Exception as e:
        logger.warning(f"Transcript extraction failed: {e}")
    return None

# ============================================
# AI SUMMARIZATION (Nemotron 3 Ultra - FREE)
# ============================================
def summarize_with_ai(content, video_info):
    """Summarize video content using Nemotron 3 Ultra"""
    if not content or len(content.strip()) < 50:
        return None
    
    prompt = f"""شما یک دستیار هوشمند و تحلیل‌گر ارشد محتوا هستید. وظیفه شما بررسی دقیق محتوای زیر و ارائه یک گزارش جامع و مفید به زبان فارسی است.

مشخصات ویدیو:
- عنوان: {video_info.get('title', 'نامشخص')}
- کانال: {video_info.get('channel', 'نامشخص')}
- مدت زمان: {video_info.get('duration', 'نامشخص')}

محتوای ویدیو (زیرنویس/توضیحات):
{content[:9000]}

لطفاً گزارش خود را با رعایت ساختار زیر به فارسی بنویسید:

۱. **🎯 جوهره ویدیو (خلاصه مدیریتی)**: 
در دو یا سه جمله کوتاه، پیام اصلی و هدف اصلی این ویدیو را توضیح دهید.

۲. **🔑 سرفصل‌ها و نکات استراتژیک**: 
مهم‌ترین مفاهیم، داده‌ها یا ادعاهای مطرح شده را به صورت لیست (بولت‌پوینت) استخراج کنید.

۳. **💡 تحلیل و ارزش افزوده**: 
چه چیزی این ویدیو را ارزشمند می‌کند؟ پیام نهایی برای مخاطب چیست؟

۴. **✅ نتیجه‌گیری نهایی**: 
یک جمع‌بندی کوتاه از کل بحث.

نکات مهم:
- از جملات کوتاه و گویا استفاده کنید.
- لحن گزارش باید حرفه‌ای و در عین حال صمیمی باشد.

گزارش تحلیلی:"""

    try:
        data = json.dumps({
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": "You are a senior content analyst. Produce professional, structured, and insightful Persian reports from video transcripts."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2500,
            "temperature": 0.5
        }).encode()
        
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://t.me/videoshahbot",
                "X-Title": "VideoShahBot"
            }
        )
        
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read())
        
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"AI summarization failed: {e}")
    return None

# ============================================
# WEB EXTRACTION
# ============================================
def extract_web(url):
    """استخراج محتوای صفحه وب با پشتیبانی از صفحات پیچیده"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        })
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="ignore")
        
        # استخراج عنوان
        title = ""
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        
        # حذف script و style
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL)
        text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL)
        
        # تلاش برای استخراج محتوای اصلی (article, main, content)
        article = ""
        for tag in ['article', 'main', 'div.content', 'div.post', 'div.entry-content']:
            if tag.startswith('div.'):
                pattern = f'<div[^>]*class="[^"]*{tag.split(".")[1]}[^"]*"[^>]*>(.*?)</div>'
            else:
                pattern = f'<{tag}[^>]*>(.*?)</{tag}>'
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                article = match.group(1)
                break
        
        if not article:
            # اگه محتوای اصلی پیدا نشد، از body استفاده کن
            body_match = re.search(r'<body[^>]*>(.*?)</body>', text, re.DOTALL)
            if body_match:
                article = body_match.group(1)
            else:
                article = text
        
        # حذف تگ‌های HTML
        article = re.sub(r"<[^>]+>", " ", article)
        article = re.sub(r"&[a-zA-Z]+;", " ", article)
        article = re.sub(r"\s+", " ", article).strip()
        
        # محدود کردن طول
        result = article[:8000]
        
        # اضافه کردن عنوان اگه وجود داشته باشه
        if title:
            result = f"📌 {title}\n\n{result}"
        
        return result
    except Exception as e:
        logger.error(f"Web extraction failed: {e}")
        return None

# ============================================
# TELEGRAM HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user.id, user.username, user.first_name, "start")
    
    await update.message.reply_text(
        "🤖 <b>ربات استخراج و خلاصه‌سازی هوشمند</b>\n\n"
        "📌 <b>قابلیت‌ها:</b>\n"
        "• <b>یوتیوب:</b> عنوان + کانال + توضیحات + فصل‌ها\n"
        "• <b>🤖 خلاصه هوشمند:</b> با Nemotron 3 Ultra\n"
        "• <b>📝 زیرنویس:</b> استخراج زیرنویس ویدیو\n"
        "• <b>وبسایت:</b> محتوای صفحه\n"
        "• <b>هر لینک:</b> تحلیل و استخراج\n\n"
        "💡 <b>کافیه لینک بفرستی!</b>\n\n"
        "⚡ قدرت گرفته از <b>Nemotron 3 Ultra</b> (رایگان)",
        parse_mode="HTML"
    )

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    log_user(user.id, user.username, user.first_name, "message", text)
    
    # YouTube
    if "youtube.com" in text or "youtu.be" in text:
        await update.message.reply_text("⏳ در حال استخراج اطلاعات ویدئو...")
        
        video_id = extract_video_id(text)
        if not video_id:
            await update.message.reply_text("❌ لینک یوتیوب معتبر نیست.")
            return
        
        # Get video info
        info = get_youtube_info(video_id)
        
        if not info["title"]:
            await update.message.reply_text("❌ نتونستم اطلاعات ویدئو رو استخراج کنم.")
            return
        
        # Build basic response
        out = f"📹 <b>عنوان:</b> {info['title']}\n"
        out += f"👤 <b>کانال:</b> {info['channel']}\n"
        if info["duration"]:
            out += f"⏱️ <b>مدت:</b> {info['duration']}\n"
        if info["description"]:
            out += f"\n📝 <b>توضیحات:</b>\n{info['description'][:1500]}"
        if info["chapters"]:
            out += "\n\n📂 <b>فصل‌ها:</b>\n"
            out += "\n".join([f"• {c['time']} - {c['title']}" for c in info["chapters"][:15]])
        
        await update.message.reply_text(out, parse_mode="HTML")
        
        # Get transcript and summarize
        await update.message.reply_text("🤖 در حال خلاصه‌سازی با Nemotron 3 Ultra...")
        
        transcript = get_youtube_transcript(video_id)
        content_for_summary = transcript or info["description"]
        
        if content_for_summary and len(content_for_summary) > 100:
            summary = summarize_with_ai(content_for_summary, info)
            if summary:
                # ذخیره محتوا برای دکمه‌ها
                web_content_store[user.id] = summary
                
                # ایجاد دکمه‌های inline
                keyboard = [[
                    InlineKeyboardButton("🔄 ترجمه به فارسی", callback_data="translate"),
                    InlineKeyboardButton("📄 دانلود فایل", callback_data="download"),
                    InlineKeyboardButton("📋 کپی", callback_data="copy")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"🎯 <b>گزارش تحلیلی:</b>\n\n{truncate_message(summary)}",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
                save_summary(user.id, video_id, text, summary)
            else:
                await update.message.reply_text("⚠️ خلاصه‌سازی نشد، ولی اطلاعات استخراج شد.")
        else:
            await update.message.reply_text("ℹ️ محتوای قابل خلاصه‌سازی یافت نشد (زیرنویس/توضیحات).")
    
    # Web links
    elif text.startswith("http"):
        await update.message.reply_text("⏳ در حال استخراج محتوای صفحه...")
        content = extract_web(text)
        if content:
            await update.message.reply_text(f"📎 <b>محتوای صفحه:</b>\n{'='*30}\n\n{truncate_message(content)}", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ نتونستم محتوا رو بخونم.")
    
    # Invalid
    else:
        await update.message.reply_text("❌ لطفاً یه لینک بفرست (یوتیوب یا وبسایت).")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    user = update.effective_user
    if user.id != 8848298889:  # Only admin
        await update.message.reply_text("❌ فقط ادمین می‌تونه آمار ببینه.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM user_stats")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM message_log")
    total_messages = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM video_summaries")
    total_summaries = c.fetchone()[0]
    
    c.execute("SELECT username, first_name, start_count, message_count FROM user_stats ORDER BY last_seen DESC LIMIT 10")
    recent_users = c.fetchall()
    
    conn.close()
    
    out = f"📊 <b>آمار ربات</b>\n\n"
    out += f"👥 کاربران: {total_users}\n"
    out += f"💬 پیام‌ها: {total_messages}\n"
    out += f"🎯 خلاصه‌ها: {total_summaries}\n\n"
    out += f"👤 <b>کاربران اخیر:</b>\n"
    for u in recent_users:
        out += f"• @{u[0]} ({u[1]}) - /start: {u[2]}, msg: {u[3]}\n"
    
    await update.message.reply_text(out, parse_mode="HTML")

# ============================================
# MAIN
# ============================================
def main():
    init_db()
    print("🤖 ربات استخراج و خلاصه‌سازی روشن شد!")
    print(f"🧠 مدل: {OPENROUTER_MODEL}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()