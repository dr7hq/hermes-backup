#!/usr/bin/env python3
"""
ربات خلاصه‌ساز لینک و ویدئو با حالت ایجنت چندمدله
"""

import os, re, json, logging, urllib.request, subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

def get_api_key():
    env_path = os.path.join(os.path.expanduser("~"), ".hermes", ".env")
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith("OPENAI_API_KEY="):
                return line.strip().split("=", 1)[1]
    return None

def get_api_url():
    env_path = os.path.join(os.path.expanduser("~"), ".hermes", ".env")
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith("OPENAI_BASE_URL="):
                return line.strip().split("=", 1)[1]
    return None

API_KEY = get_api_key()
API_URL = get_api_url()

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def call_model(prompt, model="mimo-hermes"):
    try:
        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.7
        }).encode()
        req = urllib.request.Request(
            f"{API_URL}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
        )
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"خطا: {e}")
        return None


def extract_youtube(url):
    """استخراج اطلاعات ویدئوی یوتیوب با yt-dlp"""
    try:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--sub-lang", "en,fa",
            "--sub-format", "vtt",
            "--print-json",
            "--no-playlist",
            "-o", "/tmp/yt_sub",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout:
            info = json.loads(result.stdout)
            title = info.get("title", "بدون عنوان")
            desc = info.get("description", "")
            duration = info.get("duration_string", "")
            
            # تلاش برای خواندن زیرنویس
            sub_text = ""
            for ext in ["en.vtt", "fa.vtt", "en-US.vtt"]:
                sub_path = f"/tmp/yt_sub.{ext}"
                if os.path.exists(sub_path):
                    with open(sub_path, "r", encoding="utf-8", errors="ignore") as f:
                        sub_text = f.read()
                    os.remove(sub_path)
                    break
            
            content = f"عنوان: {title}\nمدت: {duration}\nتوضیحات: {desc[:2000]}"
            if sub_text:
                # پاکسازی زیرنویس VTT
                lines = []
                for line in sub_text.split("\n"):
                    line = line.strip()
                    if not line or "-->" in line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:") or re.match(r"^\d+$", line):
                        continue
                    lines.append(line)
                content += f"\n\nمتن ویدئو: {' '.join(lines)[:5000]}"
            
            return content
        else:
            logger.error(f"yt-dlp error: {result.stderr[:200]}")
            return f"لینک یوتیوب: {url}"
    except Exception as e:
        logger.error(f"yt-dlp خطا: {e}")
        return f"لینک یوتیوب: {url}"


def extract_web(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="ignore")
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:5000]
    except:
        return None


def summarize(content, ctype="وبسایت"):
    p1 = f"این {ctype} رو خلاصه کن. نکات کلیدی رو بنویس:\n{content[:3000]}"
    r1 = call_model(p1, "gemini-2.0-flash")

    p2 = f"این {ctype} رو تحلیل کن:\n۱. خلاصه کوتاه\n۲. نکات کلیدی\n۳. جمع‌بندی\n\n{content[:3000]}"
    r2 = call_model(p2, "mimo-hermes")

    out = ""
    if r2:
        out += f"📊 تحلیل:\n{r2}\n\n"
    if r1:
        out += f"⚡ خلاصه سریع:\n{r1}"
    return out or "متأسفانه نتونستم خلاصه بسازم."


async def start(update, context):
    await update.message.reply_text(
        "🤖 ربات خلاصه‌ساز لینک و ویدئو\n\n"
        "✨ قابلیت‌ها:\n"
        "• خلاصه‌سازی لینک‌های وب\n"
        "• استخراج متن ویدئوی یوتیوب\n"
        "• تحلیل با چند مدل AI\n\n"
        "📌 کافیه یه لینک بفرستی!"
    )


async def handle_msg(update, context):
    text = update.message.text
    await update.message.reply_text("⏳ در حال پردازش...")

    if "youtube.com" in text or "youtu.be" in text:
        content = extract_youtube(text)
        ctype = "یوتیوب"
    elif text.startswith("http"):
        content = extract_web(text)
        if not content:
            await update.message.reply_text("❌ نتونستم محتوا رو بخونم.")
            return
        ctype = "وبسایت"
    else:
        await update.message.reply_text("❌ لطفاً یه لینک بفرست.")
        return

    result = summarize(content, ctype)
    await update.message.reply_text(f"📎 خلاصه {ctype}:\n{'='*30}\n\n{result}")


def main():
    print(f"🤖 ربات روشن شد!")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
