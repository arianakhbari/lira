import logging
import os
import re
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
    ContextTypes
)
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات و آیدی‌های ادمین‌ها از متغیرهای محیطی خوانده می‌شوند
TOKEN = '7732549586:AAH3XpSaeY8m3BTzhCVZGlEJzwGz-okLmos'  # جایگزین با توکن ربات خود
ADMIN_IDS = [179044957]  # جایگزین با آیدی‌های ادمین‌ها

# تنظیمات دیتابیس
engine = create_engine('sqlite:///bot.db', connect_args={'check_same_thread': False})
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

# تعریف مدل‌های دیتابیس
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)
    family_name = Column(String, nullable=False)
    country = Column(String, nullable=False)  # 'Iran' یا 'Turkey'
    phone = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)

class BankAccount(Base):
    __tablename__ = 'bank_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    bank_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    country = Column(String, nullable=False)  # 'Iran' یا 'Turkey'
    is_verified = Column(Boolean, default=False)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)  # 'buy' یا 'sell'
    amount = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default='pending')  # 'pending', 'awaiting_payment', 'payment_received', 'confirmed', 'canceled', 'done', 'transaction_completed'
    payment_proof = Column(String, nullable=True)  # مسیر فایل فیش پرداخت
    admin_payment_proof = Column(String, nullable=True)  # مسیر فایل فیش واریز ادمین

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    buy_rate = Column(Float, default=1000.0)   # نرخ خرید (تومان به لیر)
    sell_rate = Column(Float, default=950.0)   # نرخ فروش (لیر به تومان)
    buy_enabled = Column(Boolean, default=True)  # فعال یا غیرفعال بودن خرید
    sell_enabled = Column(Boolean, default=True)  # فعال یا غیرفعال بودن فروش
    admin_iran_bank_account = Column(String, nullable=True)  # اطلاعات حساب بانکی ایران ادمین
    admin_turkey_bank_account = Column(String, nullable=True)  # اطلاعات حساب بانکی ترکیه ادمین

# ایجاد جداول در دیتابیس
Base.metadata.create_all(engine)

# تعریف حالات ConversationHandler
(
    # مراحل ثبت‌نام کاربران
    NAME, FAMILY_NAME, COUNTRY, PHONE, ID_CARD,

    # مراحل تراکنش
    SELECT_TRANSACTION_TYPE, TRANSACTION_AMOUNT_TYPE, AMOUNT, CONFIRM_TRANSACTION,
    SEND_PAYMENT_PROOF,

    # مراحل مدیریت حساب‌های بانکی کاربران
    BANK_COUNTRY, BANK_NAME, BANK_ACCOUNT_NUMBER,

    # مراحل تنظیمات ادمین
    SET_BUY_RATE, SET_SELL_RATE, TOGGLE_BUY, TOGGLE_SELL, SET_ADMIN_BANK_INFO
) = range(18)  # تغییر از range(19) به range(18)

def is_admin(user_id):
    return user_id in ADMIN_IDS

# تابع شروع
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if user:
        if user.is_verified:
            await update.message.reply_text(
                "✅ شما قبلاً ثبت‌نام کرده‌اید و حساب شما تأیید شده است.",
                reply_markup=ReplyKeyboardRemove()
            )
            await main_menu(update, context)
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

# دریافت نام
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

# دریافت نام خانوادگی
async def get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    family_name = update.message.text.strip()
    if not family_name:
        await update.message.reply_text(
            "⚠️ نام خانوادگی نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:"
        )
        return FAMILY_NAME
    context.user_data['family_name'] = family_name
    keyboard = [
        [KeyboardButton("🇮🇷 ایران"), KeyboardButton("🇹🇷 ترکیه")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "🌍 کشور محل سکونت خود را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return COUNTRY

# دریافت کشور
async def get_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country = update.message.text.strip()
    if country not in ["🇮🇷 ایران", "🇹🇷 ترکیه"]:
        await update.message.reply_text(
            "⚠️ لطفاً یکی از گزینه‌های موجود را انتخاب کنید.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("🇮🇷 ایران"), KeyboardButton("🇹🇷 ترکیه")]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return COUNTRY
    context.user_data['country'] = 'Iran' if country == "🇮🇷 ایران" else 'Turkey'
    keyboard = [
        [KeyboardButton("📞 ارسال شماره تلفن", request_contact=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "📱 لطفاً شماره تلفن خود را به اشتراک بگذارید:",
        reply_markup=reply_markup
    )
    return PHONE

# دریافت شماره تلفن با اصلاحات
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        await update.message.reply_text(
            "⚠️ لطفاً شماره تلفن خود را ارسال کنید.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📞 ارسال شماره تلفن", request_contact=True)]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return PHONE

    # حذف کاراکترهای غیرعددی
    phone_number = ''.join(filter(str.isdigit, contact.phone_number))
    logger.info(f"Received phone number: {contact.phone_number}")
    logger.info(f"Sanitized phone number: {phone_number}")

    # اعتبارسنجی شماره تلفن
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

# دریافت تصویر کارت ملی یا پاسپورت
async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً یک تصویر ارسال کنید.")
        return ID_CARD
    photo = update.message.photo[-1]
    file_size = photo.file_size
    if file_size > 5 * 1024 * 1024:  # حداکثر 5 مگابایت
        await update.message.reply_text("⚠️ اندازه فایل بیش از حد مجاز است (حداکثر 5 مگابایت). لطفاً عکس کوچکتری ارسال کنید.")
        return ID_CARD
    # بررسی نوع فایل (مثلاً JPEG یا PNG)
    mime_type = photo.mime_type if hasattr(photo, 'mime_type') else 'image/jpeg'  # فرض بر JPEG
    if not mime_type.startswith('image/'):
        await update.message.reply_text("⚠️ فقط فایل‌های تصویری مجاز هستند. لطفاً یک تصویر ارسال کنید.")
        return ID_CARD
    photo_file = await photo.get_file()
    if not os.path.exists('user_data'):
        os.makedirs('user_data')
    photo_path = f"user_data/{user_id}_id.jpg"
    await photo_file.download_to_drive(custom_path=photo_path)
    context.user_data['id_card'] = photo_path
    await update.message.reply_text("📥 اطلاعات شما دریافت شد و در انتظار تأیید ادمین است.")

    # ذخیره اطلاعات کاربر در دیتابیس
    user = User(
        telegram_id=user_id,
        name=context.user_data['name'],
        family_name=context.user_data['family_name'],
        country=context.user_data['country'],
        phone=context.user_data['phone'],
        is_verified=False
    )
    session.add(user)
    try:
        session.commit()
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره‌سازی اطلاعات کاربر: {e}")
        await update.message.reply_text("⚠️ خطا در ذخیره‌سازی اطلاعات شما. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END

    # اطلاع رسانی به ادمین‌ها
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
        keyboard = [
            [InlineKeyboardButton("✅ تأیید", callback_data=f'approve_user_{user.id}'),
             InlineKeyboardButton("❌ رد", callback_data=f'reject_user_{user.id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"🔄 لطفاً کاربر {user.id} را تأیید یا رد کنید:",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

# لغو فرآیند
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '⛔️ فرآیند لغو شد.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# منوی اصلی
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["💱 لیر"],
        ["🏦 مدیریت حساب‌های بانکی"],
        ["📜 تاریخچه تراکنش‌ها"],
        ["📞 پشتیبانی"]
    ]
    if is_admin(update.effective_user.id):
        keyboard.append(["⚙️ پنل مدیریت"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📂 به منوی اصلی خوش آمدید. لطفاً یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=reply_markup
    )

# هندلر پیام‌های کاربر
async def user_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()

    if not user:
        await update.message.reply_text("❌ لطفاً ابتدا فرآیند احراز هویت را تکمیل کنید با استفاده از دستور /start.")
        return ConversationHandler.END

    if text == "💱 لیر":
        settings = session.query(Settings).first()
        if not settings:
            await update.message.reply_text("⚠️ نرخ‌ها تنظیم نشده‌اند. لطفاً بعداً تلاش کنید.")
            return ConversationHandler.END

        # بررسی فعال بودن خرید و فروش
        if not settings.buy_enabled and not settings.sell_enabled:
            await update.message.reply_text("⚠️ خرید و فروش در حال حاضر غیر فعال است.")
            return ConversationHandler.END

        # نمایش نرخ‌ها با ایموجی ترکیه
        buy_status = "✅ فعال" if settings.buy_enabled else "❌ غیرفعال"
        sell_status = "✅ فعال" if settings.sell_enabled else "❌ غیرفعال"
        text_message = (
            f"💱 **نرخ‌های فعلی لیر:**\n\n"
            f"🛒 **خرید لیر:** {settings.buy_rate} تومان به ازای هر لیر [{buy_status}]\n"
            f"💸 **فروش لیر:** {settings.sell_rate} تومان به ازای هر لیر [{sell_status}]\n\n"
            f"🔽 لطفاً نوع تراکنش خود را انتخاب کنید:"
        )
        keyboard = []
        if settings.buy_enabled:
            keyboard.append([KeyboardButton("🛒 خرید لیر")])
        if settings.sell_enabled:
            keyboard.append([KeyboardButton("💸 فروش لیر")])
        keyboard.append(["↩️ بازگشت به منوی اصلی"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            text_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return SELECT_TRANSACTION_TYPE

    elif text == "🏦 مدیریت حساب‌های بانکی":
        await manage_bank_accounts(update, context)
        return ConversationHandler.END
    elif text == "📜 تاریخچه تراکنش‌ها":
        await show_transaction_history(update, context)
        return ConversationHandler.END
    elif text == "📞 پشتیبانی":
        await update.message.reply_text("برای پشتیبانی با ما تماس بگیرید: support@example.com")
        return ConversationHandler.END
    elif text == "⚙️ پنل مدیریت" and is_admin(user_id):
        await admin_panel(update, context)
        return ConversationHandler.END
    else:
        # مدیریت انتخاب بعد از نمایش نرخ‌ها
        if text in ["🛒 خرید لیر", "💸 فروش لیر"]:
            transaction_type = 'buy' if text == "🛒 خرید لیر" else 'sell'
            settings = session.query(Settings).first()
            if transaction_type == 'buy' and not settings.buy_enabled:
                await update.message.reply_text("⚠️ خرید در حال حاضر غیر فعال است.")
                return ConversationHandler.END
            if transaction_type == 'sell' and not settings.sell_enabled:
                await update.message.reply_text("⚠️ فروش در حال حاضر غیر فعال است.")
                return ConversationHandler.END

            # انتخاب نوع وارد کردن مقدار: تومان یا لیر
            keyboard = [
                [InlineKeyboardButton("💰 وارد کردن به تومان", callback_data='amount_toman'),
                 InlineKeyboardButton("💱 وارد کردن به لیر", callback_data='amount_lira')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🔢 لطفاً انتخاب کنید که مقدار را به تومان یا لیر وارد کنید:",
                reply_markup=reply_markup
            )
            context.user_data['transaction_type'] = transaction_type
            return TRANSACTION_AMOUNT_TYPE
        elif text == "➕ افزودن حساب جدید":
            await add_bank_account(update, context)
            return BANK_COUNTRY
        elif text in ["📈 تنظیم نرخ خرید", "📉 تنظیم نرخ فروش"] and is_admin(user_id):
            if text == "📈 تنظیم نرخ خرید":
                await set_buy_rate(update, context)
                return SET_BUY_RATE
            else:
                await set_sell_rate(update, context)
                return SET_SELL_RATE
        elif text == "↩️ بازگشت به منوی اصلی":
            await main_menu(update, context)
            return ConversationHandler.END
        else:
            await update.message.reply_text("⚠️ دستور ناشناخته. لطفاً یکی از گزینه‌های منو را انتخاب کنید.")
    return ConversationHandler.END

# هندلر انتخاب نوع وارد کردن مقدار
async def transaction_amount_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'amount_toman':
        context.user_data['amount_type'] = 'toman'
        await query.edit_message_text("🔢 لطفاً مقدار تومان را وارد کنید:")
    elif data == 'amount_lira':
        context.user_data['amount_type'] = 'lira'
        await query.edit_message_text("🔢 لطفاً مقدار لیر را وارد کنید:")
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
        return ConversationHandler.END
    return AMOUNT

# دریافت مقدار تراکنش
async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.strip()
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError("مقدار باید بزرگ‌تر از صفر باشد.")
        if amount > 100000:  # مثال: حداکثر مقدار تراکنش
            await update.message.reply_text("⚠️ مقدار وارد شده بیش از حد مجاز است. لطفاً مقدار کمتری وارد کنید:")
            return AMOUNT
        if amount < 10:  # مثال: حداقل مقدار تراکنش
            await update.message.reply_text("⚠️ مقدار وارد شده کمتر از حد مجاز است. لطفاً مقدار بیشتری وارد کنید:")
            return AMOUNT
        context.user_data['amount'] = amount

        # ارسال پیام تأیید نهایی به کاربر
        transaction_type = context.user_data['transaction_type']
        amount_type = context.user_data['amount_type']
        settings = session.query(Settings).first()
        user = session.query(User).filter_by(telegram_id=update.effective_user.id).first()

        if transaction_type == 'buy':
            rate = settings.buy_rate
            if amount_type == 'toman':
                lira_amount = amount / rate
                total_price = amount
                summary = (
                    f"💰 **خرید لیر**\n"
                    f"🔢 مقدار: {lira_amount:.2f} لیر\n"
                    f"💵 نرخ خرید: {rate} تومان به ازای هر لیر\n"
                    f"💸 مبلغ کل: {total_price:.2f} تومان\n\n"
                    f"آیا از انجام این تراکنش مطمئن هستید؟"
                )
            else:
                lira_amount = amount
                total_price = amount * rate
                summary = (
                    f"💰 **خرید لیر**\n"
                    f"🔢 مقدار: {lira_amount} لیر\n"
                    f"💵 نرخ خرید: {rate} تومان به ازای هر لیر\n"
                    f"💸 مبلغ کل: {total_price:.2f} تومان\n\n"
                    f"آیا از انجام این تراکنش مطمئن هستید؟"
                )
        else:
            rate = settings.sell_rate
            if amount_type == 'toman':
                lira_amount = amount / rate
                total_price = amount
                summary = (
                    f"💸 **فروش لیر**\n"
                    f"🔢 مقدار: {lira_amount:.2f} لیر\n"
                    f"💵 نرخ فروش: {rate} تومان به ازای هر لیر\n"
                    f"💰 مبلغ کل: {total_price:.2f} تومان\n\n"
                    f"آیا از انجام این تراکنش مطمئن هستید؟"
                )
            else:
                lira_amount = amount
                total_price = amount * rate
                summary = (
                    f"💸 **فروش لیر**\n"
                    f"🔢 مقدار: {lira_amount} لیر\n"
                    f"💵 نرخ فروش: {rate} تومان به ازای هر لیر\n"
                    f"💰 مبلغ کل: {total_price:.2f} تومان\n\n"
                    f"آیا از انجام این تراکنش مطمئن هستید؟"
                )

        keyboard = [
            [InlineKeyboardButton("✅ تایید", callback_data='confirm_transaction')],
            [InlineKeyboardButton("❌ لغو", callback_data='cancel_transaction')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            summary,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return CONFIRM_TRANSACTION
    except ValueError as ve:
        await update.message.reply_text(f"⚠️ خطا: {ve}. لطفاً یک مقدار معتبر وارد کنید.")
        return AMOUNT
    except Exception as e:
        logger.error(f"❌ خطا در handle_amount: {e}")
        await update.message.reply_text("⚠️ خطایی رخ داده است. لطفاً دوباره تلاش کنید.")
        return AMOUNT

# تایید نهایی تراکنش توسط کاربر
async def confirm_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'confirm_transaction':
        transaction_type = context.user_data['transaction_type']
        amount = context.user_data['amount']
        amount_type = context.user_data['amount_type']  # 'toman' یا 'lira'
        settings = session.query(Settings).first()
        user = session.query(User).filter_by(telegram_id=query.from_user.id).first()
        if not user:
            await query.edit_message_text("❌ شما هنوز ثبت‌نام نکرده‌اید.")
            return ConversationHandler.END

        # محاسبه مبلغ بر اساس نوع وارد کردن
        if amount_type == 'toman':
            if transaction_type == 'buy':
                # کاربر مبلغ تومانی را وارد کرده و می‌خواهد لیر بخرد
                rate = settings.buy_rate  # نرخ خرید
                lira_amount = amount / rate
                total_price = amount  # مبلغ تومان
            else:
                # کاربر مبلغ تومانی را وارد کرده و می‌خواهد لیر بفروشد
                rate = settings.sell_rate  # نرخ فروش
                lira_amount = amount / rate
                total_price = amount  # مبلغ تومان
        else:
            if transaction_type == 'buy':
                # کاربر مبلغ لیری را وارد کرده و می‌خواهد لیر بخرد
                rate = settings.buy_rate
                lira_amount = amount
                total_price = amount * rate  # مبلغ تومان
            else:
                # کاربر مبلغ لیری را وارد کرده و می‌خواهد لیر بفروشد
                rate = settings.sell_rate
                lira_amount = amount
                total_price = amount * rate  # مبلغ تومان

        # ایجاد تراکنش
        transaction = Transaction(
            user_id=user.id,
            transaction_type=transaction_type,
            amount=lira_amount,
            total_price=total_price,
            status='awaiting_payment'
        )
        session.add(transaction)
        try:
            session.commit()
        except Exception as e:
            logger.error(f"❌ خطا در ثبت تراکنش: {e}")
            await query.edit_message_text("⚠️ خطا در ثبت تراکنش. لطفاً دوباره تلاش کنید.")
            return ConversationHandler.END

        # ارسال اطلاعات بانکی ادمین به مشتری
        if transaction_type == 'buy':
            # ارسال شماره ایبان ترکیه و نام صاحب حساب بانکی ترکیه ادمین
            admin_bank_info = settings.admin_turkey_bank_account or "🔸 شماره ایبان ترکیه: TRXXXXXXXXXXXXXX\n🔸 نام صاحب حساب: ادمین"
            payment_instruction = (
                f"📥 **دستورالعمل پرداخت:**\n\n"
                f"لطفاً مبلغ **{total_price:.2f} تومان** را به شماره ایبان زیر واریز کنید:\n\n"
                f"{admin_bank_info}\n\n"
                f"📸 پس از واریز، لطفاً فیش پرداخت خود را ارسال کنید."
            )
        else:
            # ارسال شماره شبا، شماره کارت و صاحب حساب بانکی ایران ادمین
            admin_bank_info = settings.admin_iran_bank_account or "🔸 شماره شبا ایران: IRXXXXXXXXXXXXXX\n🔸 شماره کارت: XXXXXXXXXXXXXXXX\n🔸 نام صاحب حساب: ادمین"
            payment_instruction = (
                f"📥 **دستورالعمل پرداخت:**\n\n"
                f"لطفاً مبلغ **{total_price:.2f} تومان** را به شماره شبا زیر واریز کنید:\n\n"
                f"{admin_bank_info}\n\n"
                f"📸 پس از واریز، لطفاً فیش پرداخت خود را ارسال کنید."
            )

        await query.edit_message_text(
            payment_instruction,
            parse_mode='Markdown'
        )

        # ارسال پیام به ادمین‌ها برای بررسی فیش پرداخت
        for admin_id in ADMIN_IDS:
            transaction_details = (
                f"🔔 **تراکنش جدید:**\n\n"
                f"👤 **کاربر:** {user.name} {user.family_name} (ID: {user.id})\n"
                f"🌍 **کشور:** {'ایران' if user.country == 'Iran' else 'ترکیه'}\n"
                f"📞 **شماره تلفن:** {user.phone}\n\n"
                f"💱 **نوع تراکنش:** {'خرید' if transaction_type == 'buy' else 'فروش'} لیر\n"
                f"🔢 **مقدار:** {transaction.amount} لیر\n"
                f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
                f"🔄 **وضعیت:** {transaction.status.capitalize()}.\n\n"
                f"📥 **دستورالعمل پرداخت:**\n{payment_instruction}"
            )
            keyboard = [
                [InlineKeyboardButton("📸 ارسال فیش پرداخت", callback_data=f'send_payment_proof_{transaction.id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=admin_id,
                text=transaction_details,
                reply_markup=reply_markup
            )
        return ConversationHandler.END

# ارسال فیش پرداخت توسط کاربر (مرحله بعدی بعد از ارسال فیش)
async def send_payment_proof_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('send_payment_proof_'):
        transaction_id = int(data.split('_')[-1])
        transaction = session.query(Transaction).filter_by(id=transaction_id).first()
        if not transaction or transaction.status != 'awaiting_payment':
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا در وضعیت مناسبی قرار ندارد.")
            return ConversationHandler.END

        # درخواست فیش پرداخت از کاربر
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="📸 لطفاً فیش پرداخت خود را ارسال کنید."
        )
        # ذخیره تراکنش در context برای مرحله بعد
        context.user_data['current_transaction_id'] = transaction_id
        return SEND_PAYMENT_PROOF
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
        return ConversationHandler.END

# دریافت فیش پرداخت
async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    transaction_id = context.user_data.get('current_transaction_id')
    transaction = session.query(Transaction).filter_by(id=transaction_id, user_id=user_id).first()
    if not transaction:
        await update.message.reply_text("⚠️ تراکنش یافت نشد.")
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً یک تصویر فیش پرداخت ارسال کنید.")
        return SEND_PAYMENT_PROOF

    photo = update.message.photo[-1]
    file_size = photo.file_size
    if file_size > 5 * 1024 * 1024:
        await update.message.reply_text("⚠️ اندازه فایل بیش از حد مجاز است (حداکثر 5 مگابایت). لطفاً فیش کوچکتری ارسال کنید.")
        return SEND_PAYMENT_PROOF

    # دانلود فیش پرداخت
    photo_file = await photo.get_file()
    if not os.path.exists('payment_proofs'):
        os.makedirs('payment_proofs')
    photo_path = f"payment_proofs/{transaction_id}_payment.jpg"
    await photo_file.download_to_drive(custom_path=photo_path)
    transaction.payment_proof = photo_path
    transaction.status = 'payment_received'
    session.commit()

    await update.message.reply_text("✅ فیش پرداخت شما دریافت شد و در انتظار بررسی ادمین است.")

    # اطلاع رسانی به ادمین‌ها
    for admin_id in ADMIN_IDS:
        user = session.query(User).filter_by(id=transaction.user_id).first()
        transaction_details = (
            f"🔔 **فیش پرداخت برای تراکنش {transaction.id} ارسال شده است.**\n\n"
            f"👤 **کاربر:** {user.name} {user.family_name} (ID: {user.id})\n"
            f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
            f"🔢 **مقدار:** {transaction.amount} لیر\n"
            f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
            f"🔄 **وضعیت:** {transaction.status.capitalize()}.\n\n"
            f"📸 **فیش پرداخت کاربر:**"
        )
        keyboard = [
            [InlineKeyboardButton("✅ تایید پرداخت", callback_data=f'approve_payment_{transaction.id}'),
             InlineKeyboardButton("❌ رد پرداخت", callback_data=f'reject_payment_{transaction.id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=transaction_details,
            reply_markup=reply_markup
        )
        with open(photo_path, 'rb') as photo_file_obj:
            await context.bot.send_photo(chat_id=admin_id, photo=photo_file_obj)
    return ConversationHandler.END

# تایید یا رد پرداخت توسط ادمین
async def admin_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('approve_payment_'):
        transaction_id = int(data.split('_')[-1])
        transaction = session.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'payment_received':
            transaction.status = 'confirmed'
            session.commit()
            user = session.query(User).filter_by(id=transaction.user_id).first()

            # ارسال اطلاعات حساب بانکی ادمین به کاربر
            settings = session.query(Settings).first()
            if transaction.transaction_type == 'buy':
                admin_bank_info = settings.admin_turkey_bank_account or "🔸 شماره ایبان ترکیه: TRXXXXXXXXXXXXXX\n🔸 نام صاحب حساب: ادمین"
            else:
                admin_bank_info = settings.admin_iran_bank_account or "🔸 شماره شبا ایران: IRXXXXXXXXXXXXXX\n🔸 شماره کارت: XXXXXXXXXXXXXXXX\n🔸 نام صاحب حساب: ادمین"

            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"✅ **پرداخت شما تأیید شد!**\n\n"
                    f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
                    f"🔢 **مقدار:** {transaction.amount} لیر\n"
                    f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n\n"
                    f"📥 **اطلاعات بانکی ادمین:**\n{admin_bank_info}\n\n"
                    f"🔄 لطفاً مبلغ را به حساب بانکی ادمین واریز کنید و سپس فیش واریز را ارسال کنید."
                )
            )

            # درخواست فیش واریز از کاربر
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text="📸 لطفاً فیش واریز خود را ارسال کنید."
            )

            await query.edit_message_text("✅ پرداخت تأیید شد. اطلاعات بانکی ادمین به کاربر ارسال شد.")
        else:
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا قبلاً تأیید شده است.")
    elif data.startswith('reject_payment_'):
        transaction_id = int(data.split('_')[-1])
        transaction = session.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'payment_received':
            transaction.status = 'canceled'
            session.commit()
            user = session.query(User).filter_by(id=transaction.user_id).first()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"❌ **پرداخت شما رد شد.**\n\n"
                    f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
                    f"🔢 **مقدار:** {transaction.amount} لیر\n"
                    f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n\n"
                    f"🔄 وضعیت تراکنش: {transaction.status.capitalize()}."
                )
            )
            await query.edit_message_text("❌ پرداخت رد شد.")
        else:
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا قبلاً تأیید شده است.")
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
    return ConversationHandler.END

# ارسال فیش واریز از کاربر پس از تأیید پرداخت توسط ادمین
async def receive_admin_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        await update.message.reply_text("❌ تراکنش یافت نشد.")
        return ConversationHandler.END

    # یافتن تراکنش‌های تایید شده و در انتظار واریز
    transaction = session.query(Transaction).filter_by(user_id=user.id, status='confirmed').first()
    if not transaction:
        await update.message.reply_text("❌ تراکنش یافت نشد یا در وضعیت مناسبی قرار ندارد.")
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً یک تصویر فیش واریز ارسال کنید.")
        return SEND_PAYMENT_PROOF

    photo = update.message.photo[-1]
    file_size = photo.file_size
    if file_size > 5 * 1024 * 1024:
        await update.message.reply_text("⚠️ اندازه فایل بیش از حد مجاز است (حداکثر 5 مگابایت). لطفاً فیش کوچکتری ارسال کنید.")
        return SEND_PAYMENT_PROOF

    # دانلود فیش واریز
    photo_file = await photo.get_file()
    if not os.path.exists('admin_payment_proofs'):
        os.makedirs('admin_payment_proofs')
    photo_path = f"admin_payment_proofs/{transaction.id}_admin_payment.jpg"
    await photo_file.download_to_drive(custom_path=photo_path)
    transaction.admin_payment_proof = photo_path
    transaction.status = 'transaction_completed'
    session.commit()

    await update.message.reply_text("✅ فیش واریز شما دریافت شد و در انتظار تأیید ادمین است.")

    # اطلاع رسانی به ادمین‌ها
    for admin_id in ADMIN_IDS:
        user = session.query(User).filter_by(id=transaction.user_id).first()
        transaction_details = (
            f"🔔 **فیش واریز برای تراکنش {transaction.id} ارسال شده است.**\n\n"
            f"👤 **کاربر:** {user.name} {user.family_name} (ID: {user.id})\n"
            f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
            f"🔢 **مقدار:** {transaction.amount} لیر\n"
            f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n\n"
            f"📸 **فیش واریز ادمین:**"
        )
        keyboard = [
            [InlineKeyboardButton("✅ تایید تراکنش", callback_data=f'complete_transaction_{transaction.id}'),
             InlineKeyboardButton("❌ لغو تراکنش", callback_data=f'cancel_transaction_{transaction.id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=transaction_details,
            reply_markup=reply_markup
        )
        with open(photo_path, 'rb') as photo_file_obj:
            await context.bot.send_photo(chat_id=admin_id, photo=photo_file_obj)
    return ConversationHandler.END

# تایید یا لغو تراکنش توسط ادمین پس از ارسال فیش واریز ادمین
async def admin_final_confirm_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('complete_transaction_'):
        transaction_id = int(data.split('_')[-1])
        transaction = session.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'transaction_completed':
            transaction.status = 'done'
            session.commit()
            user = session.query(User).filter_by(id=transaction.user_id).first()

            # ارسال پیام به کاربر درباره تکمیل تراکنش
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"✅ **تراکنش شما به طور کامل انجام شد!**\n\n"
                    f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
                    f"🔢 **مقدار:** {transaction.amount} لیر\n"
                    f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
                    f"🔄 **وضعیت تراکنش:** {transaction.status.capitalize()}."
                )
            )
            await query.edit_message_text("✅ تراکنش تکمیل شد.")
        else:
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا قبلاً تکمیل شده است.")
    elif data.startswith('cancel_transaction_'):
        transaction_id = int(data.split('_')[-1])
        transaction = session.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'transaction_completed':
            transaction.status = 'canceled'
            session.commit()
            user = session.query(User).filter_by(id=transaction.user_id).first()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"❌ **تراکنش شما لغو شد.**\n\n"
                    f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
                    f"🔢 **مقدار:** {transaction.amount} لیر\n"
                    f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
                    f"🔄 **وضعیت تراکنش:** {transaction.status.capitalize()}."
                )
            )
            await query.edit_message_text("❌ تراکنش لغو شد.")
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
    return ConversationHandler.END

# مدیریت حساب‌های بانکی
async def manage_bank_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        await update.message.reply_text("❌ شما هنوز ثبت‌نام نکرده‌اید.")
        return
    accounts = session.query(BankAccount).filter_by(user_id=user.id).all()
    if accounts:
        text = "🏦 **حساب‌های بانکی شما:**\n"
        for account in accounts:
            status = "✅ تأیید شده" if account.is_verified else "⏳ در انتظار تأیید"
            country = "🇮🇷 ایران" if account.country == 'Iran' else "🇹🇷 ترکیه"
            text += f"- {account.bank_name} {country}: {account.account_number} [{status}]\n"
    else:
        text = "❌ شما هیچ حساب بانکی ثبت‌شده‌ای ندارید."
    keyboard = [
        ["➕ افزودن حساب جدید"],
        ["↩️ بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

# افزودن حساب بانکی جدید
async def add_bank_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🏦 حساب بانکی ایران"), KeyboardButton("🏦 حساب بانکی ترکیه")],
        ["↩️ بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "🏦 لطفاً نوع حساب بانکی خود را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return BANK_COUNTRY

# دریافت کشور حساب بانکی
async def get_bank_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country = update.message.text.strip()
    if country not in ["🏦 حساب بانکی ایران", "🏦 حساب بانکی ترکیه"]:
        await update.message.reply_text(
            "⚠️ لطفاً یکی از گزینه‌های موجود را انتخاب کنید.",
            reply_markup=ReplyKeyboardMarkup(
                [["🏦 حساب بانکی ایران", "🏦 حساب بانکی ترکیه"]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return BANK_COUNTRY
    context.user_data['bank_country'] = 'Iran' if country == "🏦 حساب بانکی ایران" else 'Turkey'
    await update.message.reply_text(
        "🏦 لطفاً نام بانک را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return BANK_NAME

# دریافت نام بانک
async def get_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bank_name = update.message.text.strip()
    if not bank_name:
        await update.message.reply_text("⚠️ نام بانک نمی‌تواند خالی باشد. لطفاً دوباره وارد کنید:")
        return BANK_NAME
    context.user_data['bank_name'] = bank_name
    await update.message.reply_text(
        "💳 لطفاً شماره حساب را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return BANK_ACCOUNT_NUMBER

# دریافت شماره حساب بانکی
async def get_bank_account_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_number = update.message.text.strip()
    if not account_number.isdigit():
        await update.message.reply_text("⚠️ شماره حساب باید شامل اعداد باشد. لطفاً دوباره تلاش کنید:")
        return BANK_ACCOUNT_NUMBER
    if len(account_number) < 10 or len(account_number) > 20:
        await update.message.reply_text("⚠️ شماره حساب باید بین 10 تا 20 رقم باشد. لطفاً دوباره تلاش کنید:")
        return BANK_ACCOUNT_NUMBER
    context.user_data['account_number'] = account_number
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        await update.message.reply_text("❌ شما هنوز ثبت‌نام نکرده‌اید.")
        return ConversationHandler.END
    bank_account = BankAccount(
        user_id=user.id,
        bank_name=context.user_data['bank_name'],
        account_number=context.user_data['account_number'],
        country=context.user_data['bank_country'],
        is_verified=False
    )
    session.add(bank_account)
    try:
        session.commit()
        await update.message.reply_text(
            "✅ حساب بانکی شما اضافه شد و در انتظار تأیید ادمین است."
        )
    except Exception as e:
        logger.error(f"❌ خطا در افزودن حساب بانکی: {e}")
        await update.message.reply_text("⚠️ خطا در افزودن حساب بانکی. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    return ConversationHandler.END

# نمایش تاریخچه تراکنش‌ها
async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        await update.message.reply_text("❌ شما هنوز ثبت‌نام نکرده‌اید.")
        return
    transactions = session.query(Transaction).filter_by(user_id=user.id).all()
    if transactions:
        text = "📜 **تاریخچه تراکنش‌های شما:**\n"
        for t in transactions:
            text += f"- **{t.transaction_type.capitalize()} لیر:** {t.amount} لیر، مبلغ: {t.total_price:.2f} تومان، وضعیت: {t.status.capitalize()}\n"
    else:
        text = "❌ شما هیچ تراکنشی ندارید."
    keyboard = [
        ["↩️ بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

# پنل مدیریت
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ شما دسترسی لازم برای انجام این عمل را ندارید.")
        return ConversationHandler.END
    keyboard = [
       
        ["👥 مدیریت کاربران"],
        ["📈 تنظیم نرخ‌ها"],
        ["🔄 مدیریت خرید و فروش"],
        ["📋 تنظیم اطلاعات بانکی ادمین"],
        ["↩️ بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("⚙️ **پنل مدیریت:**", reply_markup=reply_markup)

# تنظیم نرخ خرید
async def set_buy_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 لطفاً نرخ خرید جدید را وارد کنید (تومان به لیر):",
        reply_markup=ReplyKeyboardRemove()
    )
    return SET_BUY_RATE

# ذخیره نرخ خرید
async def save_buy_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_rate = float(update.message.text.strip())
        if new_rate <= 0:
            raise ValueError("نرخ باید بزرگ‌تر از صفر باشد.")
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(buy_rate=new_rate)
            session.add(settings)
        else:
            settings.buy_rate = new_rate
        session.commit()
        await update.message.reply_text(f"📈 نرخ خرید جدید تنظیم شد: {new_rate} تومان به ازای هر لیر.")
    except ValueError as ve:
        await update.message.reply_text(f"⚠️ خطا: {ve}. لطفاً یک عدد معتبر و بزرگ‌تر از صفر وارد کنید:")
        return SET_BUY_RATE
    except Exception as e:
        logger.error(f"❌ خطا در تنظیم نرخ خرید: {e}")
        await update.message.reply_text("⚠️ خطا در تنظیم نرخ خرید. لطفاً دوباره تلاش کنید:")
        return SET_BUY_RATE
    await admin_panel(update, context)
    return ConversationHandler.END

# تنظیم نرخ فروش
async def set_sell_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📉 لطفاً نرخ فروش جدید را وارد کنید (لیر به تومان):",
        reply_markup=ReplyKeyboardRemove()
    )
    return SET_SELL_RATE

# ذخیره نرخ فروش
async def save_sell_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_rate = float(update.message.text.strip())
        if new_rate <= 0:
            raise ValueError("نرخ باید بزرگ‌تر از صفر باشد.")
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(sell_rate=new_rate)
            session.add(settings)
        else:
            settings.sell_rate = new_rate
        session.commit()
        await update.message.reply_text(f"📉 نرخ فروش جدید تنظیم شد: {new_rate} تومان به ازای هر لیر.")
    except ValueError as ve:
        await update.message.reply_text(f"⚠️ خطا: {ve}. لطفاً یک عدد معتبر و بزرگ‌تر از صفر وارد کنید:")
        return SET_SELL_RATE
    except Exception as e:
        logger.error(f"❌ خطا در تنظیم نرخ فروش: {e}")
        await update.message.reply_text("⚠️ خطا در تنظیم نرخ فروش. لطفاً دوباره تلاش کنید:")
        return SET_SELL_RATE
    await admin_panel(update, context)
    return ConversationHandler.END

# تنظیم اطلاعات بانکی ادمین
async def set_admin_bank_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ شما دسترسی لازم برای انجام این عمل را ندارید.")
        return ConversationHandler.END
    text = update.message.text.strip()
    settings = session.query(Settings).first()
    if not settings:
        settings = Settings()
        session.add(settings)
    if "ایران" in text:
        settings.admin_iran_bank_account = text
        await update.message.reply_text("🔸 اطلاعات حساب بانکی ایران ادمین ذخیره شد.")
    elif "ترکیه" in text:
        settings.admin_turkey_bank_account = text
        await update.message.reply_text("🔸 اطلاعات حساب بانکی ترکیه ادمین ذخیره شد.")
    else:
        await update.message.reply_text("⚠️ لطفاً اطلاعات بانکی را به درستی وارد کنید.")
        return SET_ADMIN_BANK_INFO
    session.commit()
    await admin_panel(update, context)
    return ConversationHandler.END

# غیرفعال یا فعال کردن خرید
async def toggle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ شما دسترسی لازم برای انجام این عمل را ندارید.")
        return ConversationHandler.END
    settings = session.query(Settings).first()
    if not settings:
        settings = Settings()
        session.add(settings)
    settings.buy_enabled = not settings.buy_enabled
    session.commit()
    status = "✅ فعال" if settings.buy_enabled else "❌ غیرفعال"
    await update.message.reply_text(f"📈 قابلیت خرید لیر به حالت `{status}` تغییر یافت.", parse_mode='Markdown')
    await admin_panel(update, context)
    return ConversationHandler.END

# غیرفعال یا فعال کردن فروش
async def toggle_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ شما دسترسی لازم برای انجام این عمل را ندارید.")
        return ConversationHandler.END
    settings = session.query(Settings).first()
    if not settings:
        settings = Settings()
        session.add(settings)
    settings.sell_enabled = not settings.sell_enabled
    session.commit()
    status = "✅ فعال" if settings.sell_enabled else "❌ غیرفعال"
    await update.message.reply_text(f"📉 قابلیت فروش لیر به حالت `{status}` تغییر یافت.", parse_mode='Markdown')
    await admin_panel(update, context)
    return ConversationHandler.END

# تایید تراکنش توسط ادمین (تراکنش‌های کاربران)
async def approve_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('approve_user_'):
        transaction_id = int(data.split('_')[-1])
        user = session.query(User).filter_by(id=transaction_id).first()
        if user:
            user.is_verified = True
            session.commit()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text="✅ حساب شما تأیید شد! اکنون می‌توانید از امکانات ربات استفاده کنید."
            )
            await query.edit_message_text("✅ کاربر تأیید شد.")
        else:
            await query.edit_message_text("⚠️ کاربر یافت نشد.")
    elif data.startswith('reject_user_'):
        transaction_id = int(data.split('_')[-1])
        user = session.query(User).filter_by(id=transaction_id).first()
        if user:
            session.delete(user)
            session.commit()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text="❌ حساب شما توسط ادمین رد شد."
            )
            await query.edit_message_text("❌ کاربر رد شد.")
        else:
            await query.edit_message_text("⚠️ کاربر یافت نشد.")
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
    return ConversationHandler.END

# تایید یا لغو تراکنش توسط ادمین پس از ارسال فیش واریز ادمین
async def approve_transaction_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith('complete_transaction_'):
        transaction_id = int(data.split('_')[-1])
        transaction = session.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'transaction_completed':
            transaction.status = 'done'
            session.commit()
            user = session.query(User).filter_by(id=transaction.user_id).first()

            # ارسال پیام به کاربر درباره تکمیل تراکنش
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"✅ **تراکنش شما به طور کامل انجام شد!**\n\n"
                    f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
                    f"🔢 **مقدار:** {transaction.amount} لیر\n"
                    f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
                    f"🔄 **وضعیت تراکنش:** {transaction.status.capitalize()}."
                )
            )
            await query.edit_message_text("✅ تراکنش تکمیل شد.")
        else:
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا قبلاً تکمیل شده است.")
    elif data.startswith('cancel_transaction_'):
        transaction_id = int(data.split('_')[-1])
        transaction = session.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'transaction_completed':
            transaction.status = 'canceled'
            session.commit()
            user = session.query(User).filter_by(id=transaction.user_id).first()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"❌ **تراکنش شما لغو شد.**\n\n"
                    f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
                    f"🔢 **مقدار:** {transaction.amount} لیر\n"
                    f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
                    f"🔄 **وضعیت تراکنش:** {transaction.status.capitalize()}."
                )
            )
            await query.edit_message_text("❌ تراکنش لغو شد.")
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
    return ConversationHandler.END

# هندلر مدیریت خطاهای عمومی
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # ارسال پیام خطا به کاربر
    if isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ خطایی در سرور رخ داده است. لطفاً بعداً تلاش کنید."
        )
    # ارسال پیام خطا به ادمین‌ها
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"⚠️ یک خطا در ربات رخ داده است:\n{context.error}"
        )

# بخش اصلی اجرای ربات
def main():
    # ایجاد application
    application = Application.builder().token(TOKEN).build()

    # حذف وبهوک (در صورت استفاده از polling)
    application.bot.delete_webhook(drop_pending_updates=True)

    # تعریف ConversationHandler برای کاربران
    user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            FAMILY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_name)],
            COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_country)],
            PHONE: [MessageHandler(filters.CONTACT, get_phone)],
            ID_CARD: [MessageHandler(filters.PHOTO & ~filters.COMMAND, get_id_card)],
            SELECT_TRANSACTION_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_message_handler)],
            TRANSACTION_AMOUNT_TYPE: [CallbackQueryHandler(transaction_amount_type_handler, pattern='^amount_(toman|lira)$')],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            CONFIRM_TRANSACTION: [CallbackQueryHandler(confirm_transaction, pattern='^confirm_transaction$')],
            SEND_PAYMENT_PROOF: [MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_payment_proof)],
            BANK_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_country)],
            BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_name)],
            BANK_ACCOUNT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_account_number)],
            SET_BUY_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_buy_rate)],
            SET_SELL_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_sell_rate)],
            TOGGLE_BUY: [MessageHandler(filters.TEXT & ~filters.COMMAND, toggle_buy)],
            TOGGLE_SELL: [MessageHandler(filters.TEXT & ~filters.COMMAND, toggle_sell)],
            SET_ADMIN_BANK_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_admin_bank_info)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
    )

    # تعریف ConversationHandler برای ادمین‌ها
    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(approve_transaction, pattern='^(approve|reject)_user_\d+$')],
        states={
            # هیچ حالت خاصی برای ادمین‌ها در اینجا نیاز نیست
        },
        fallbacks=[],
        per_user=True,
    )

    admin_final_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_final_confirm_transaction, pattern='^(complete|cancel)_transaction_\d+$')],
        states={
            # هیچ حالت خاصی برای ادمین‌ها در اینجا نیاز نیست
        },
        fallbacks=[],
        per_user=True,
    )

    # اضافه کردن ConversationHandlerها به application
    application.add_handler(user_conv_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(admin_final_conv_handler)

    # اضافه کردن هندلر خطا به اپلیکیشن
    application.add_error_handler(error_handler)

    # اضافه کردن CallbackQueryHandler برای ارسال فیش پرداخت
    application.add_handler(CallbackQueryHandler(send_payment_proof_handler, pattern='^send_payment_proof_\d+$'))

    # اضافه کردن CallbackQueryHandler برای تایید پرداخت
    application.add_handler(CallbackQueryHandler(admin_confirm_payment, pattern='^(approve|reject)_payment_\d+$'))

    # اضافه کردن هندلر ارسال فیش واریز توسط کاربر
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_admin_payment_proof))

    # اضافه کردن هندلر تایید نهایی تراکنش توسط ادمین
    application.add_handler(CallbackQueryHandler(admin_final_confirm_transaction, pattern='^(complete|cancel)_transaction_\d+$'))

    # شروع polling
    application.run_polling()

if __name__ == '__main__':
    main()
