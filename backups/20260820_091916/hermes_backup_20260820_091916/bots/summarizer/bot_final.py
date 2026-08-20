#!/usr/bin/env python3
"""ربات استخراج و خلاصه‌سازی هوشمند - @videoshahbot
Model: Nemotron 3 Ultra (FREE via OpenRouter)
"""

import os, re, json, logging, urllib.request, sqlite3, subprocess, tempfile, asyncio, traceback
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ============================================
# CONFIGURATION
# ============================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8633608471:AAHmqmb4u5sHGE1GyTsxvOIzJps-voyyFBM")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "«redacted»")
OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DB_PATH = os.environ.get("DB_PATH", "/data/workspace/summarizer_bot.db")
ADMIN_USER_ID = 8848298889

# Rate limiting
RATE_LIMIT = 5  # max requests per minute per user
user_requests = {}  # user_id -> [timestamps]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# DATABASE (Context Manager - No Leaks)
# ============================================
class Database:
    """SQLite database with proper connection management."""
    
    def __init__(self, path: str):
        self.path = path
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    start_count INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS message_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message_type TEXT,
                    content_preview TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS video_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    video_id TEXT,
                    video_url TEXT,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS web_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    url TEXT,
                    content TEXT,
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
    
    def log_user(self, user_id, username, first_name, msg_type="start", content=""):
        with sqlite3.connect(self.path) as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM user_stats WHERE user_id = ?", (user_id,))
            if c.fetchone():
                if msg_type == "start":
                    c.execute("""UPDATE user_stats SET start_count = start_count + 1,
                        last_seen = CURRENT_TIMESTAMP, username = ?, first_name = ?
                        WHERE user_id = ?""", (username, first_name, user_id))
                else:
                    c.execute("""UPDATE user_stats SET message_count = message_count + 1,
                        last_seen = CURRENT_TIMESTAMP, username = ?, first_name = ?
                        WHERE user_id = ?""", (username, first_name, user_id))
            else:
                c.execute("""INSERT INTO user_stats (user_id, username, first_name, start_count, message_count)
                    VALUES (?, ?, ?, ?, ?)""",
                    (user_id, username, first_name, 1 if msg_type == "start" else 0,
                     0 if msg_type == "start" else 1))
            c.execute("INSERT INTO message_log (user_id, message_type, content_preview) VALUES (?, ?, ?)",
                      (user_id, msg_type, content[:100]))
    
    def save_summary(self, user_id, video_id, video_url, summary):
        with sqlite3.connect(self.path) as conn:
            conn.execute("""INSERT INTO video_summaries (user_id, video_id, video_url, summary)
                VALUES (?, ?, ?, ?)""", (user_id, video_id, video_url, summary))
    
    def save_web_content(self, user_id, url, content, language="en"):
        with sqlite3.connect(self.path) as conn:
            conn.execute("""INSERT INTO web_content (user_id, url, content, language)
                VALUES (?, ?, ?, ?)""", (user_id, url, content, language))
    
    def get_web_content(self, user_id, limit=5):
        with sqlite3.connect(self.path) as conn:
            c = conn.cursor()
            c.execute("""SELECT id, url, content, language, created_at
                FROM web_content WHERE user_id = ? ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit))
            return c.fetchall()
    
    def delete_web_content(self, content_id):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM web_content WHERE id = ?", (content_id,))
    
    def get_stats(self):
        with sqlite3.connect(self.path) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM user_stats")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM message_log")
            total_messages = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM video_summaries")
            total_summaries = c.fetchone()[0]
            c.execute("""SELECT username, first_name, start_count, message_count
                FROM user_stats ORDER BY last_seen DESC LIMIT 10""")
            recent_users = c.fetchall()
            return {
                "total_users": total_users,
                "total_messages": total_messages,
                "total_summaries": total_summaries,
                "recent_users": recent_users
            }

db = Database(DB_PATH)

# ============================================
# RATE LIMITING
# ============================================
def check_rate_limit(user_id: int) -> bool:
    """Check if user is within rate limits."""
    now = datetime.now().timestamp()
    if user_id not in user_requests:
        user_requests[user_id] = []
    # Remove old timestamps (older than 60 seconds)
    user_requests[user_id] = [t for t in user_requests[user_id] if now - t < 60]
    if len(user_requests[user_id]) >= RATE_LIMIT:
        return False
    user_requests[user_id].append(now)
    return True

# ============================================
# ERROR NOTIFICATION
# ============================================
_error_bot = None

def set_error_bot(bot):
    global _error_bot
    _error_bot = bot

async def send_error_notification(error_type, error_msg, context_str=""):
    if _error_bot is None:
        return
    try:
        msg = f"🚨 <b>خطای @videoshahbot</b>\n\n"
        msg += f"📌 <b>نوع:</b> {error_type}\n"
        msg += f"❌ <b>خطا:</b> {str(error_msg)[:500]}\n"
        if context_str:
            msg += f"📝 <b>جزئیات:</b> {context_str[:300]}\n"
        msg += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await _error_bot.send_message(chat_id=ADMIN_USER_ID, text=msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")

# ============================================
# YOUTUBE EXTRACTION
# ============================================
def extract_video_id(url):
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
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['fa', 'en'])
        full_text = ""
        for entry in transcript_list:
            seconds = int(entry['start'])
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            full_text += f"[{minutes:02d}:{remaining_seconds:02d}] {entry['text']}\n"
        return full_text
    except Exception as e:
        logger.warning(f"Transcript extraction failed: {e}")
        return None

# ============================================
# WEB EXTRACTION
# ============================================
def extract_web(url):
    try:
        # Method 1: trafilatura
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_links=False, include_tables=True)
                if text and len(text) > 200:
                    return text
        except Exception:
            pass

        # Method 2: BeautifulSoup (Smart Fallback)
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Clean up unwanted elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Try to find the main article content specifically for blog.google and others
        content_containers = [
            soup.find("article"),
            soup.find("main"),
            soup.find("div", class_=lambda x: x and any(c in x.lower() for c in ["post-content", "entry-content", "article-body", "main-content"])),
            soup.find("div", id=lambda x: x and any(i in x.lower() for i in ["content", "main", "article"]))
        ]

        for container in content_containers:
            if container:
                text = container.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return text

        # Last resort: full body text
        return soup.get_text(separator="\n", strip=True)

    except Exception as e:
        logger.error(f"Web extraction failed for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Web extraction failed: {e}")
        asyncio.create_task(send_error_notification("Web Extraction", str(e), f"url: {url[:100]}"))
        return None

# ============================================
# OPENROUTER API CALLS (with retry + rate limit)
# ============================================
def call_openrouter(messages, max_tokens=4000, temperature=0.5):
    """Call OpenRouter API with retry logic."""
    for attempt in range(3):
        try:
            data = json.dumps({
                "model": OPENROUTER_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
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
            
            resp = urllib.request.urlopen(req, timeout=90)
            result = json.loads(resp.read())
            
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"].strip()
            return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"Rate limited, retrying in {2 ** attempt}s...")
                import time
                time.sleep(2 ** attempt)
                continue
            elif e.code >= 500:
                logger.warning(f"Server error {e.code}, retrying...")
                import time
                time.sleep(2 ** attempt)
                continue
            else:
                logger.error(f"OpenRouter API error: {e}")
                return None
        except Exception as e:
            logger.error(f"OpenRouter call failed: {e}")
            return None
    return None

# ============================================
# TRANSLATION TO PERSIAN
# ============================================
def translate_to_persian(text):
    if not text or len(text.strip()) < 10:
        return text
    
    messages = [
        {"role": "system", "content": "You are a professional translator. Translate English content to fluent, natural Persian."},
        {"role": "user", "content": f"این متن رو به فارسی روون و طبیعی ترجمه کن. فقط ترجمه رو بنویس:\n\n{text[:6000]}"}
    ]
    return call_openrouter(messages, max_tokens=4000, temperature=0.3) or text

# ============================================
# AI SUMMARIZATION
# ============================================
def summarize_with_ai(content, video_info):
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
- از به کار بردن کلمات انگلیسی در متن فارسی خودداری کنید.
- لحن گزارش باید حرفه‌ای و در عین حال صمیمی باشد.

گزارش تحلیلی:"""

    messages = [
        {"role": "system", "content": "You are a senior content analyst. Produce professional, structured, and insightful Persian reports from video transcripts."},
        {"role": "user", "content": prompt}
    ]
    return call_openrouter(messages, max_tokens=2500, temperature=0.5)

# ============================================
# MESSAGE SPLITTING (Telegram 4096 limit)
# ============================================
def split_message(text, max_len=3500):
    if len(text) <= max_len:
        return [text]
    
    messages = []
    paragraphs = text.split("\n")
    current_msg = ""
    
    for paragraph in paragraphs:
        if len(paragraph) > max_len:
            if current_msg:
                messages.append(current_msg.strip())
                current_msg = ""
            while len(paragraph) > max_len:
                split_pos = paragraph.rfind(" ", 0, max_len)
                if split_pos <= 0:
                    split_pos = max_len
                messages.append(paragraph[:split_pos].strip())
                paragraph = paragraph[split_pos:].lstrip()
            if paragraph.strip():
                current_msg = paragraph + "\n"
        elif len(current_msg) + len(paragraph) + 2 <= max_len:
            current_msg += paragraph + "\n\n"
        else:
            if current_msg.strip():
                messages.append(current_msg.strip())
            current_msg = paragraph + "\n\n"
    
    if current_msg.strip():
        messages.append(current_msg.strip())
    
    return messages if messages else [text[:max_len]]

# ============================================
# HANDLERS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.log_user(user.id, user.username, user.first_name, "start")
    
    await update.message.reply_text(
        "🤖 <b>ربات استخراج و خلاصه‌سازی هوشمند</b>\n\n"
        "📌 <b>قابلیت‌ها:</b>\n"
        "• <b>یوتیوب:</b> عنوان + کانال + توضیحات + فصل‌ها\n"
        "• <b>🤖 خلاصه هوشمند:</b> با Nemotron 3 Ultra\n"
        "• <b>📝 زیرنویس:</b> استخراج زیرنویس ویدیو\n"
        "• <b>🌐 وبسایت:</b> محتوای صفحه کامل\n"
        "• <b>📄 خروجی .md:</b> فایل‌های مارک‌داون\n"
        "• <b>🔄 ترجمه:</b> ترجمه خودکار به فارسی\n\n"
        "💡 <b>کافیه لینک بفرستی!</b>\n\n"
        "⚡ قدرت گرفته از <b>Nemotron 3 Ultra</b> (رایگان)",
        parse_mode="HTML"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 <b>راهنمای ربات</b>\n\n"
        "<b>دستورات:</b>\n"
        "/start - شروع مجدد\n"
        "/stats - آمار ربات (ادمین)\n"
        "/help - این راهنما\n\n"
        "<b>نحوه استفاده:</b>\n"
        "• لینک یوتیوب بفرستید\n"
        "• لینک وبسایت بفرستید\n"
        "• از دکمه‌های inline استفاده کنید",
        parse_mode="HTML"
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ فقط ادمین می‌تونه آمار ببینه.")
        return
    
    stats = db.get_stats()
    out = f"📊 <b>آمار ربات</b>\n\n"
    out += f"👥 کاربران: {stats['total_users']}\n"
    out += f"💬 پیام‌ها: {stats['total_messages']}\n"
    out += f"🎯 خلاصه‌ها: {stats['total_summaries']}\n\n"
    out += f"👤 <b>کاربران اخیر:</b>\n"
    for u in stats['recent_users']:
        out += f"• @{u[0]} ({u[1]}) - /start: {u[2]}, msg: {u[3]}\n"
    
    await update.message.reply_text(out, parse_mode="HTML")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "summarize":
        content_list = db.get_web_content(user_id, limit=1)
        if not content_list:
            await query.edit_message_text("❌ محتوا یافت نشد. لطفاً دوباره لینک بفرستید.")
            return
        
        content = content_list[0][2]
        url = content_list[0][1]
        is_youtube = "youtube.com" in url or "youtu.be" in url
        
        await query.edit_message_text("🤖 در حال خلاصه‌سازی با Nemotron 3 Ultra...")
        
        if is_youtube:
            video_id = extract_video_id(url)
            info = get_youtube_info(video_id) if video_id else {"title": "نامشخص", "channel": "نامشخص", "duration": "نامشخص"}
            summary = summarize_with_ai(content, info)
        else:
            summary = summarize_with_ai(content, {"title": url, "channel": "", "duration": ""})
        
        if summary:
            db.save_summary(user_id, "summary_" + url[-20:], url, summary)
            keyboard = [[
                InlineKeyboardButton("🎯 خلاصه دقیق", callback_data="summarize"),
                InlineKeyboardButton("📄 فایل ترجمه شده", callback_data="translate_file")
            ],[
                InlineKeyboardButton("📄 دانلود .md", callback_data="download_raw"),
                InlineKeyboardButton("📋 کپی", callback_data="copy")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            messages = split_message(f"🎯 <b>گزارش تحلیلی:</b>\n\n{summary}")
            for i, msg in enumerate(messages):
                if i == len(messages) - 1:
                    await context.bot.send_message(chat_id=query.message.chat_id, text=msg, parse_mode="HTML", reply_markup=reply_markup)
                else:
                    await context.bot.send_message(chat_id=query.message.chat_id, text=msg, parse_mode="HTML")
                    await asyncio.sleep(0.5)
        else:
            await query.edit_message_text("⚠️ خلاصه‌سازی انجام نشد. محتوا کافی نیست.")
    
    elif data == "translate_file":
        content_list = db.get_web_content(user_id, limit=1)
        if not content_list:
            await query.edit_message_text("❌ محتوا یافت نشد.")
            return
        
        content = content_list[0][2]
        url = content_list[0][1]
        
        await query.edit_message_text("🔄 در حال ترجمه...")
        
        translated = translate_to_persian(content)
        if translated:
            is_youtube = "youtube.com" in url or "youtu.be" in url
            filename = "video_translated.md" if is_youtube else "page_translated.md"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                f.write(translated)
                temp_path = f.name
            
            with open(temp_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    filename=filename,
                    caption="📄 فایل ترجمه شده"
                )
            os.unlink(temp_path)
        else:
            await query.edit_message_text("❌ ترجمه انجام نشد.")
    
    elif data == "download_raw":
        content_list = db.get_web_content(user_id, limit=1)
        if not content_list:
            await query.edit_message_text("❌ محتوا یافت نشد.")
            return
        
        content = content_list[0][2]
        url = content_list[0][1]
        is_youtube = "youtube.com" in url or "youtu.be" in url
        filename = "video_content.md" if is_youtube else "page_content.md"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        
        with open(temp_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f,
                filename=filename,
                caption="📄 فایل محتوای اصلی"
            )
        os.unlink(temp_path)
    
    elif data == "copy":
        await query.answer("✅ محتوا آماده کپی شد!", show_alert=True)

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        text = update.message.text.strip()
        
        # Rate limit check
        if not check_rate_limit(user.id):
            await update.message.reply_text(
                "⚠️ <b>محدودیت درخواست</b>\n\n"
                "شما در یک دقیقه گذشته درخواست زیادی ارسال کردید.\n"
                "لطفاً چند لحظه صبر کنید.",
                parse_mode="HTML"
            )
            return
        
        db.log_user(user.id, user.username, user.first_name, "message", text)
        
        # YouTube
        if "youtube.com" in text or "youtu.be" in text:
            await update.message.reply_text("⏳ در حال استخراج اطلاعات ویدئو...")
            
            video_id = extract_video_id(text)
            if not video_id:
                await update.message.reply_text("❌ لینک یوتیوب معتبر نیست.")
                return
            
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
            
            # Get transcript (save for later use)
            transcript = get_youtube_transcript(video_id)
            content_for_use = transcript or info["description"]
            
            # Save raw content for buttons
            if content_for_use and len(content_for_use) > 50:
                db.save_web_content(user.id, text, content_for_use, "en")
            
            # Show action buttons
            keyboard = [[
                InlineKeyboardButton("🎯 خلاصه دقیق", callback_data="summarize"),
                InlineKeyboardButton("📄 فایل ترجمه شده", callback_data="translate_file")
            ],[
                InlineKeyboardButton("📄 دانلود .md", callback_data="download_raw"),
                InlineKeyboardButton("📋 کپی", callback_data="copy")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🔘 <b>قابلیت‌های اضافی:</b>",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        
        # Web links
        elif text.startswith("http"):
            await update.message.reply_text("⏳ در حال استخراج محتوای صفحه...")
            content = extract_web(text)
            if content:
                # Save to DB
                db.save_web_content(user.id, text, content)
                
                header = "📎 <b>محتوای صفحه:</b>\n" + "="*30 + "\n\n"
                
                if len(content) <= 3500:
                    keyboard = [[
                        InlineKeyboardButton("🎯 خلاصه دقیق", callback_data="summarize"),
                        InlineKeyboardButton("📄 فایل ترجمه شده", callback_data="translate_file")
                    ],[
                        InlineKeyboardButton("📄 دانلود .md", callback_data="download_raw"),
                        InlineKeyboardButton("📋 کپی", callback_data="copy")
                    ]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"📎 <b>محتوای صفحه:</b>\n{'='*30}\n\n{content}",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    messages = split_message(header + content)
                    total_msgs = len(messages)
                    
                    await update.message.reply_text(f"📦 محتوا استخراج شد! تعداد پیام‌ها: {total_msgs}")
                    
                    for i, msg in enumerate(messages):
                        if i > 0:
                            await asyncio.sleep(1)
                        
                        safe_msg = msg if len(msg) <= 4000 else msg[:3950] + "\n\n... (ادامه در پیام بعدی)"
                        
                        if i == len(messages) - 1:
                            keyboard = [[
                                InlineKeyboardButton("🎯 خلاصه دقیق", callback_data="summarize"),
                                InlineKeyboardButton("📄 فایل ترجمه شده", callback_data="translate_file")
                            ],[
                                InlineKeyboardButton("📄 دانلود .md", callback_data="download_raw"),
                                InlineKeyboardButton("📋 کپی", callback_data="copy")
                            ]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await update.message.reply_text(safe_msg, reply_markup=reply_markup)
                        else:
                            await update.message.reply_text(f"📄 بخش {i+1}/{total_msgs}\n\n{safe_msg}")
            else:
                await update.message.reply_text("❌ نتونستم محتوا رو بخونم.")
        
        else:
            await update.message.reply_text(
                "❌ لطفاً یه لینک بفرست (یوتیوب یا وبسایت).\n\n"
                "💡 برای راهنمایی /help بزن.",
                parse_mode="HTML"
            )
    
    except Exception as e:
        logger.error(f"Handler error: {e}")
        await send_error_notification("Message Handler", str(e), f"user: {user.id if 'user' in locals() else 'unknown'}")
        try:
            await update.message.reply_text("❌ خطایی پیش اومد. لطفاً دوباره تلاش کن.")
        except:
            pass

# ============================================
# MAIN
# ============================================
def main():
    print("🤖 ربات استخراج و خلاصه‌سازی روشن شد!")
    print(f"🧠 مدل: {OPENROUTER_MODEL}")
    print(f"💾 دیتابیس: {DB_PATH}")
    
    async def post_init(application):
        set_error_bot(application.bot)
        await send_error_notification("Bot Started", "ربات @videoshahbot روشن شد ✅", "سیستم اعلان خطا فعال است")
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    print("🚀 در حال اجرای polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
