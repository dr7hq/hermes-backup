#!/usr/bin/env python3
"""
Telegram API Creator Bot - نسخه کامل
با تمام تجربه‌ها از my.telegram.org:
- ذخیره session برای ورود مجدد
- نمایش خطاهای دقیق
- راهنمایی در صورت خطا
- پشتیبانی از TOR برای تغییر IP
"""
import logging
import requests
import re
import pickle
import os
import json
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

# States
WAITING_PHONE, WAITING_CODE = range(2)

# Bot token
BOT_TOKEN = os.environ.get("TELEGRAM_API_BOT_TOKEN", "")

# Session storage
SESSION_DIR = "/data/workspace/api_bot_sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── متن‌های راهنما ───
HELP_TEXT = """
📖 **راهنمای ربات:**

این ربات به my.telegram.org وصل میشه و برات **API ID** و **API Hash** میسازه.

**دستورات:**
• `/start` - شروع فرآیند ساخت اپ
• `/myapps` - مشاهده اپ‌های ساخته شده
• `/help` - این راهنما
• `/cancel` - لغو عملیات

**مراحل کار:**
1️⃣ شماره تلفنت رو بده
2️⃣ کد تأییدی که به تلگرامت اومد رو وارد کن
3️⃣ ربات اپ رو میسازه و اطلاعات رو بهت میده!

**نکات مهم:**
• ⚠️ به هر شماره فقط **یک اپ** تعلق میگیره
• 🔄 اگه قبلاً اپ ساختی، همون اطلاعات رو نشون میده
• ⏱️ کدها بعد از چند دقیقه منقضی میشن
• 🔒 اطلاعاتت کاملاً امن میمونه

**خطاهای رایج و راه‌حل‌ها:**
• "Sorry, too many tries" → چند ساعت صبر کن
• "Invalid confirmation code" → کد رو دوباره چک کن
• "ERROR" در ساخت اپ → اپ قبلاً ساخته شده یا محدودیت داری
"""

ERROR_GUIDE = """
🔍 **راهنمای عیب‌یابی:**

**خطای "Sorry, too many tries":**
→ تلگرام IP یا حساب تو رو محدود کرده
→ راه‌حل: چند ساعت صبر کن یا از شماره دیگه استفاده کن

**خطای "Invalid confirmation code":**
→ کد منقضی شده یا اشتباه وارد کردی
→ راه‌حل: `/start` بزن و کد جدید بگیر

**خطای "ERROR" در ساخت اپ:**
→ ممکنه اپ قبلاً ساخته شده
→ راه‌حل: ربات چک میکنه اگه اپ هست، اطلاعاتش رو نشون میده

**خطای "Object Object":**
→ سرور تلگرام خطا برگردونده ولی جزئیاتش معلوم نیست
→ راه‌حل: دوباره تلاش کن یا شماره دیگه امتحان کن

**خطای "No hash found":**
→ صفحه my.telegram.org تغییر کرده
→ راه‌حل: به ادمین اطلاع بده
"""


def get_session_path(phone):
    """Get session file path for a phone number"""
    safe_phone = phone.replace('+', '').replace(' ', '')
    return os.path.join(SESSION_DIR, f"{safe_phone}.pkl")


def create_session(phone):
    """Create a new requests session with TOR proxy"""
    s = requests.Session()
    
    # Try TOR first, fallback to direct
    try:
        proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
        # Test if TOR is available
        r = s.get("https://check.torproject.org/api/ip", proxies=proxies, timeout=10)
        if r.status_code == 200:
            s.proxies = proxies
            logger.info(f"Using TOR proxy, IP: {r.json().get('IP')}")
        else:
            logger.info("TOR not available, using direct connection")
    except Exception as e:
        logger.info(f"TOR not available: {e}, using direct connection")
    
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    })
    
    return s


def save_session(phone, session):
    """Save session to file"""
    path = get_session_path(phone)
    with open(path, 'wb') as f:
        pickle.dump(session, f)
    logger.info(f"Session saved for {phone}")


def load_session(phone):
    """Load session from file"""
    path = get_session_path(phone)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            session = pickle.load(f)
        # Re-apply headers and proxy
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        try:
            proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            session.proxies = proxies
        except:
            pass
        logger.info(f"Session loaded for {phone}")
        return session
    return None


def delete_session(phone):
    """Delete session file"""
    path = get_session_path(phone)
    if os.path.exists(path):
        os.remove(path)
        logger.info(f"Session deleted for {phone}")


def send_verification_code(phone):
    """
    Send verification code to phone number.
    Returns: dict with status and message
    """
    session = create_session(phone)
    
    try:
        r = session.post(
            "https://my.telegram.org/auth/send_password",
            data={"phone": phone},
            timeout=30
        )
        
        logger.info(f"Send password response: {r.text[:200]}")
        
        if "too many tries" in r.text.lower():
            return {
                "status": "error",
                "error_type": "rate_limit",
                "message": "⛔ **تعداد تلاش‌ها بیش از حد مجاز است!**\n\n"
                           "تلگرام IP یا حساب تو رو محدود کرده.\n"
                           "⏱️ **راه‌حل:** چند ساعت صبر کن یا شماره دیگه امتحان کن.\n\n"
                           f"📝 **جزئیات:** `{r.text[:100]}`"
            }
        
        try:
            result = r.json()
            if 'random_hash' in result:
                # Save session for later use
                save_session(phone, session)
                return {
                    "status": "success",
                    "message": "✅ **کد تأیید ارسال شد!**\n\n"
                               "📱 کدی که به تلگرامت اومد رو وارد کن.\n"
                               "⏱️ کد بعد از چند دقیقه منقضی میشه."
                }
        except json.JSONDecodeError:
            pass
        
        return {
            "status": "error",
            "error_type": "unknown",
            "message": f"❌ **خطای نامعلوم**\n\n"
                       f"📝 **پاسخ سرور:** `{r.text[:200]}`\n\n"
                       f"🔍 راهنما: /help"
        }
        
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "error_type": "timeout",
            "message": "⏱️ **زمان انتظار تمام شد!**\n\n"
                       "اتصال به my.telegram.org قطع شد.\n"
                       "🔄 دوباره تلاش کن."
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": "exception",
            "message": f"❌ **خطای غیرمنتظره:**\n\n"
                       f"`{str(e)[:200]}`\n\n"
                       f"🔍 راهنما: /help"
        }


def login_and_create_app(phone, code):
    """
    Login with code and create app.
    Returns: dict with status and data
    """
    session = load_session(phone)
    if not session:
        return {
            "status": "error",
            "message": "❌ ** session منقضی شده!**\n\n"
                       "🔄 دوباره /start بزن و شماره رو بده."
        }
    
    try:
        # Login
        r = session.post(
            "https://my.telegram.org/auth/login",
            data={"phone": phone, "password": code},
            timeout=30
        )
        
        logger.info(f"Login response: {r.text[:300]}")
        
        if "Invalid confirmation code" in r.text or "invalid" in r.text.lower():
            return {
                "status": "error",
                "error_type": "invalid_code",
                "message": "❌ **کد نامعتبر است!**\n\n"
                           "📝 **دلایل احتمالی:**\n"
                           "• کد رو اشتباه وارد کردی\n"
                           "• کد منقضی شده\n"
                           "• کد مال شماره دیگه‌ای است\n\n"
                           "🔄 **راه‌حل:** /start بزن و کد جدید بگیر"
            }
        
        if "too many tries" in r.text.lower():
            return {
                "status": "error",
                "error_type": "rate_limit",
                "message": "⛔ **تعداد تلاش‌ها بیش از حد مجاز است!**\n\n"
                           "⏱️ **راه‌حل:** چند ساعت صبر کن."
            }
        
        if '"success":true' not in r.text:
            return {
                "status": "error",
                "error_type": "login_failed",
                "message": f"❌ **ورود ناموفق!**\n\n"
                           f"📝 **پاسخ سرور:** `{r.text[:200]}`\n\n"
                           f"🔄 دوباره تلاش کن یا شماره دیگه امتحان کن."
            }
        
        # Login successful - get apps page
        r = session.get("https://my.telegram.org/apps", timeout=30)
        title = re.search(r'<title>(.*?)</title>', r.text)
        page_title = title.group(1) if title else ""
        
        logger.info(f"Apps page title: {page_title}")
        
        # ─── بررسی وجود اپ قبلی ───
        if 'App configuration' in r.text or 'api_id' in r.text.lower():
            # Extract existing credentials
            aid = re.search(r'<strong>(\d+)</strong>', r.text)
            ah = re.search(r'<span class="form-control input-lg">([a-f0-9]+)</span>', r.text)
            
            if aid and ah:
                delete_session(phone)
                return {
                    "status": "success",
                    "message": "📋 **اپ قبلاً ساخته شده!**\n\n"
                               "این اطلاعات مال اپ قبلی توئه:",
                    "api_id": aid.group(1),
                    "api_hash": ah.group(1),
                    "existing": True
                }
            
            # Try alternative patterns
            all_strongs = re.findall(r'<strong[^>]*>(.*?)</strong>', r.text)
            all_spans = re.findall(r'<span class="form-control input-lg">(.*?)</span>', r.text)
            
            if all_strongs and all_spans:
                delete_session(phone)
                return {
                    "status": "success",
                    "message": "📋 **اپ قبلاً ساخته شده!**\n\n"
                               "این اطلاعات مال اپ قبلی توئه:",
                    "api_id": all_strongs[0],
                    "api_hash": all_spans[0],
                    "existing": True
                }
        
        # ─── استخراج hash برای ساخت اپ جدید ───
        m = re.search(r'<input type="hidden" name="hash" value="([a-f0-9]+)"', r.text)
        if not m:
            delete_session(phone)
            return {
                "status": "error",
                "error_type": "no_hash",
                "message": "❌ **خطا در دریافت اطلاعات صفحه!**\n\n"
                           "📝 **پاسخ سرور:** صفحه حاوی hash نیست\n\n"
                           "🔍 **احتمالا:**\n"
                           "• صفحه my.telegram.org تغییر کرده\n"
                           "• حساب تو محدود شده\n\n"
                           f"📄 **عنوان صفحه:** `{page_title}`"
            }
        
        h = m.group(1)
        logger.info(f"Got hash: {h}")
        
        # ─── ساخت اپ ───
        data = {
            'hash': h,
            'app_title': 'MyTelegramApp',
            'app_shortname': 'myapp',
            'app_url': '',
            'app_platform': 'android',
            'app_desc': 'Telegram application'
        }
        
        r = session.post(
            "https://my.telegram.org/apps/create",
            data=data,
            headers={'X-Requested-With': 'XMLHttpRequest'},
            timeout=30
        )
        
        logger.info(f"Create response: {repr(r.text)}")
        
        if r.text == "ERROR":
            delete_session(phone)
            return {
                "status": "error",
                "error_type": "create_error",
                "message": "❌ **خطا در ساخت اپ!**\n\n"
                           "📝 **دلایل احتمالی:**\n"
                           "• اپ قبلاً ساخته شده (ولی نمایش داده نمیشه)\n"
                           "• حساب تو محدود شده برای ساخت اپ\n"
                           "• تغییرات در سرور تلگرام\n\n"
                           "🔍 **پیشنهاد:**\n"
                           "1. با شماره دیگه امتحان کن\n"
                           "2. چند ساعت صبر کن\n"
                           "3. به ادمین اطلاع بده"
            }
        
        if "Object" in r.text:
            delete_session(phone)
            return {
                "status": "error",
                "error_type": "object_error",
                "message": "⚠️ **پاسخ نامعلوم از سرور!**\n\n"
                           "📝 سرور یه آبجکت برگردونده ولی جزئیاتش معلوم نیست.\n\n"
                           "🔄 **راه‌حل:** دوباره تلاش کن یا شماره دیگه امتحان کن."
            }
        
        # Try to parse JSON response
        try:
            result = r.json()
            logger.info(f"Parsed JSON: {result}")
            
            if 'App' in result:
                app = result['App']
                delete_session(phone)
                return {
                    "status": "success",
                    "message": "🎉 **اپ با موفقیت ساخته شد!**",
                    "api_id": str(app.get('api_id', '')),
                    "api_hash": app.get('api_hash', ''),
                    "existing": False
                }
            
            if 'error_code' in result:
                delete_session(phone)
                return {
                    "status": "error",
                    "error_type": "api_error",
                    "message": f"❌ **خطا از سرور تلگرام!**\n\n"
                               f"📝 **کد خطا:** `{result.get('error_code')}`\n"
                               f"📝 **پیام:** `{result.get('error_message', 'نامعلوم')}`"
                }
                
        except json.JSONDecodeError:
            pass
        
        # Unknown response
        delete_session(phone)
        return {
            "status": "error",
            "error_type": "unknown_response",
            "message": f"❓ **پاسخ نامعلوم**\n\n"
                       f"📝 **پاسخ خام:** `{r.text[:200]}`\n\n"
                       f"🔍 این اطلاعات رو به ادمین بده تا بررسی کنه."
        }
        
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "error_type": "timeout",
            "message": "⏱️ **زمان انتظار تمام شد!**\n\n"
                       "اتصال قطع شد. دوباره تلاش کن."
        }
    except Exception as e:
        logger.error(f"Exception: {e}")
        return {
            "status": "error",
            "error_type": "exception",
            "message": f"❌ **خطای غیرمنتظره:**\n\n"
                       f"`{str(e)[:200]}`"
        }


# ─── Handlers ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند"""
    user = update.effective_user
    
    # Check for existing sessions
    phone = None
    for f in os.listdir(SESSION_DIR):
        if f.endswith('.pkl'):
            phone = f.replace('.pkl', '').replace('989', '+989')
            break
    
    keyboard = []
    if phone:
        keyboard.append([InlineKeyboardButton(f"📱 استفاده از {phone}", callback_data=f"use_{phone}")])
    keyboard.append([InlineKeyboardButton("📱 شماره جدید", callback_data="new_phone")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔑 **سلام {user.first_name}!**\n\n"
        f"به **سازنده اپ تلگرام** خوش آمدی!\n\n"
        f"این ربات به my.telegram.org وصل میشه و برات **API ID** و **API Hash** میسازه.\n\n"
        f"💡 **نکته:** به هر شماره فقط **یک اپ** تعلق میگیره.\n\n"
        f"شماره تلفنت رو انتخاب کن:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return WAITING_PHONE


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """-handling inline keyboard buttons"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_phone":
        await query.edit_message_text(
            "📱 **شماره تلفنت رو بده:**\n\n"
            "فرمت صحیح: `+989123456789`\n\n"
            "⚠️ مطمئن شو شماره‌ای که باهاش وارد تلگرام شدی رو میدی.",
            parse_mode='Markdown'
        )
        context.user_data['awaiting_phone'] = True
        return WAITING_PHONE
    
    elif query.data.startswith("use_"):
        phone = query.data.replace("use_", "")
        phone = "+" + phone
        context.user_data['phone'] = phone
        
        await query.edit_message_text(f"⏳ دارم کد تأیید رو به {phone} میفرستم...")
        
        result = send_verification_code(phone)
        
        if result['status'] == 'success':
            await query.edit_message_text(
                f"{result['message']}\n\n"
                f"📱 **کد رو اینجا بفرست:**",
                parse_mode='Markdown'
            )
            return WAITING_CODE
        else:
            await query.edit_message_text(
                result['message'],
                parse_mode='Markdown'
            )
            return ConversationHandler.END


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت شماره تلفن"""
    phone = update.message.text.strip()
    
    # Validate phone format
    if not phone.startswith('+') or len(phone) < 10 or not phone[1:].isdigit():
        await update.message.reply_text(
            "❌ **شماره نامعتبره!**\n\n"
            "📝 **فرمت صحیح:** `+989123456789`\n\n"
            "⚠️ مطمئن شو:\n"
            "• با `+` شروع بشه\n"
            "• فقط عدد باشه\n"
            "• حداقل ۱۰ رقم داشته باشه",
            parse_mode='Markdown'
        )
        return WAITING_PHONE
    
    context.user_data['phone'] = phone
    
    await update.message.reply_text(f"⏳ دارم کد تأیید رو به {phone} میفرستم...")
    
    # Send verification code
    result = send_verification_code(phone)
    
    if result['status'] == 'success':
        await update.message.reply_text(
            f"{result['message']}\n\n"
            f"📱 **کد رو اینجا بفرست:**",
            parse_mode='Markdown'
        )
        return WAITING_CODE
    else:
        await update.message.reply_text(
            result['message'],
            parse_mode='Markdown'
        )
        return ConversationHandler.END


async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت کد و ساخت اپ"""
    code = update.message.text.strip()
    phone = context.user_data.get('phone')
    
    if not phone:
        await update.message.reply_text(
            "❌ **شماره‌ای ذخیره نشده!**\n\n🔄 دوباره /start بزن.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    # Validate code format (usually 5-6 digits or alphanumeric)
    if len(code) < 5:
        await update.message.reply_text(
            "❌ **کد خیلی کوتاهه!**\n\n"
            "📝 کدهای تلگرام معمولاً ۵-۶ کاراکتری هستن.\n"
            "🔄 کد رو دوباره چک کن.",
            parse_mode='Markdown'
        )
        return WAITING_CODE
    
    await update.message.reply_text("⏳ **دارم وارد میشم و اپ میسازم...**\n\n⏱️ کمی صبر کن...")
    
    # Login and create app
    result = login_and_create_app(phone, code)
    
    if result['status'] == 'success':
        existing_msg = "\n📌 *(اپ قبلاً ساخته شده بود)*" if result.get('existing') else ""
        
        await update.message.reply_text(
            f"{result['message']}{existing_msg}\n\n"
            f"🔑 **API ID:**\n"
            f"`{result['api_id']}`\n\n"
            f"🔐 **API Hash:**\n"
            f"`{result['api_hash']}`\n\n"
            f"{'─' * 30}\n\n"
            f"⚠️ **این اطلاعات رو حفظ کن!**\n\n"
            f"💡 **نحوه استفاده:**\n"
            f"1. کتابخانه `telethon` رو نصب کن:\n"
            f"   `pip install telethon`\n\n"
            f"2. کد نمونه:\n"
            f"```python\n"
            f"from telethon import TelegramClient\n\n"
            f"api_id = {result['api_id']}\n"
            f"api_hash = '{result['api_hash']}'\n"
            f"client = TelegramClient('session', api_id, api_hash)\n"
            f"```",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            result['message'],
            parse_mode='Markdown'
        )
    
    # Clean up
    delete_session(phone)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو عملیات"""
    phone = context.user_data.get('phone')
    if phone:
        delete_session(phone)
    
    await update.message.reply_text(
        "❌ **لغو شد.**\n\n🔄 برای شروع مجدد، /start بزنید.",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def my_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش اپ‌های ذخیره شده"""
    await update.message.reply_text(
        "📋 **اطلاعات اپ شما:**\n\n"
        "اگه قبلاً اپ ساختی، با /start و شماره‌ات میتونی اطلاعاتش رو ببینی.\n\n"
        "⚠️ اطلاعات API بعد از هر بار ساخت نمایش داده میشه و ذخیره نمیمونه.\n"
        "لطفاً اون‌ها رو یادداشت کن!",
        parse_mode='Markdown'
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنما"""
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode='Markdown'
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاها"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ **خطای غیرمنتظره رخ داد!**\n\n"
            "🔄 دوباره تلاش کن یا /start بزن.\n\n"
            f"📝 **جزئیات خطا:**\n`{str(context.error)[:200]}`",
            parse_mode='Markdown'
        )


def main():
    """راه‌اندازی ربات"""
    if not BOT_TOKEN:
        print("❌ TELEGRAM_API_BOT_TOKEN not set!")
        return
    
    print("🚀 Telegram API Creator Bot starting...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
                CallbackQueryHandler(button_callback, pattern='^(use_|new_phone)')
            ],
            WAITING_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("help", help_cmd)
        ],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("myapps", my_apps))
    app.add_error_handler(error_handler)
    
    print("✅ Bot is running!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
