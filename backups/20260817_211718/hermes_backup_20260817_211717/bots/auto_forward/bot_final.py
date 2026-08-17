#!/usr/bin/env python3
"""
ربات فوروارد خودکار با وب‌اسکرپینگ (نسخه نهایی)
===================================
بدون نیاز به API ID، بدون نیاز به ادمین کردن بات در کانال مبدأ
فقط کافیه کانال‌ها عمومی باشن!
"""

import os
import json
import time
import re
import html
import urllib.request
import logging

# ============================================
# ⚙️ تنظیمات
# ============================================

BOT_TOKEN = os.environ.get("FORWARD_BOT_TOKEN", "8574290709:AAG5zONYD5neogndcnN0MggSx8UoiFd-VPA")

SOURCE_CHANNELS = [
    "MatinSenPaii",
    # "cacti_vibe",  # وقتی فعال شد اضافه کن
]

DESTINATION_CHANNEL = "-1004486385560"

CHECK_INTERVAL = 300  # هر 5 دقیقه

KEYWORD_FILTER = []  # خالی = همه چی

MAX_MESSAGES = 5  # حداکثر پیام جدید در هر بار بررسی

# ============================================
# 🤖 منطق
# ============================================

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

STATE_FILE = "forward_state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send_message(text):
    try:
        data = json.dumps({
            "chat_id": DESTINATION_CHANNEL,
            "text": text[:4000]
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read()).get("ok", False)
    except Exception as e:
        logger.error(f"خطا: {e}")
        return False


def scrape_channel(username):
    messages = []
    try:
        url = f"https://t.me/s/{username}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        page = resp.read().decode("utf-8")

        msg_ids = re.findall(r'data-post="([^"]+)"', page)
        texts = re.findall(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', page, re.DOTALL)

        clean_texts = [html.unescape(re.sub(r'<[^>]+>', ' ', t).strip()) for t in texts]

        for i, msg_id in enumerate(msg_ids):
            parts = msg_id.split("/")
            if len(parts) >= 2:
                try:
                    real_id = int(parts[-1])
                    text = clean_texts[i] if i < len(clean_texts) else ""
                    messages.append({"id": real_id, "text": text})
                except ValueError:
                    pass

        logger.info(f"📡 {len(messages)} پیام از @{username}")
    except Exception as e:
        logger.error(f"خطا @{username}: {e}")

    return messages


def check_and_forward():
    state = load_state()
    total = 0

    for channel in SOURCE_CHANNELS:
        messages = scrape_channel(channel)
        last_id = state.get(channel, 0)
        new_msgs = [m for m in messages if m["id"] > last_id]
        new_msgs.sort(key=lambda x: x["id"])

        for msg in new_msgs[:MAX_MESSAGES]:
            text = msg["text"]
            if not text:
                continue

            if KEYWORD_FILTER:
                if not any(kw.lower() in text.lower() for kw in KEYWORD_FILTER):
                    continue

            source_url = f"https://t.me/{channel}/{msg['id']}"
            full_text = f"📡 از @{channel}:\n\n{text}\n\n🔗 {source_url}"

            if send_message(full_text):
                total += 1
                state[channel] = msg["id"]
                logger.info(f"✅ @{channel}/{msg['id']}")
                time.sleep(0.5)

    save_state(state)
    return total


def main():
    print("🚀 ربات فوروارد خودکار شروع شد!")
    print(f"📡 مبدأ: {SOURCE_CHANNELS}")
    print(f"🎯 مقصد: {DESTINATION_CHANNEL}")
    print(f"⏱️ فاصله: {CHECK_INTERVAL} ثانیه\n")

    send_message("🤖 ربات فوروارد خودکار فعال شد!")

    while True:
        try:
            n = check_and_forward()
            if n:
                logger.info(f"📊 {n} پیام جدید فوروارد شد")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\n🛑 متوقف شد!")
            send_message("🛑 ربات فوروارد متوقف شد!")
            break
        except Exception as e:
            logger.error(f"خطا: {e}")
            time.sleep(60)


if __name__ == "__main__":
    main()
