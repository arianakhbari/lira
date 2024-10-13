# handlers/user_handlers.py
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
from models import User
from utils.helpers import sanitize_phone_number

logger = logging.getLogger(__name__)

# تعریف Enum برای حالت‌های ConversationHandler
TERMS, NAME, FAMILY_NAME, COUNTRY, PHONE, ID_CARD = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    هندلر برای دستور /start. ارسال شرایط و قوانین به کاربر.
    """
    keyboard = [
        [InlineKeyboardButton("✅ قبول شرایط و قوانین", callback_data='accept_terms')],
        [InlineKeyboardButton("❌ رد شرایط و قوانین", callback_data='decline_terms')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    terms_text = (
        "📜 **شرایط و قوانین استفاده از ربات**\n\n"
        "1. **قانون اول:** کاربران باید اطلاعات صحیح وارد کنند.\n"
        "2. **قانون دوم:** ارسال فیش‌های پرداخت باید واقعی باشد.\n"
        "3. **قانون سوم:** هرگونه سوء استفاده منجر به مسدود شدن حساب کاربری می‌شود.\n\n"
        "برای ادامه استفاده از ربات، لطفاً شرایط و قوانین را بپذیرید."
    )
    
    await update.message.reply_text(
        terms_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return TERMS

async def terms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    هندلر برای پاسخ‌های مربوط به پذیرش یا رد شرایط و قوانین.
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    
    user_id = update.effective_user.id
    db = context.bot_data['db']
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if data == 'accept_terms':
        if user:
            user.has_accepted_terms = True
            db.commit()
            await query.edit_message_text("✅ شما شرایط و قوانین را پذیرفتید.\nخوش آمدید! لطفاً فرآیند ثبت‌نام را ادامه دهید.")
        else:
            # اگر کاربر یافت نشد، ایجاد یک کاربر جدید با پذیرش شرایط
            new_user = User(
                telegram_id=user_id,
                name="",
                family_name="",
                country="",
                phone="",
                id_card="",
                is_verified=False,
                has_accepted_terms=True
            )
            db.add(new_user)
            db.commit()
            await query.edit_message_text("✅ شما شرایط و قوانین را پذیرفتید.\nخوش آمدید! لطفاً فرآیند ثبت‌نام را ادامه دهید.")
        # شروع فرآیند ثبت‌نام
        keyboard = [
            [InlineKeyboardButton("شروع ثبت‌نام", callback_data='start_registration')],
            [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "برای شروع ثبت‌نام، روی گزینه زیر کلیک کنید.",
            reply_markup=reply_markup
        )
        return NAME  # مرحله بعدی ConversationHandler
    elif data == 'decline_terms':
        await query.edit_message_text("❌ شما شرایط و قوانین را پذیرفتن نکردید. متأسفانه نمی‌توانید از ربات استفاده کنید.")
        return ConversationHandler.END

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت نام کاربر.
    """
    name = update.message.text.strip()
    context.user_data['name'] = name
    
    keyboard = [
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "لطفاً نام خانوادگی خود را وارد کنید:",
        reply_markup=reply_markup
    )
    return FAMILY_NAME

async def get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت نام خانوادگی کاربر.
    """
    family_name = update.message.text.strip()
    context.user_data['family_name'] = family_name
    
    keyboard = [
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "لطفاً کشور خود را وارد کنید:",
        reply_markup=reply_markup
    )
    return COUNTRY

async def get_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت کشور کاربر.
    """
    country = update.message.text.strip()
    context.user_data['country'] = country
    
    keyboard = [
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "لطفاً شماره تلفن خود را ارسال کنید:",
        reply_markup=reply_markup
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت شماره تلفن کاربر.
    """
    phone = update.message.contact.phone_number
    phone = sanitize_phone_number(phone)
    
    if not (10 <= len(phone) <= 15):
        await update.message.reply_text(
            "⚠️ شماره تلفن باید بین ۱۰ تا ۱۵ رقم باشد. لطفاً دوباره ارسال کنید:"
        )
        return PHONE
    
    context.user_data['phone'] = phone
    
    keyboard = [
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "لطفاً تصویر کارت ملی خود را ارسال کنید:",
        reply_markup=reply_markup
    )
    return ID_CARD

async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت تصویر کارت ملی کاربر.
    """
    photo = update.message.photo[-1]
    file_size = photo.file_size
    if file_size > 5 * 1024 * 1024:
        await update.message.reply_text("⚠️ اندازه فایل بیش از حد مجاز است (حداکثر 5 مگابایت). لطفاً تصویر کوچکتری ارسال کنید.")
        return ID_CARD
    
    photo_file = await photo.get_file()
    id_card_path = os.path.join('id_cards', f"{update.effective_user.id}_id.jpg")
    if not os.path.exists('id_cards'):
        os.makedirs('id_cards')
    await photo_file.download_to_drive(custom_path=id_card_path)
    
    context.user_data['id_card'] = id_card_path
    
    # ذخیره کاربر در دیتابیس
    db = context.bot_data['db']
    user = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
    if user:
        user.name = context.user_data['name']
        user.family_name = context.user_data['family_name']
        user.country = context.user_data['country']
        user.phone = context.user_data['phone']
        user.id_card = context.user_data['id_card']
        user.is_verified = False  # نیاز به تأیید توسط ادمین
        db.commit()
    else:
        new_user = User(
            telegram_id=update.effective_user.id,
            name=context.user_data['name'],
            family_name=context.user_data['family_name'],
            country=context.user_data['country'],
            phone=context.user_data['phone'],
            id_card=context.user_data['id_card'],
            is_verified=False,
            has_accepted_terms=True  # از آنجا که شرایط پذیرفته شده است
        )
        db.add(new_user)
        db.commit()
    
    await update.message.reply_text("✅ ثبت‌نام شما با موفقیت انجام شد و در انتظار تأیید توسط ادمین‌ها است.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    هندلر برای لغو فرآیند.
    """
    user = update.effective_user
    await update.message.reply_text("❌ فرآیند لغو شد.")
    return ConversationHandler.END
