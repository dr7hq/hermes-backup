#!/usr/bin/env python3
"""
ربات فوروارد خودکار با وب‌اسکرپینگ
===================================
بدون نیاز به API ID، بدون نیاز به ادمین کردن بات در کانال مبدأ
فقط کافیه کانال‌ها عمومی باشن!

روش کار:
۱. هر ۳۰ ثانیه کانال‌ها رو چک میکنه
۲. پیام‌های جدید رو پیدا میکنه
۳. از طریق Bot API به کانال مقصد فوروارد میکنه
"""

import os
import json
import time
import re
import html
import urllib.request
import logging
from datetime import datetime

# ============================================
# ⚙️ تنظیمات
# ============================================

# توکن بات مقصد (از @BotFather)
BOT_TOKEN = os.environ.get("FORWARD_BOT_TOKEN", "8574290709:AAG5zONYD5neogndcnN0MggSx8UoiFd-VPA")

# کانال‌های مبدأ (یوزرنیم بدون @)
SOURCE_CHANNELS = [
    # "MatinSenPaii",
    # "cacti_vibe",
]

# کانال مقصد (chat_id)
DESTINATION_CHANNEL = None  # مثال: -1004486385560

# فاصله بررسی (ثانیه)
CHECK_INTERVAL = 30

# فیلتر کلمات کلیدی (اختیاری)
KEYWORD_FILTER = []

# حداکثر پیام برای هر بار بررسی
MAX_MESSAGES_PER_CHECK = 20

# ============================================
# 🤖 منطق ربات
# ============================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# فایل ذخیره وضعیت
STATE_FILE = "forward_state.json"


def load_state():
    """بارگذاری وضعیت آخرین پیام‌های ارسال شده"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    """ذخیره وضعیت"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_telegram_message(text, chat_id=None):
    """ارسال پیام از طریق Bot API"""
    if chat_id is None:
        chat_id = DESTINATION_CHANNEL
    
    try:
        data = json.dumps({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result.get("ok", False)
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")
        return False


def forward_telegram_message(from_chat_id, message_id):
    """فوروارد پیام از طریق Bot API"""
    try:
        data = json.dumps({
            "chat_id": DESTINATION_CHANNEL,
            "from_chat_id": from_chat_id,
            "message_id": message_id
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/forwardMessage",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result.get("ok", False)
    except Exception as e:
        logger.error(f"خطا در فوروارد: {e}")
        return False


def scrape_channel(channel_username):
    """خواندن پیام‌های کانال از طریق وب‌اسکرپینگ"""
    messages = []
    
    try:
        url = f"https://t.me/s/{channel_username}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=15)
        page = resp.read().decode("utf-8")
        
        # استخراج پیام‌ها
        # الگوی پیام در t.me/s/
        msg_pattern = r'<div class="tgme_widget_message_wrap[^"]*"[^>]*data-post="([^"]*)"[^>]*>'
        msg_ids = re.findall(msg_pattern, page)
        
        # استخراج متن‌ها
        text_pattern = r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>'
        texts = re.findall(text_pattern, page, re.DOTALL)
        
        # پاکسازی متن‌ها
        clean_texts = []
        for t in texts:
            clean = re.sub(r'<[^>]+>', ' ', t).strip()
            clean = html.unescape(clean)
            clean_texts.append(clean)
        
        # ترکیب ID و متن
        for i, msg_id in enumerate(msg_ids):
            # استخراج شماره پیام از data-post
            parts = msg_id.split("/")
            if len(parts) >= 2:
                try:
                    real_id = int(parts[-1])
                    text = clean_texts[i] if i < len(clean_texts) else ""
                    messages.append({
                        "id": real_id,
                        "text": text,
                        "username": channel_username
                    })
                except ValueError:
                    pass
        
        logger.info(f"📡 {len(messages)} پیام از @{channel_username} خوانده شد")
        
    except Exception as e:
        logger.error(f"خطا در خواندن @{channel_username}: {e}")
    
    return messages


def check_and_forward():
    """بررسی کانال‌ها و فوروارد پیام‌های جدید"""
    state = load_state()
    total_forwarded = 0
    
    for channel in SOURCE_CHANNELS:
        # خواندن پیام‌ها
        messages = scrape_channel(channel)
        
        # پیدا کردن آخرین پیام ارسال شده
        last_id = state.get(channel, 0)
        
        # فیلتر پیام‌های جدید
        new_messages = [m for m in messages if m["id"] > last_id]
        new_messages.sort(key=lambda x: x["id"])  # مرتب کردن از قدیم به جدید
        
        # فوروارد پیام‌های جدید
        for msg in new_messages[:MAX_MESSAGES_PER_CHECK]:
            text = msg["text"]
            
            # فیلتر کلمات کلیدی
            if KEYWORD_FILTER:
                found = any(kw.lower() in text.lower() for kw in KEYWORD_FILTER)
                if not found:
                    continue
            
            # فوروارد پیام
            success = forward_telegram_message(
                from_chat_id=f"@{channel}",
                message_id=msg["id"]
            )
            
            if success:
                total_forwarded += 1
                state[channel] = msg["id"]
                logger.info(f"✅ فوروارد شد: @{channel}/{msg['id']}")
            else:
                logger.warning(f"⚠️ خطا در فوروارد: @{channel}/{msg['id']}")
            
            time.sleep(0.5)  # تأخیر بین فورواردها
    
    save_state(state)
    return total_forwarded


def main():
    """حلقه اصلی"""
    print("🚀 ربات فوروارد خودکار شروع به کار کرد!")
    print(f"📡 کانال‌های مبدأ: {SOURCE_CHANNELS}")
    print(f"🎯 کانال مقصد: {DESTINATION_CHANNEL}")
    print(f"⏱️ فاصله بررسی: {CHECK_INTERVAL} ثانیه")
    print("   برای توقف Ctrl+C بزنید\n")
    
    # ارسال پیام شروع
    send_telegram_message("🤖 ربات فوروارد خودکار فعال شد!")
    
    while True:
        try:
            forwarded = check_and_forward()
            if forwarded > 0:
                logger.info(f"📊 {forwarded} پیام فوروارد شد")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n🛑 ربات متوقف شد!")
            send_telegram_message("🛑 ربات فوروارد خودکار متوقف شد!")
            break
        except Exception as e:
            logger.error(f"خطای غیرمنتظره: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
