#!/usr/bin/env python3
"""
ربات فوروارد خودکار پیام‌های تلگرام
Auto Forward Bot - forwards messages from channels/groups to destinations

Usage:
1. Create a new bot via @BotFather
2. Add the bot as ADMIN to source channels
3. Add the bot as ADMIN to destination channel/group
4. Configure settings below
5. Run: python3 auto_forward.py
"""

import os
import json
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ============================================
# ⚙️ تنظیمات ربات
# ============================================

# توکن ربات (از @BotFather بگیرید)
BOT_TOKEN = os.environ.get("FORWARD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# کانال/گروه مبدأ (از اینجا فوروارد میشه)
# chat_id منفی برای کانال‌ها، مثبت برای گروه‌ها
SOURCE_CHANNELS = [
    # -1001234567890,  # مثال: کانال اخبار
    # -1009876543210,  # مثال: گروه تکنولوژی
]

# کانال/گروه مقصد (به اینجا فوروارد میشه)
DESTINATION_CHANNEL = None  # مثال: -1001111111111

# فیلتر کلمات کلیدی (اختیاری)
# اگه خالی باشه، همه پیام‌ها فوروارد میشن
KEYWORD_FILTER = []  # مثال: ["هوش مصنوعی", "AI", "ربات"]

# حالت فوروارد
# True = حفظ فرستنده اصلی (Forward)
# False = بدون نام فرستنده (Copy)
KEEP_SENDER = True

# ============================================
# 🤖 منطق ربات
# ============================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌های جدید کانال"""
    message = update.channel_post or update.message
    if not message:
        return

    chat_id = message.chat.id

    # بررسی آیا کانال مبدأ هست
    if chat_id not in SOURCE_CHANNELS:
        return

    # بررسی مقصد
    if DESTINATION_CHANNEL is None:
        return

    # استخراج متن پیام
    text = message.text or message.caption or ""

    # فیلتر کلمات کلیدی
    if KEYWORD_FILTER:
        found = any(kw.lower() in text.lower() for kw in KEYWORD_FILTER)
        if not found:
            logger.info(f"پیام فیلتر شد: {text[:50]}...")
            return

    try:
        if KEEP_SENDER:
            # فوروارد با حفظ فرستنده
            await context.bot.forward_message(
                chat_id=DESTINATION_CHANNEL,
                from_chat_id=chat_id,
                message_id=message.message_id
            )
        else:
            # کپی بدون فرستنده
            await context.bot.copy_message(
                chat_id=DESTINATION_CHANNEL,
                from_chat_id=chat_id,
                message_id=message.message_id
            )

        logger.info(f"✅ پیام از {chat_id} به {DESTINATION_CHANNEL} فوروارد شد")

    except Exception as e:
        logger.error(f"❌ خطا در فوروارد: {e}")


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستورات ربات"""
    if update.message is None:
        return

    text = update.message.text
    chat_id = update.message.chat.id

    if text == "/start":
        await update.message.reply_text(
            "🤖 ربات فوروارد خودکار\n\n"
            "این ربات پیام‌های جدید کانال‌ها رو خودکار فوروارد میکنه.\n\n"
            "دستورات:\n"
            "/status - وضعیت ربات\n"
            "/sources - لیست کانال‌های مبدأ\n"
            "/dest - کانال مقصد\n\n"
            "⚙️ تنظیمات در فایل پیکربندی انجام میشه."
        )

    elif text == "/status":
        status = "🟢 فعال" if DESTINATION_CHANNEL else "🔴 غیرفعال"
        await update.message.reply_text(
            f"📊 وضعیت ربات: {status}\n\n"
            f"کانال‌های مبدأ: {len(SOURCE_CHANNELS)}\n"
            f"کانال مقصد: {DESTINATION_CHANNEL or 'تعریف نشده'}\n"
            f"فیلتر کلمات: {len(KEYWORD_FILTER)} کلمه\n"
            f"حالت فوروارد: {'حفظ فرستنده' if KEEP_SENDER else 'بدون فرستنده'}"
        )

    elif text == "/sources":
        if SOURCE_CHANNELS:
            sources = "\n".join([f"• {s}" for s in SOURCE_CHANNELS])
            await update.message.reply_text(f"📡 کانال‌های مبدأ:\n{sources}")
        else:
            await update.message.reply_text("⚠️ هیچ کانال مبدأ تعریف نشده!")

    elif text == "/dest":
        if DESTINATION_CHANNEL:
            await update.message.reply_text(f"🎯 کانال مقصد: {DESTINATION_CHANNEL}")
        else:
            await update.message.reply_text("⚠️ کانال مقصد تعریف نشده!")


def main():
    """شروع ربات"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ لطفاً توکن ربات رو تنظیم کنید!")
        print("   یا از @BotFather یه ربات بسازید و توکنش رو بدید")
        return

    # ساخت اپلیکیشن
    app = Application.builder().token(BOT_TOKEN).build()

    # اضافه کردن هندلرها
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_channel_post))
    app.add_handler(MessageHandler(filters.TEXT & filters.COMMAND, handle_command))

    print("🚀 ربات فوروارد خودکار شروع به کار کرد!")
    print(f"📡 کانال‌های مبدأ: {SOURCE_CHANNELS}")
    print(f"🎯 کانال مقصد: {DESTINATION_CHANNEL}")
    print("   برای توقف Ctrl+C بزنید")

    # شروع polling
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
