#!/usr/bin/env python3
"""
Registration Bot - ربات ثبت‌نام تلگرام
Users register through the bot in Telegram.
Collects: name, username, phone, purpose
Stores registrations in SQLite database.
"""
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

# States
NAME, PHONE, PURPOSE, CONFIRM = range(4)

# Bot token - will be set from env
import os
BOT_TOKEN = os.environ.get("REGISTRATION_BOT_TOKEN", "")

# Database
import sqlite3
DB_PATH = "/data/workspace/registration_bot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            purpose TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_registration(user_id, username, first_name, last_name, phone, purpose):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO registrations 
        (user_id, username, first_name, last_name, phone, purpose)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, first_name, last_name, phone, purpose))
    conn.commit()
    conn.close()

def get_registration(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM registrations WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def get_all_registrations():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM registrations ORDER BY registered_at DESC")
    results = c.fetchall()
    conn.close()
    return results

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if already registered
    existing = get_registration(user.id)
    if existing:
        await update.message.reply_text(
            f"✅ شما قبلاً ثبت‌نام کردید!\n\n"
            f"📋 اطلاعات شما:\n"
            f"• نام: {existing[3]} {existing[4] or ''}\n"
            f"• یوزرنیم: @{existing[2] or 'ندارد'}\n"
            f"• تلفن: {existing[5] or 'ثبت نشده'}\n"
            f"• هدف: {existing[6] or 'ثبت نشده'}\n"
            f"• تاریخ ثبت‌نام: {existing[7]}\n\n"
            f"برای ویرایش اطلاعات، /edit را بزنید."
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"👋 سلام {user.first_name}!\n\n"
        f"به ربات ثبت‌نام خوش آمدید.\n"
        f"برای ثبت‌نام، لطفاً اطلاعات خود را وارد کنید.\n\n"
        f"مرحله ۱/۴: نام کامل خود را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    
    # Ask for phone with keyboard button
    keyboard = [[KeyboardButton("📱 ارسال شماره تلفن", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        "مرحله ۲/۴: شماره تلفن خود را ارسال کنید.\n"
        "(روی دکمه زیر کلیک کنید یا شماره را تایپ کنید)",
        reply_markup=reply_markup
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        context.user_data['phone'] = update.message.contact.phone_number
    else:
        context.user_data['phone'] = update.message.text
    
    await update.message.reply_text(
        "مرحله ۳/۴: هدف شما از ثبت‌نام چیست؟\n"
        "(مثلاً: یادگیری، کار، پروژه شخصی، و...)",
        reply_markup=ReplyKeyboardRemove()
    )
    return PURPOSE

async def get_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['purpose'] = update.message.text
    
    user = update.effective_user
    name = context.user_data.get('name', 'نامشخص')
    phone = context.user_data.get('phone', 'ثبت نشده')
    purpose = context.user_data.get('purpose', 'ثبت نشده')
    
    # Confirm
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = [
        [InlineKeyboardButton("✅ بله", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ خیر", callback_data="confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"مرحله ۴/۴: تأیید اطلاعات\n\n"
        f"📋 خلاصه ثبت‌نام شما:\n"
        f"• نام: {name}\n"
        f"• یوزرنیم: @{user.username or 'ندارد'}\n"
        f"• آی‌دی: {user.id}\n"
        f"• تلفن: {phone}\n"
        f"• هدف: {purpose}\n\n"
        f"آیا اطلاعات صحیح است؟",
        reply_markup=reply_markup
    )
    return CONFIRM

async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_yes":
        user = query.from_user
        save_registration(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=context.user_data.get('phone'),
            purpose=context.user_data.get('purpose')
        )
        
        await query.edit_message_text(
            "🎉 ثبت‌نام شما با موفقیت انجام شد!\n\n"
            f"📋 اطلاعات ذخیره شده:\n"
            f"• نام: {user.first_name} {user.last_name or ''}\n"
            f"• یوزرنیم: @{user.username or 'ندارد'}\n"
            f"• آی‌دی: {user.id}\n\n"
            f"از ثبت‌نام شما متشکریم! 🙏"
        )
    else:
        await query.edit_message_text(
            "❌ ثبت‌نام لغو شد.\n"
            "برای شروع مجدد، /start را بزنید."
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ ثبت‌نام لغو شد.\n"
        "برای شروع مجدد، /start را بزنید.",
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reg = get_registration(user.id)
    
    if reg:
        await update.message.reply_text(
            f"📋 اطلاعات ثبت‌نام شما:\n\n"
            f"• نام: {reg[3]} {reg[4] or ''}\n"
            f"• یوزرنیم: @{reg[2] or 'ندارد'}\n"
            f"• آی‌دی: {reg[1]}\n"
            f"• تلفن: {reg[5] or 'ثبت نشده'}\n"
            f"• هدف: {reg[6] or 'ثبت نشده'}\n"
            f"• تاریخ ثبت‌نام: {reg[7]}"
        )
    else:
        await update.message.reply_text(
            "❌ شما هنوز ثبت‌نام نکردید.\n"
            "برای ثبت‌نام، /start را بزنید."
        )

async def list_registrations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command - list all registrations"""
    user = update.effective_user
    
    # Check if admin (you can change this to your user ID)
    ADMIN_IDS = [8848298889]  # شاهرخ's Telegram ID
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ شما اجازه دسترسی ندارید.")
        return
    
    regs = get_all_registrations()
    
    if not regs:
        await update.message.reply_text("📭 هنوز کسی ثبت‌نام نکرده.")
        return
    
    msg = f"📊 لیست ثبت‌نام‌ها ({len(regs)} نفر):\n\n"
    
    for i, reg in enumerate(regs, 1):
        msg += (
            f"{i}. {reg[3]} {reg[4] or ''}\n"
            f"   🆔 {reg[1]} | @{reg[2] or 'ندارد'}\n"
            f"   📱 {reg[5] or '-'} | 🎯 {reg[6] or '-'}\n"
            f"   📅 {reg[7]}\n\n"
        )
    
    # Telegram has 4096 char limit
    if len(msg) > 4000:
        for i in range(0, len(msg), 4000):
            await update.message.reply_text(msg[i:i+4000])
    else:
        await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 راهنمای ربات ثبت‌نام:\n\n"
        "• /start - شروع ثبت‌نام\n"
        "• /myinfo - مشاهده اطلاعات ثبت‌نام\n"
        "• /help - این راهنما\n\n"
        "برای ثبت‌نام، کافیه /start بزنید و اطلاعاتتون رو وارد کنید."
    )

def main():
    if not BOT_TOKEN:
        print("❌ REGISTRATION_BOT_TOKEN not set!")
        print("Set it in .env or environment.")
        return
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for registration
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
            PURPOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_purpose)],
            CONFIRM: [CallbackQueryHandler(confirm_callback, pattern='^confirm_')],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("myinfo", my_info))
    app.add_handler(CommandHandler("list", list_registrations))
    app.add_handler(CommandHandler("help", help_cmd))
    
    print("🚀 Registration bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
