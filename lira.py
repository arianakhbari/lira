import logging
import os
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات خود را وارد کنید
TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # مکان 1: جایگزین کردن توکن درست

# آیدی‌های ادمین‌ها
ADMIN_IDS = [YOUR_ADMIN_ID]  # مکان 2: جایگزین کردن آیدی‌های ادمین

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
    country = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)

class BankAccount(Base):
    __tablename__ = 'bank_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    account_number = Column(String, nullable=False)
    bank_name = Column(String, nullable=False)
    country = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)  # 'buy' یا 'sell'
    amount = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default='pending')  # 'pending', 'completed', 'failed'

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    buy_rate = Column(Float, default=1000.0)   # نرخ خرید (تومان به لیر)
    sell_rate = Column(Float, default=950.0)   # نرخ فروش (لیر به تومان)

# ایجاد جداول در دیتابیس
Base.metadata.create_all(engine)

# تعریف مراحل ConversationHandler
(
    NAME, FAMILY_NAME, COUNTRY, PHONE, ID_CARD,
    SET_BUY_RATE, SET_SELL_RATE,
    BANK_NAME, BANK_ACCOUNT_NUMBER,
    AMOUNT
) = range(10)

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if user:
        if user.is_verified:
            await update.message.reply_text(
                "شما قبلاً ثبت‌نام کرده‌اید و حساب شما تأیید شده است.",
                reply_markup=ReplyKeyboardRemove()
            )
            await main_menu(update, context)
        else:
            await update.message.reply_text(
                "حساب شما در انتظار تأیید است. لطفاً صبور باشید.",
                reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "سلام! برای استفاده از ربات، لطفاً فرآیند احراز هویت را تکمیل کنید.\nلطفاً نام خود را وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("لطفاً نام خانوادگی خود را وارد کنید:")
    return FAMILY_NAME

async def get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['family_name'] = update.message.text.strip()
    keyboard = [
        [KeyboardButton("ایران"), KeyboardButton("ترکیه")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "کشور محل سکونت خود را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return COUNTRY

async def get_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country = update.message.text.strip()
    if country not in ["ایران", "ترکیه"]:
        await update.message.reply_text(
            "لطفاً یکی از گزینه‌های موجود را انتخاب کنید.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("ایران"), KeyboardButton("ترکیه")]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return COUNTRY
    context.user_data['country'] = country
    keyboard = [
        [KeyboardButton("ارسال شماره تلفن", request_contact=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        "لطفاً شماره تلفن خود را به اشتراک بگذارید:",
        reply_markup=reply_markup
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        await update.message.reply_text(
            "لطفاً شماره تلفن خود را ارسال کنید.",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("ارسال شماره تلفن", request_contact=True)]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
        return PHONE
    context.user_data['phone'] = contact.phone_number
    await update.message.reply_text(
        "لطفاً تصویر کارت ملی یا پاسپورت خود را ارسال کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ID_CARD

async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not update.message.photo:
        await update.message.reply_text("لطفاً یک تصویر ارسال کنید.")
        return ID_CARD
    photo_file = await update.message.photo[-1].get_file()
    if not os.path.exists('user_data'):
        os.makedirs('user_data')
    photo_path = f"user_data/{user_id}_id.jpg"
    await photo_file.download_to_drive(custom_path=photo_path)
    context.user_data['id_card'] = photo_path
    await update.message.reply_text("اطلاعات شما دریافت شد و در انتظار تأیید ادمین است.")
    
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
    session.commit()
    
    # اطلاع رسانی به ادمین‌ها
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=(
                f"کاربر جدید:\n"
                f"نام: {user.name} {user.family_name}\n"
                f"کشور: {user.country}\n"
                f"شماره تلفن: {user.phone}"
            )
        )
        with open(photo_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=admin_id, photo=photo)
        keyboard = [
            [KeyboardButton(f"تأیید کاربر {user.id}"), KeyboardButton(f"رد کاربر {user.id}")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(
            chat_id=admin_id,
            text="لطفاً کاربر را تأیید یا رد کنید:",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'فرآیند لغو شد.',
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["خرید لیر", "فروش لیر"],
        ["مدیریت حساب‌های بانکی"],
        ["تاریخچه تراکنش‌ها"],
        ["پشتیبانی"]
    ]
    if is_admin(update.effective_user.id):
        keyboard.append(["پنل مدیریت"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "به منوی اصلی خوش آمدید. لطفاً یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "خرید لیر":
        await update.message.reply_text(
            "لطفاً مقدار لیر که می‌خواهید بخرید را وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['transaction_type'] = 'buy'
        return AMOUNT
    elif text == "فروش لیر":
        await update.message.reply_text(
            "لطفاً مقدار لیر که می‌خواهید بفروشید را وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['transaction_type'] = 'sell'
        return AMOUNT
    elif text == "مدیریت حساب‌های بانکی":
        await manage_bank_accounts(update, context)
        return ConversationHandler.END
    elif text == "تاریخچه تراکنش‌ها":
        await show_transaction_history(update, context)
        return ConversationHandler.END
    elif text == "پشتیبانی":
        await update.message.reply_text("برای پشتیبانی با ما تماس بگیرید: support@example.com")
    elif text == "پنل مدیریت" and is_admin(update.effective_user.id):
        await admin_panel(update, context)
    elif text.startswith("تأیید کاربر") and is_admin(update.effective_user.id):
        try:
            user_id = int(text.split()[-1])
            await approve_user(user_id, context)
            await update.message.reply_text("کاربر تأیید شد.")
        except ValueError:
            await update.message.reply_text("فرآیند تأیید ناموفق بود.")
    elif text.startswith("رد کاربر") and is_admin(update.effective_user.id):
        try:
            user_id = int(text.split()[-1])
            await reject_user(user_id, context)
            await update.message.reply_text("کاربر رد شد.")
        except ValueError:
            await update.message.reply_text("فرآیند رد ناموفق بود.")
    else:
        await update.message.reply_text("دستور ناشناخته. لطفاً یکی از گزینه‌های منو را انتخاب کنید.")

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text.strip()
    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError
        context.user_data['amount'] = amount
        transaction_type = context.user_data['transaction_type']
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings()
            session.add(settings)
            session.commit()
        if transaction_type == 'buy':
            rate = settings.sell_rate  # نرخ فروش
            total_price = amount / rate
            await update.message.reply_text(
                f"مبلغ کل برای خرید {amount} لیر برابر است با {total_price:.2f} تومان."
            )
            # ثبت تراکنش در دیتابیس
            transaction = Transaction(
                user_id=session.query(User).filter_by(telegram_id=update.effective_user.id).first().id,
                transaction_type='buy',
                amount=amount,
                total_price=total_price,
                status='pending'
            )
            session.add(transaction)
            session.commit()
        else:
            rate = settings.buy_rate  # نرخ خرید
            total_price = amount * rate
            await update.message.reply_text(
                f"مبلغ کل برای فروش {amount} لیر برابر است با {total_price:.2f} تومان."
            )
            # ثبت تراکنش در دیتابیس
            transaction = Transaction(
                user_id=session.query(User).filter_by(telegram_id=update.effective_user.id).first().id,
                transaction_type='sell',
                amount=amount,
                total_price=total_price,
                status='pending'
            )
            session.add(transaction)
            session.commit()
        # در اینجا می‌توانید فرآیند پرداخت یا ادامه تراکنش را اضافه کنید.
    except ValueError:
        await update.message.reply_text("لطفاً یک مقدار معتبر وارد کنید.")
        return AMOUNT
    return ConversationHandler.END

async def manage_bank_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        await update.message.reply_text("شما هنوز ثبت‌نام نکرده‌اید.")
        return
    accounts = session.query(BankAccount).filter_by(user_id=user.id).all()
    if accounts:
        text = "حساب‌های بانکی شما:\n"
        for account in accounts:
            status = "تأیید شده" if account.is_verified else "در انتظار تأیید"
            text += f"- {account.bank_name} ({account.country}): {account.account_number} [{status}]\n"
    else:
        text = "شما هیچ حساب بانکی ثبت‌شده‌ای ندارید."
    keyboard = [
        ["افزودن حساب جدید"],
        ["بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def add_bank_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "لطفاً نام بانک را وارد کنید:",
        reply_markup=ReplyKeyboardRemove()
    )
    return BANK_NAME

async def get_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bank_name'] = update.message.text.strip()
    await update.message.reply_text(
        "لطفاً شماره حساب را وارد کنید:"
    )
    return BANK_ACCOUNT_NUMBER

async def get_bank_account_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_number = update.message.text.strip()
    if not account_number.isdigit():
        await update.message.reply_text("شماره حساب باید شامل اعداد باشد. لطفاً دوباره تلاش کنید:")
        return BANK_ACCOUNT_NUMBER
    context.user_data['account_number'] = account_number
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    bank_account = BankAccount(
        user_id=user.id,
        bank_name=context.user_data['bank_name'],
        account_number=context.user_data['account_number'],
        country=user.country,
        is_verified=False
    )
    session.add(bank_account)
    session.commit()
    await update.message.reply_text(
        "حساب بانکی شما اضافه شد و در انتظار تأیید ادمین است."
    )
    return ConversationHandler.END

async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        await update.message.reply_text("شما هنوز ثبت‌نام نکرده‌اید.")
        return
    transactions = session.query(Transaction).filter_by(user_id=user.id).all()
    if transactions:
        text = "تاریخچه تراکنش‌های شما:\n"
        for t in transactions:
            text += f"- {t.transaction_type.capitalize()}: {t.amount} لیر، مبلغ: {t.total_price:.2f} تومان، وضعیت: {t.status}\n"
    else:
        text = "شما هیچ تراکنشی ندارید."
    keyboard = [
        ["بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["مدیریت کاربران"],
        ["تنظیم نرخ‌ها"],
        ["بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("پنل مدیریت:", reply_markup=reply_markup)

async def set_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["تنظیم نرخ خرید"],
        ["تنظیم نرخ فروش"],
        ["بازگشت به منوی اصلی"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("تنظیم نرخ‌ها:", reply_markup=reply_markup)

async def set_buy_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "لطفاً نرخ خرید جدید را وارد کنید (تومان به لیر):",
        reply_markup=ReplyKeyboardRemove()
    )
    return SET_BUY_RATE

async def save_buy_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_rate = float(update.message.text.strip())
        if new_rate <= 0:
            raise ValueError
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(buy_rate=new_rate)
            session.add(settings)
        else:
            settings.buy_rate = new_rate
        session.commit()
        await update.message.reply_text(f"نرخ خرید جدید تنظیم شد: {new_rate} تومان به ازای هر لیر.")
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر و بزرگ‌تر از صفر وارد کنید:")
        return SET_BUY_RATE
    return ConversationHandler.END

async def set_sell_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "لطفاً نرخ فروش جدید را وارد کنید (لیر به تومان):",
        reply_markup=ReplyKeyboardRemove()
    )
    return SET_SELL_RATE

async def save_sell_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_rate = float(update.message.text.strip())
        if new_rate <= 0:
            raise ValueError
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(sell_rate=new_rate)
            session.add(settings)
        else:
            settings.sell_rate = new_rate
        session.commit()
        await update.message.reply_text(f"نرخ فروش جدید تنظیم شد: {new_rate} تومان به ازای هر لیر.")
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر و بزرگ‌تر از صفر وارد کنید:")
        return SET_SELL_RATE
    return ConversationHandler.END

async def approve_user(user_id, context: ContextTypes.DEFAULT_TYPE):
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        user.is_verified = True
        session.commit()
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text="حساب شما تأیید شد و اکنون می‌توانید از ربات استفاده کنید."
        )
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text="به منوی اصلی خوش آمدید.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        logger.error(f"کاربر با ID {user_id} یافت نشد.")

async def reject_user(user_id, context: ContextTypes.DEFAULT_TYPE):
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        session.delete(user)
        session.commit()
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text="حساب شما رد شد. اگر فکر می‌کنید اشتباهی رخ داده، دوباره تلاش کنید."
        )
    else:
        logger.error(f"کاربر با ID {user_id} یافت نشد.")

async def add_bank_account_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_bank_account(update, context)
    return BANK_NAME

async def set_rates_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_rates(update, context)
    return

# بخش اصلی اجرای ربات
def main():
    # ایجاد application
    application = Application.builder().token(TOKEN).build()

    # حذف وبهوک (در صورت استفاده از polling)
    application.bot.delete_webhook(drop_pending_updates=True)

    # تعریف ConversationHandler‌ها
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            FAMILY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_name)],
            COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_country)],
            PHONE: [MessageHandler(filters.CONTACT, get_phone)],
            ID_CARD: [MessageHandler(filters.PHOTO, get_id_card)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            SET_BUY_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_buy_rate)],
            SET_SELL_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_sell_rate)],
            BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_name)],
            BANK_ACCOUNT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_account_number)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
    )

    # اضافه کردن ConversationHandler به application
    application.add_handler(conv_handler)

    # اضافه کردن MessageHandler برای مدیریت منوها و سایر پیام‌ها
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # اضافه کردن هندلرهای مربوط به تنظیم نرخ‌ها توسط ادمین
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_rates_flow))

    # شروع polling
    application.run_polling()

if __name__ == '__main__':
    main()
