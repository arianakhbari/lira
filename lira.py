import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler, ContextTypes
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# تنظیمات لاگینگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن ربات خود را وارد کنید
TOKEN = '7732549586:AAH3XpSaeY8m3BTzhCVZGlEJzwGz-okLmos'  # مکان 1: جایگزین کردن توکن درست

# آیدی‌های ادمین‌ها
ADMIN_IDS = [179044957]  # جایگزین با آیدی‌های ادمین

# تنظیمات دیتابیس
engine = create_engine('sqlite:///bot.db', connect_args={'check_same_thread': False})
Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()

# تعریف مدل‌های دیتابیس
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    name = Column(String)
    family_name = Column(String)
    country = Column(String)
    phone = Column(String)
    is_verified = Column(Boolean, default=False)

class BankAccount(Base):
    __tablename__ = 'bank_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    account_number = Column(String)
    bank_name = Column(String)
    country = Column(String)
    is_verified = Column(Boolean, default=False)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    transaction_type = Column(String)
    amount = Column(Float)
    total_price = Column(Float)
    status = Column(String)

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    buy_rate = Column(Float, default=1000.0)
    sell_rate = Column(Float, default=950.0)

# ایجاد جداول در دیتابیس
Base.metadata.create_all(engine)

# تعریف مراحل ConversationHandler
NAME, FAMILY_NAME, COUNTRY, PHONE, ID_CARD = range(5)
SET_BUY_RATE, SET_SELL_RATE = range(10, 12)
BANK_COUNTRY, BANK_NAME, BANK_ACCOUNT_NUMBER = range(12, 15)
AMOUNT = range(15, 16)

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if user:
        if user.is_verified:
            await update.message.reply_text("شما قبلاً ثبت‌نام کرده‌اید و حساب شما تأیید شده است.")
            await main_menu(update, context)
        else:
            await update.message.reply_text("حساب شما در انتظار تأیید است. لطفاً صبور باشید.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("سلام! برای استفاده از ربات، لطفاً فرآیند احراز هویت را تکمیل کنید.\nلطفاً نام خود را وارد کنید:")
        return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("لطفاً نام خانوادگی خود را وارد کنید:")
    return FAMILY_NAME

async def get_family_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['family_name'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("ایران", callback_data='ایران'),
         InlineKeyboardButton("ترکیه", callback_data='ترکیه')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("کشور محل سکونت خود را انتخاب کنید:", reply_markup=reply_markup)
    return COUNTRY

async def get_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['country'] = query.data
    keyboard = [[
        KeyboardButton("ارسال شماره تلفن", request_contact=True)
    ]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await context.bot.send_message(chat_id=query.from_user.id, text="لطفاً شماره تلفن خود را به اشتراک بگذارید:", reply_markup=reply_markup)
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    context.user_data['phone'] = contact.phone_number
    await update.message.reply_text("لطفاً تصویر کارت ملی یا پاسپورت خود را ارسال کنید:", reply_markup=ReplyKeyboardRemove())
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
    await photo_file.download(photo_path)
    context.user_data['id_card'] = photo_path
    await update.message.reply_text("اطلاعات شما دریافت شد و در انتظار تأیید ادمین است.")
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
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=f"کاربر جدید:\nنام: {user.name} {user.family_name}\nکشور: {user.country}\nشماره تلفن: {user.phone}")
        with open(photo_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=admin_id, photo=photo)
        keyboard = [
            [InlineKeyboardButton("تأیید", callback_data=f'approve_user_{user.id}'),
             InlineKeyboardButton("رد", callback_data=f'reject_user_{user.id}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=admin_id, text="لطفاً کاربر را تأیید یا رد کنید:", reply_markup=reply_markup)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('فرآیند لغو شد.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("خرید لیر", callback_data='buy_lira')],
        [InlineKeyboardButton("فروش لیر", callback_data='sell_lira')],
        [InlineKeyboardButton("مدیریت حساب‌های بانکی", callback_data='bank_accounts')],
        [InlineKeyboardButton("تاریخچه تراکنش‌ها", callback_data='transaction_history')],
        [InlineKeyboardButton("پشتیبانی", callback_data='support')]
    ]
    if is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("پنل مدیریت", callback_data='admin_panel')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("به منوی اصلی خوش آمدید. لطفاً یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("به منوی اصلی خوش آمدید. لطفاً یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'buy_lira':
        await query.message.reply_text("لطفاً مقدار لیر که می‌خواهید بخرید را وارد کنید:")
        context.user_data['transaction_type'] = 'buy'
        return AMOUNT
    elif data == 'sell_lira':
        await query.message.reply_text("لطفاً مقدار لیر که می‌خواهید بفروشید را وارد کنید:")
        context.user_data['transaction_type'] = 'sell'
        return AMOUNT
    elif data == 'bank_accounts':
        await manage_bank_accounts(update, context)
        return ConversationHandler.END
    elif data == 'transaction_history':
        await show_transaction_history(update, context)
        return ConversationHandler.END
    elif data == 'support':
        await query.message.reply_text("برای پشتیبانی با ما تماس بگیرید: support@example.com")
    elif data == 'main_menu':
        await main_menu(update, context)
    elif data == 'admin_panel':
        if is_admin(update.effective_user.id):
            await admin_panel(update, context)
        else:
            await query.message.reply_text("شما دسترسی لازم را ندارید.")
    elif data.startswith('approve_user_'):
        user_id = int(data.split('_')[-1])
        await approve_user(user_id, context)
        await query.message.reply_text("کاربر تأیید شد.")
    elif data.startswith('reject_user_'):
        user_id = int(data.split('_')[-1])
        await reject_user(user_id, context)
        await query.message.reply_text("کاربر رد شد.")
    else:
        await query.message.reply_text("دستور ناشناخته.")
    return ConversationHandler.END

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text
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
            rate = settings.buy_rate
            total_price = amount * rate
            await update.message.reply_text(f"مبلغ کل برای خرید {amount} لیر برابر است با {total_price} تومان.")
        else:
            rate = settings.sell_rate
            total_price = amount * rate
            await update.message.reply_text(f"مبلغ کل برای فروش {amount} لیر برابر است با {total_price} تومان.")
        # در اینجا می‌توانید فرآیند پرداخت یا ادامه تراکنش را اضافه کنید.
    except ValueError:
        await update.message.reply_text("لطفاً یک مقدار معتبر وارد کنید.")
        return AMOUNT
    return ConversationHandler.END

async def manage_bank_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    accounts = session.query(BankAccount).filter_by(user_id=user.id).all()
    if accounts:
        text = "حساب‌های بانکی شما:\n"
        for account in accounts:
            text += f"- {account.bank_name} ({account.country}): {account.account_number}\n"
    else:
        text = "شما هیچ حساب بانکی ثبت‌شده‌ای ندارید."
    keyboard = [
        [InlineKeyboardButton("افزودن حساب جدید", callback_data='add_bank_account')],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    transactions = session.query(Transaction).filter_by(user_id=user.id).all()
    if transactions:
        text = "تاریخچه تراکنش‌های شما:\n"
        for t in transactions:
            text += f"- {t.transaction_type}: {t.amount} لیر، وضعیت: {t.status}\n"
    else:
        text = "شما هیچ تراکنشی ندارید."
    keyboard = [
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("مدیریت کاربران", callback_data='manage_users')],
        [InlineKeyboardButton("تنظیم نرخ‌ها", callback_data='set_rates')],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("پنل مدیریت:", reply_markup=reply_markup)

async def approve_user(user_id, context: ContextTypes.DEFAULT_TYPE):
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        user.is_verified = True
        session.commit()
        await context.bot.send_message(chat_id=user.telegram_id, text="حساب شما تأیید شد.")
    else:
        logger.error("کاربر یافت نشد.")

async def reject_user(user_id, context: ContextTypes.DEFAULT_TYPE):
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        session.delete(user)
        session.commit()
        await context.bot.send_message(chat_id=user.telegram_id, text="حساب شما رد شد.")
    else:
        logger.error("کاربر یافت نشد.")

async def set_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("تنظیم نرخ خرید", callback_data='set_buy_rate')],
        [InlineKeyboardButton("تنظیم نرخ فروش", callback_data='set_sell_rate')],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("تنظیم نرخ‌ها:", reply_markup=reply_markup)

# بخش اصلی اجرای ربات
def main():
    # ایجاد application
    application = Application.builder().token(TOKEN).build()

    # تعریف ConversationHandler‌ها
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            FAMILY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_name)],
            COUNTRY: [CallbackQueryHandler(get_country, pattern='^(ایران|ترکیه)$')],
            PHONE: [MessageHandler(filters.CONTACT, get_phone)],
            ID_CARD: [MessageHandler(filters.PHOTO, get_id_card)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
    )

    # اضافه کردن هندلرها به application
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))

    # شروع polling
    application.run_polling()

if __name__ == '__main__':
    main()
