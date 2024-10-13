# handlers/user_handlers.py
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters
)
from models import User
from utils.helpers import is_admin, sanitize_phone_number
from keyboards.user_keyboards import (
    main_menu_keyboard,
    country_selection_keyboard,
    contact_keyboard
)
from keyboards.admin_keyboards import user_approval_keyboard
from config import ADMIN_IDS, USER_DATA_DIR
import os
import logging

logger = logging.getLogger(__name__)

# تعریف حالات ConversationHandler
NAME, FAMILY_NAME, COUNTRY, PHONE, ID_CARD = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    db = context.bot_data['db']
    user = db.query(User).filter_by(telegram_id=user_id).first()
    if user:
        if user.is_verified:
            await update.message.reply_text(
                "✅ شما قبلاً ثبت‌نام کرده‌اید و حساب شما تأیید شده است.",
                reply_markup=main_menu_keyboard(is_admin=is_admin(user_id))
            )
            # می‌توانید منوی اصلی را فراخوانی کنید
        else:
            await update.message.reply_text(
                "⏳ حساب شما در انتظار تأیید است. لطفاً صبور باشید.",
                reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "👋 سلام! برای استفاده از ربات، لطفاً فرآیند احراز هویت را تکمیل کنید.\nلطفاً نام خود را وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text(
            "⚠️ نام نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:"
        )
        return NAME
    context.user_data['name'] = name
    await update.message.reply_text("👤 لطفاً نام خانوادگی خود را وارد کنید:")
    return FAMILY_NAME

async def get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    family_name = update.message.text.strip()
    if not family_name:
        await update.message.reply_text(
            "⚠️ نام خانوادگی نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:"
        )
        return FAMILY_NAME
    context.user_data['family_name'] = family_name
    await update.message.reply_text(
        "🌍 کشور محل سکونت خود را انتخاب کنید:",
        reply_markup=country_selection_keyboard()
    )
    return COUNTRY

async def get_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country = update.message.text.strip()
    if country not in ["🇮🇷 ایران", "🇹🇷 ترکیه"]:
        await update.message.reply_text(
            "⚠️ لطفاً یکی از گزینه‌های موجود را انتخاب کنید.",
            reply_markup=country_selection_keyboard()
        )
        return COUNTRY
    context.user_data['country'] = 'Iran' if country == "🇮🇷 ایران" else 'Turkey'
    await update.message.reply_text(
        "📱 لطفاً شماره تلفن خود را به اشتراک بگذارید:",
        reply_markup=contact_keyboard()
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        await update.message.reply_text(
            "⚠️ لطفاً شماره تلفن خود را ارسال کنید.",
            reply_markup=contact_keyboard()
        )
        return PHONE

    phone_number = sanitize_phone_number(contact.phone_number)
    logger.info(f"Received phone number: {contact.phone_number}")
    logger.info(f"Sanitized phone number: {phone_number}")

    if not phone_number or len(phone_number) < 10 or len(phone_number) > 15:
        await update.message.reply_text(
            "⚠️ شماره تلفن نامعتبر است. لطفاً یک شماره تلفن معتبر ارسال کنید:"
        )
        return PHONE

    context.user_data['phone'] = phone_number
    await update.message.reply_text(
        "📄 لطفاً تصویر کارت ملی یا پاسپورت خود را ارسال کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ID_CARD

async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً یک تصویر ارسال کنید.")
        return ID_CARD
    photo = update.message.photo[-1]
    file_size = photo.file_size
    if file_size > 5 * 1024 * 1024:
        await update.message.reply_text("⚠️ اندازه فایل بیش از حد مجاز است (حداکثر 5 مگابایت). لطفاً عکس کوچکتری ارسال کنید.")
        return ID_CARD

    # دانلود عکس کارت ملی یا پاسپورت
    photo_file = await photo.get_file()
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)
    photo_path = f"{USER_DATA_DIR}/{user_id}_id.jpg"
    await photo_file.download_to_drive(custom_path=photo_path)
    context.user_data['id_card'] = photo_path
    await update.message.reply_text("📥 اطلاعات شما دریافت شد و در انتظار تأیید ادمین است.")

    db = context.bot_data['db']
    user = User(
        telegram_id=user_id,
        name=context.user_data['name'],
        family_name=context.user_data['family_name'],
        country=context.user_data['country'],
        phone=context.user_data['phone'],
        is_verified=False
    )
    db.add(user)
    try:
        db.commit()
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره‌سازی اطلاعات کاربر: {e}")
        await update.message.reply_text("⚠️ خطا در ذخیره‌سازی اطلاعات شما. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END

    # اطلاع‌رسانی به ادمین‌ها
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"📋 کاربر جدید:\n"
                f"👤 نام: {user.name} {user.family_name}\n"
                f"🌍 کشور: {user.country}\n"
                f"📞 شماره تلفن: {user.phone}"
            )
        )
        with open(photo_path, 'rb') as photo_file_obj:
            await context.bot.send_photo(chat_id=admin_id, photo=photo_file_obj)
        await context.bot.send_message(
            chat_id=admin_id,
            text="🔄 لطفاً کاربر را تأیید یا رد کنید:",
            reply_markup=user_approval_keyboard(user.id)
        )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '⛔️ فرآیند لغو شد.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# سایر هندلرهای مربوط به کاربران را در این فایل اضافه کنید
