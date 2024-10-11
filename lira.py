import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# تنظیمات لاگینگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = '7732549586:AAH3XpSaeY8m3BTzhCVZGlEJzwGz-okLmos'  # مکان 1: جایگزین کردن توکن درست

# تعریف آیدی‌های ادمین
ADMIN_IDS = [179044957]  # آیدی تلگرام ادمین را در این لیست قرار دهید

# تابع برای بررسی ادمین بودن کاربر
def is_admin(user_id):
    return user_id in ADMIN_IDS

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

async def start(update: Update, context):
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if user:
        if not user.is_verified:
            await update.message.reply_text("حساب کاربری شما هنوز تأیید نشده است. لطفاً منتظر تأیید ادمین باشید.")
            return ConversationHandler.END
        await update.message.reply_text("شما قبلاً ثبت‌نام کرده‌اید.")
        await main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("سلام! برای استفاده از ربات، لطفاً فرآیند احراز هویت را تکمیل کنید.\nلطفاً نام خود را وارد کنید:")
        return NAME

async def get_name(update: Update, context):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("لطفاً نام خانوادگی خود را وارد کنید:")
    return FAMILY_NAME

async def get_family_name(update: Update, context):
    context.user_data['family_name'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("ایران", callback_data='Iran'),
         InlineKeyboardButton("ترکیه", callback_data='Turkey')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("کشور محل سکونت خود را انتخاب کنید:", reply_markup=reply_markup)
    return COUNTRY

async def get_country(update: Update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['country'] = query.data
    keyboard = [[
        KeyboardButton("ارسال شماره تلفن", request_contact=True)
    ]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await context.bot.send_message(chat_id=query.from_user.id, text="لطفاً شماره تلفن خود را به اشتراک بگذارید:", reply_markup=reply_markup)
    return PHONE

async def get_phone(update: Update, context):
    contact = update.message.contact
    context.user_data['phone'] = contact.phone_number
    await update.message.reply_text("لطفاً تصویر کارت ملی یا پاسپورت خود را ارسال کنید:")
    return ID_CARD

async def get_id_card(update: Update, context):
    user_id = update.message.from_user.id
    photo_file = await update.message.photo[-1].get_file()
    if not os.path.exists('user_data'):
        os.makedirs('user_data')
    photo_path = f"user_data/{user_id}_id.jpg"
    await photo_file.download(photo_path)
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
    # ارسال اطلاعات به ادمین‌ها برای تأیید
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

async def cancel(update: Update, context):
    await update.message.reply_text('فرآیند لغو شد.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def main_menu(update: Update, context):
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

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.data == 'buy_lira':
        # await buy_lira(update, context)
        pass  # تابع را بر اساس نیاز خود تکمیل کنید
    elif query.data == 'sell_lira':
        # await sell_lira(update, context)
        pass
    elif query.data == 'bank_accounts':
        # await bank_accounts(update, context)
        pass
    elif query.data == 'transaction_history':
        # await transaction_history(update, context)
        pass
    elif query.data == 'support':
        # await support(update, context)
        pass
    elif query.data == 'main_menu':
        await main_menu(update, context)
    elif query.data == 'admin_panel':
        # await admin_panel(update, context)
        pass
    elif query.data.startswith('approve_user_') or query.data.startswith('reject_user_'):
        await approve_or_reject_user(update, context)
    # ادامه برای مدیریت بقیه حالت‌ها...

async def approve_or_reject_user(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    action = data[0]
    user_id = int(data[2])
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        if action == 'approve':
            user.is_verified = True
            session.commit()
            await context.bot.send_message(chat_id=user.telegram_id, text="حساب کاربری شما تأیید شد.")
            await query.edit_message_text("کاربر تأیید شد.")
        elif action == 'reject':
            session.delete(user)
            session.commit()
            await context.bot.send_message(chat_id=user.telegram_id, text="حساب کاربری شما رد شد.")
            await query.edit_message_text("کاربر رد شد.")
    else:
        await query.edit_message_text("کاربر مورد نظر یافت نشد.")

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
            COUNTRY: [CallbackQueryHandler(get_country)],
            PHONE: [MessageHandler(filters.CONTACT, get_phone)],
            ID_CARD: [MessageHandler(filters.PHOTO, get_id_card)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # اضافه کردن هندلرها به application
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(approve_or_reject_user, pattern='^(approve|reject)_user_\\d+$'))
    # بقیه هندلرها را نیز اضافه کنید

    # شروع polling
    application.run_polling()

if __name__ == '__main__':
    main()
