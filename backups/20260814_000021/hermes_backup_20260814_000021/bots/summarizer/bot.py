import os
import logging
import yt_dlp
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تنظیمات
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# توکن جمنای خودت رو اینجا بزار (یا از محیط تنظیم کن)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

# تنظیم گوگل جمنای
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! لینک یوتیوب یا وبسایت رو بفرست تا برات خلاصه کنم.")

async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    await update.message.reply_text("در حال پردازش... لطفا صبر کن.")
    
    try:
        # دانلود زیرنویس یوتیوب
        ydl_opts = {'skip_download': True, 'writesubtitles': True, 'subtitleslangs': ['en', 'fa'], 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # اینجا فرض میکنیم زیرنویس داره، یا متن وب رو میگیریم
            text = info.get('description', '')[:5000] # ساده‌سازی
        
        # خلاصه سازی با جمنای
        response = model.generate_content(f"این متن رو خلاصه کن: {text}")
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, summarize))

print("ربات خلاصه‌ساز روشن شد!")
app.run_polling()
