# bot.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler, ContextTypes
from telegram.request import HTTPXRequest
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توکن ربات
TOKEN = '7732549586:AAH3XpSaeY8m3BTzhCVZGlEJzwGz-okLmos'  # جایگزین با توکن ربات خود

# تعریف شناسه ادمین
ADMIN_IDS = ['179044957']  # جایگزین با شناسه‌های تلگرام ادمین‌ها (به صورت رشته)

def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

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
SET_BUY_RATE, SET_SELL_RATE = range(5, 7)
BANK_COUNTRY, BANK_NAME, BANK_ACCOUNT_NUMBER = range(7, 10)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if user:
        await update.message.reply_text("شما قبلاً ثبت‌نام کرده‌اید.")
        await main_menu(update, context)
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
        [InlineKeyboardButton("ایران", callback_data='Iran'),
         InlineKeyboardButton("ترکیه", callback_data='Turkey')]
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
    await update.message.reply_text("لطفاً تصویر کارت ملی یا پاسپورت خود را ارسال کنید:")
    return ID_CARD

async def get_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
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
             InlineKeyboardButton("رد", callback_data=f'reject_user_{user.id}')]
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
    if query.data == 'buy_lira':
        await buy_lira(update, context)
    elif query.data == 'sell_lira':
        await sell_lira(update, context)
    elif query.data == 'bank_accounts':
        await bank_accounts(update, context)
    elif query.data == 'transaction_history':
        await transaction_history(update, context)
    elif query.data == 'support':
        await support(update, context)
    elif query.data == 'main_menu':
        await main_menu(update, context)
    elif query.data == 'admin_panel':
        await admin_panel(update, context)
    elif query.data == 'add_account':
        return await add_account_start(update, context)
    elif query.data == 'view_accounts':
        return await view_accounts(update, context)
    elif query.data == 'manage_users':
        await manage_users(update, context)
    elif query.data.startswith('approve_user_'):
        await approve_user(update, context)
    elif query.data.startswith('reject_user_'):
        await reject_user(update, context)
    elif query.data == 'next_user':
        await next_user(update, context)
    elif query.data == 'manage_transactions':
        await manage_transactions(update, context)
    elif query.data.startswith('approve_transaction_'):
        await approve_transaction(update, context)
    elif query.data.startswith('reject_transaction_'):
        await reject_transaction(update, context)
    elif query.data == 'next_transaction':
        await next_transaction(update, context)
    elif query.data == 'set_rates':
        return await set_rates(update, context)
    else:
        await query.edit_message_text("دستور نامعتبر.")

async def buy_lira(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user or not user.is_verified:
        await query.edit_message_text("لطفاً ابتدا احراز هویت کنید.")
        return
    settings = session.query(Settings).first()
    if settings:
        current_rate = settings.buy_rate
    else:
        current_rate = 1000
    context.user_data['current_rate'] = current_rate
    await query.edit_message_text(f"نرخ فعلی خرید لیر: {current_rate} تومان\nلطفاً مقدار لیر مورد نظر خود را وارد کنید:")
    context.user_data['transaction_type'] = 'buy'

async def sell_lira(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user or not user.is_verified:
        await query.edit_message_text("لطفاً ابتدا احراز هویت کنید.")
        return
    settings = session.query(Settings).first()
    if settings:
        current_rate = settings.sell_rate
    else:
        current_rate = 950
    context.user_data['current_rate'] = current_rate
    await query.edit_message_text(f"نرخ فعلی فروش لیر: {current_rate} تومان\nلطفاً مقدار لیر مورد نظر خود را وارد کنید:")
    context.user_data['transaction_type'] = 'sell'

async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_text = update.message.text
    try:
        amount = float(amount_text)
        context.user_data['amount'] = amount
        total_price = amount * context.user_data['current_rate']
        context.user_data['total_price'] = total_price
        await update.message.reply_text(f"مبلغ کل: {total_price} تومان\nلطفاً قوانین را مطالعه و تأیید کنید.", reply_markup=confirmation_keyboard())
    except ValueError:
        await update.message.reply_text("لطفاً یک مقدار معتبر وارد کنید.")

def confirmation_keyboard():
    keyboard = [
        [InlineKeyboardButton("تأیید", callback_data='confirm_transaction')],
        [InlineKeyboardButton("لغو", callback_data='cancel_transaction')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def confirm_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    transaction_type = context.user_data.get('transaction_type')
    total_price = context.user_data.get('total_price')
    amount = context.user_data.get('amount')
    user_id = query.from_user.id
    transaction = Transaction(
        user_id=user_id,
        transaction_type=transaction_type,
        amount=amount,
        total_price=total_price,
        status='pending'
    )
    session.add(transaction)
    session.commit()
    if transaction_type == 'buy':
        account_info = "شماره حساب ایران: xxxxxxxx"
    else:
        account_info = "شماره حساب ترکیه: yyyyyyyy"
    await query.edit_message_text(f"لطفاً مبلغ {total_price} تومان را به حساب زیر واریز کنید:\n{account_info}\nسپس فیش واریزی را ارسال کنید.")
    context.user_data['waiting_for_receipt'] = True
    context.user_data['transaction_id'] = transaction.id

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_receipt'):
        photo_file = await update.message.photo[-1].get_file()
        user_id = update.message.from_user.id
        if not os.path.exists('user_data'):
            os.makedirs('user_data')
        photo_path = f"user_data/{user_id}_receipt.jpg"
        await photo_file.download(photo_path)
        await update.message.reply_text("فیش شما دریافت شد و در حال بررسی است.")
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=f"تراکنش جدید از کاربر {user_id}")
            with open(photo_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=admin_id, photo=photo)
            keyboard = [
                [InlineKeyboardButton("تأیید", callback_data=f'approve_transaction_{context.user_data["transaction_id"]}'),
                 InlineKeyboardButton("رد", callback_data=f'reject_transaction_{context.user_data["transaction_id"]}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=admin_id, text="لطفاً تراکنش را تأیید یا رد کنید:", reply_markup=reply_markup)
        transaction = session.query(Transaction).filter_by(id=context.user_data["transaction_id"]).first()
        if transaction:
            transaction.status = 'waiting_for_approval'
            session.commit()
        context.user_data['waiting_for_receipt'] = False
    else:
        await update.message.reply_text("دستور نامعتبر.")

async def bank_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("افزودن حساب بانکی", callback_data='add_account')],
        [InlineKeyboardButton("مشاهده حساب‌ها", callback_data='view_accounts')],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=reply_markup)

async def add_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("ایران", callback_data='Iran')],
        [InlineKeyboardButton("ترکیه", callback_data='Turkey')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=query.from_user.id, text="لطفاً کشوری که حساب بانکی در آن دارید را انتخاب کنید:", reply_markup=reply_markup)
    return BANK_COUNTRY

async def get_bank_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['bank_country'] = query.data
    await context.bot.send_message(chat_id=query.from_user.id, text="لطفاً نام بانک را وارد کنید:")
    return BANK_NAME

async def get_bank_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bank_name = update.message.text
    context.user_data['bank_name'] = bank_name
    await context.bot.send_message(chat_id=update.message.chat_id, text="لطفاً شماره حساب یا IBAN را وارد کنید:")
    return BANK_ACCOUNT_NUMBER

async def get_bank_account_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_number = update.message.text
    context.user_data['account_number'] = account_number
    user_id = update.message.from_user.id
    bank_account = BankAccount(
        user_id=user_id,
        country=context.user_data['bank_country'],
        bank_name=context.user_data['bank_name'],
        account_number=account_number,
        is_verified=False
    )
    session.add(bank_account)
    session.commit()
    await update.message.reply_text("حساب بانکی شما با موفقیت اضافه شد.")
    return ConversationHandler.END

async def view_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    bank_accounts = session.query(BankAccount).filter_by(user_id=user_id).all()
    if bank_accounts:
        message = "حساب‌های بانکی شما:\n"
        for idx, account in enumerate(bank_accounts, start=1):
            message += f"{idx}. کشور: {account.country}, بانک: {account.bank_name}, شماره حساب: {account.account_number}\n"
    else:
        message = "شما هیچ حساب بانکی ثبت‌شده‌ای ندارید."
    await query.edit_message_text(message)

async def transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    transactions = session.query(Transaction).filter_by(user_id=user_id).all()
    if transactions:
        message = "تاریخچه تراکنش‌های شما:\n"
        for t in transactions:
            message += f"تراکنش {t.id} - نوع: {t.transaction_type} - مقدار: {t.amount} - مبلغ: {t.total_price} - وضعیت: {t.status}\n"
    else:
        message = "شما هیچ تراکنشی ندارید."
    await query.edit_message_text(message)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("برای ارتباط با پشتیبانی، پیام خود را ارسال کنید.")
    context.user_data['waiting_for_support'] = True

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_for_support'):
        message = update.message.text
        user_id = update.message.from_user.id
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=f"پیام پشتیبانی از کاربر {user_id}:\n{message}")
        await update.message.reply_text("پیام شما به پشتیبانی ارسال شد.")
        context.user_data['waiting_for_support'] = False
    else:
        await update.message.reply_text("دستور نامعتبر.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("مدیریت کاربران", callback_data='manage_users')],
            [InlineKeyboardButton("مدیریت تراکنش‌ها", callback_data='manage_transactions')],
            [InlineKeyboardButton("تنظیم نرخ‌ها", callback_data='set_rates')],
            [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text("به پنل مدیریت خوش آمدید. لطفاً یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text("به پنل مدیریت خوش آمدید. لطفاً یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("شما دسترسی ادمین ندارید.")

async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending_users = session.query(User).filter_by(is_verified=False).all()
    if pending_users:
        user = pending_users[0]
        keyboard = [
            [InlineKeyboardButton("تأیید", callback_data=f'approve_user_{user.id}'),
             InlineKeyboardButton("رد", callback_data=f'reject_user_{user.id}')],
            [InlineKeyboardButton("برو به بعدی", callback_data='next_user')],
            [InlineKeyboardButton("بازگشت", callback_data='admin_panel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = f"کاربر:\nنام: {user.name} {user.family_name}\nکشور: {user.country}\nشماره تلفن: {user.phone}"
        await query.edit_message_text(message, reply_markup=reply_markup)
        context.user_data['user_index'] = 0
    else:
        await query.edit_message_text("هیچ کاربر در انتظار تأییدی وجود ندارد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data='admin_panel')]]))

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split('_')[-1])
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        user.is_verified = True
        session.commit()
        await query.edit_message_text(f"کاربر {user.name} {user.family_name} تأیید شد.")
        await context.bot.send_message(chat_id=user.telegram_id, text="حساب شما توسط ادمین تأیید شد.")
    else:
        await query.edit_message_text("کاربر یافت نشد.")
    await manage_users(update, context)

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split('_')[-1])
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        session.delete(user)
        session.commit()
        await query.edit_message_text(f"کاربر {user.name} {user.family_name} رد شد و حذف گردید.")
        await context.bot.send_message(chat_id=user.telegram_id, text="حساب شما توسط ادمین رد شد.")
    else:
        await query.edit_message_text("کاربر یافت نشد.")
    await manage_users(update, context)

async def next_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['user_index'] += 1
    pending_users = session.query(User).filter_by(is_verified=False).all()
    if context.user_data['user_index'] < len(pending_users):
        user = pending_users[context.user_data['user_index']]
        keyboard = [
            [InlineKeyboardButton("تأیید", callback_data=f'approve_user_{user.id}'),
             InlineKeyboardButton("رد", callback_data=f'reject_user_{user.id}')],
            [InlineKeyboardButton("برو به بعدی", callback_data='next_user')],
            [InlineKeyboardButton("بازگشت", callback_data='admin_panel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = f"کاربر:\nنام: {user.name} {user.family_name}\nکشور: {user.country}\nشماره تلفن: {user.phone}"
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await query.edit_message_text("کاربر دیگری در انتظار تأیید نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data='admin_panel')]]))

async def manage_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending_transactions = session.query(Transaction).filter_by(status='pending').all()
    if pending_transactions:
        transaction = pending_transactions[0]
        user = session.query(User).filter_by(telegram_id=transaction.user_id).first()
        keyboard = [
            [InlineKeyboardButton("تأیید", callback_data=f'approve_transaction_{transaction.id}'),
             InlineKeyboardButton("رد", callback_data=f'reject_transaction_{transaction.id}')],
            [InlineKeyboardButton("برو به بعدی", callback_data='next_transaction')],
            [InlineKeyboardButton("بازگشت", callback_data='admin_panel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = f"تراکنش:\nکاربر: {user.name} {user.family_name}\nنوع: {transaction.transaction_type}\nمقدار: {transaction.amount}\nمبلغ: {transaction.total_price}"
        await query.edit_message_text(message, reply_markup=reply_markup)
        context.user_data['transaction_index'] = 0
    else:
        await query.edit_message_text("هیچ تراکنش در انتظار تأییدی وجود ندارد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data='admin_panel')]]))

async def approve_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    transaction_id = int(query.data.split('_')[-1])
    transaction = session.query(Transaction).filter_by(id=transaction_id).first()
    if transaction:
        transaction.status = 'approved'
        session.commit()
        await query.edit_message_text("تراکنش تأیید شد.")
        await context.bot.send_message(chat_id=transaction.user_id, text="تراکنش شما توسط ادمین تأیید شد.")
    else:
        await query.edit_message_text("تراکنش یافت نشد.")
    await manage_transactions(update, context)

async def reject_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    transaction_id = int(query.data.split('_')[-1])
    transaction = session.query(Transaction).filter_by(id=transaction_id).first()
    if transaction:
        transaction.status = 'rejected'
        session.commit()
        await query.edit_message_text("تراکنش رد شد.")
        await context.bot.send_message(chat_id=transaction.user_id, text="تراکنش شما توسط ادمین رد شد.")
    else:
        await query.edit_message_text("تراکنش یافت نشد.")
    await manage_transactions(update, context)

async def next_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['transaction_index'] += 1
    pending_transactions = session.query(Transaction).filter_by(status='pending').all()
    if context.user_data['transaction_index'] < len(pending_transactions):
        transaction = pending_transactions[context.user_data['transaction_index']]
        user = session.query(User).filter_by(telegram_id=transaction.user_id).first()
        keyboard = [
            [InlineKeyboardButton("تأیید", callback_data=f'approve_transaction_{transaction.id}'),
             InlineKeyboardButton("رد", callback_data=f'reject_transaction_{transaction.id}')],
            [InlineKeyboardButton("برو به بعدی", callback_data='next_transaction')],
            [InlineKeyboardButton("بازگشت", callback_data='admin_panel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = f"تراکنش:\nکاربر: {user.name} {user.family_name}\nنوع: {transaction.transaction_type}\nمقدار: {transaction.amount}\nمبلغ: {transaction.total_price}"
        await query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await query.edit_message_text("تراکنش دیگری در انتظار تأیید نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data='admin_panel')]]))

async def set_rates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if is_admin(query.from_user.id):
        await context.bot.send_message(chat_id=query.from_user.id, text="لطفاً نرخ خرید لیر را وارد کنید (به تومان):")
        return SET_BUY_RATE
    else:
        await query.edit_message_text("شما دسترسی ادمین ندارید.")
        return ConversationHandler.END

async def set_buy_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        buy_rate = float(update.message.text)
        context.user_data['buy_rate'] = buy_rate
        await update.message.reply_text(f"نرخ خرید لیر به {buy_rate} تومان تنظیم شد.\nلطفاً نرخ فروش لیر را وارد کنید (به تومان):")
        return SET_SELL_RATE
    except ValueError:
        await update.message.reply_text("لطفاً یک مقدار معتبر وارد کنید.")
        return SET_BUY_RATE

async def set_sell_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sell_rate = float(update.message.text)
        buy_rate = context.user_data.get('buy_rate')
        settings = session.query(Settings).first()
        if settings:
            settings.buy_rate = buy_rate
            settings.sell_rate = sell_rate
        else:
            settings = Settings(buy_rate=buy_rate, sell_rate=sell_rate)
            session.add(settings)
        session.commit()
        await update.message.reply_text(f"نرخ فروش لیر به {sell_rate} تومان تنظیم شد.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("لطفاً یک مقدار معتبر وارد کنید.")
        return SET_SELL_RATE

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    # تنظیم پروکسی (در صورت نیاز)
    proxy_url = 'socks5://127.0.0.1:1089/'  # جایگزین با آدرس پروکسی خود یا در صورت عدم نیاز، این خط را حذف کنید
    request = HTTPXRequest(proxy_url=proxy_url)

    application = Application.builder().token(TOKEN).request(request).build()

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

    set_rates_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_rates, pattern='^set_rates$')],
        states={
            SET_BUY_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_buy_rate)],
            SET_SELL_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_sell_rate)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=False,
        per_chat=True
    )

    add_account_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_account_start, pattern='^add_account$')],
        states={
            BANK_COUNTRY: [CallbackQueryHandler(get_bank_country)],
            BANK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_name)],
            BANK_ACCOUNT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bank_account_number)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True
    )

    application.add_handler(conv_handler)
    application.add_handler(set_rates_conv_handler)
    application.add_handler(add_account_conv_handler)
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount))
    application.add_handler(MessageHandler(filters.PHOTO, receive_receipt))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_message))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
