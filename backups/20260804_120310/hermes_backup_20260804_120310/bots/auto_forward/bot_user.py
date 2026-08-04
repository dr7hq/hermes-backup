#!/usr/bin/env python3
"""
ربات فوروارد خودکار با اکانت کاربری (Telethon)
============================================
این ربات با اکانت تلگرام شما کار می‌کنه و نیازی به ادمین کردن بات نیست!
فقط کافیه کانال‌ها رو عمومی باشن یا عضوشون باشید.

Usage:
1. اولین بار اجرا: شماره تلفن و کد تأیید رو وارد کنید
2. تنظیمات کانال‌ها رو انجام بدید
3. ربات رو اجرا کنید
"""

import os
import json
import asyncio
import logging
from telethon import TelegramClient, events

# ============================================
# ⚙️ تنظیمات
# ============================================

# API ID و Hash رو از https://my.telegram.org بگیرید
API_ID = int(os.environ.get("TG_API_ID", "0"))
API_HASH = os.environ.get("TG_API_HASH", "")

# نام فایل نشست
SESSION_NAME = "forward_session"

# کانال‌های مبدأ (یوزرنیم یا chat_id)
SOURCE_CHANNELS = [
    # "@MatinSenPaii",
    # "@cacti_vibe",
    # -1001234567890,
]

# کانال/گروه مقصد (یوزرنیم یا chat_id)
DESTINATION_CHANNEL = None  # مثال: "@my_destination" یا -1001111111111

# فیلتر کلمات کلیدی (اختیاری - خالی = همه چی)
KEYWORD_FILTER = []

# حالت فوروارد
# True = با حفظ فرستنده
# False = بدون فرستنده
KEEP_SENDER = True

# ============================================
# 🤖 منطق ربات
# ============================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def load_config():
    """بارگذاری تنظیمات از فایل"""
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = json.load(f)
            return config
    return {}


def save_config(config):
    """ذخیره تنظیمات در فایل"""
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


async def setup_config():
    """تنظیم اولیه کانال‌ها"""
    config = load_config()
    
    print("\n⚙️ تنظیمات ربات فوروارد")
    print("=" * 40)
    
    # کانال‌های مبدأ
    if not config.get("sources"):
        print("\n📡 کانال‌های مبدأ رو وارد کنید (هر کدوم یه خط - برای پایان Enter بزنید):")
        sources = []
        while True:
            src = input("  کانال مبدأ: ").strip()
            if not src:
                break
            sources.append(src)
        config["sources"] = sources
    
    # کانال مقصد
    if not config.get("destination"):
        dest = input("\n🎯 کانال مقصد: ").strip()
        config["destination"] = dest
    
    # فیلتر کلمات
    if not config.get("keywords"):
        kw_input = input("\n🔍 کلمات کلیدی (اختیاری - با کاما جدا کنید): ").strip()
        config["keywords"] = [k.strip() for k in kw_input.split(",") if k.strip()] if kw_input else []
    
    save_config(config)
    return config


async def forward_message(event, config):
    """فوروارد پیام"""
    dest = config.get("destination")
    if not dest:
        return
    
    # فیلتر کلمات کلیدی
    keywords = config.get("keywords", [])
    if keywords:
        text = event.message.text or ""
        found = any(kw.lower() in text.lower() for kw in keywords)
        if not found:
            return
    
    try:
        if config.get("keep_sender", True):
            await event.message.forward_to(dest)
        else:
            await event.message.reply(text=event.message.text or "")
        
        logger.info(f"✅ پیام فوروارد شد به {dest}")
    except Exception as e:
        logger.error(f"❌ خطا در فوروارد: {e}")


async def main():
    """تابع اصلی"""
    if not API_ID or not API_HASH:
        print("❌ لطفاً API_ID و API_HASH رو تنظیم کنید!")
        print("   از https://my.telegram.org دریافت کنید")
        return
    
    # تنظیمات
    config = await setup_config()
    
    # ساخت کلاینت
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    
    print("\n🚀 ربات شروع به کار کرد!")
    print(f"📡 کانال‌های مبدأ: {config['sources']}")
    print(f"🎯 کانال مقصد: {config['destination']}")
    print("   برای توقف Ctrl+C بزنید\n")
    # resolve entity برای کانال‌های مبدأ
    source_entities = []
    for src in config["sources"]:
        try:
            entity = await client.get_entity(src)
            source_entities.append(entity.id)
            print(f"  ✅ {src} -> {entity.id}")
        except Exception as e:
            print(f"  ❌ {src}: {e}")
    
    # ریجیستر هندلر
    @client.on(events.NewMessage(chats=source_entities))
    async def handler(event):
        await forward_message(event, config)
    
    # اجرای کلاینت
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
