# handlers/transaction_handlers.py
import os
import logging
from enum import Enum

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from models import Transaction, Settings, User
from keyboards.admin_keyboards import payment_confirmation_keyboard
from keyboards.user_keyboards import main_menu_keyboard
from utils.helpers import is_admin, sanitize_phone_number
from config import ADMIN_IDS, PAYMENT_PROOFS_DIR

logger = logging.getLogger(__name__)

# تعریف Enum برای نوع تراکنش‌ها و وضعیت تراکنش‌ها
class TransactionType(Enum):
    BUY = 'buy'
    SELL = 'sell'

class TransactionStatus(Enum):
    AWAITING_PAYMENT = 'awaiting_payment'
    PAYMENT_RECEIVED = 'payment_received'
    CONFIRMED = 'confirmed'
    CANCELED = 'canceled'

# تعریف حالات ConversationHandler برای تراکنش‌ها
SELECT_TRANSACTION_TYPE, TRANSACTION_AMOUNT_TYPE, AMOUNT, CONFIRM_TRANSACTION, SEND_PAYMENT_PROOF = range(5)

async def initiate_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    آغاز فرآیند تراکنش توسط کاربر (خرید یا فروش لیر).
    """
    user_id = update.message.from_user.id
    db = context.bot_data['db']
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if not user or not user.is_verified or not user.has_accepted_terms:
        await update.message.reply_text(
            "❌ شما هنوز ثبت‌نام نکرده‌اید، حساب شما تأیید نشده است یا شرایط و قوانین را پذیرفته‌اید."
        )
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🛒 خرید لیر", callback_data=TransactionType.BUY.value)],
        [InlineKeyboardButton("🛍️ فروش لیر", callback_data=TransactionType.SELL.value)],
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💱 لطفاً نوع تراکنش خود را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return SELECT_TRANSACTION_TYPE

async def select_transaction_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت نوع تراکنش (خرید یا فروش) از کاربر.
    """
    query = update.callback_query
    await query.answer()
    transaction_type = query.data
    
    if transaction_type not in [t.value for t in TransactionType]:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
        return ConversationHandler.END
    
    context.user_data['transaction_type'] = TransactionType(transaction_type)
    
    keyboard = [
        [InlineKeyboardButton("🔢 مبلغ به تومان", callback_data='toman')],
        [InlineKeyboardButton("💴 مبلغ به لیر", callback_data='lira')],
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🔢 لطفاً نوع محاسبه مبلغ تراکنش را انتخاب کنید:",
        reply_markup=reply_markup
    )
    return TRANSACTION_AMOUNT_TYPE

async def select_amount_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت نوع محاسبه مبلغ تراکنش (تومان به لیر یا لیر به تومان).
    """
    query = update.callback_query
    await query.answer()
    amount_type = query.data
    
    if amount_type not in ['toman', 'lira']:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
        return ConversationHandler.END
    
    context.user_data['amount_type'] = amount_type
    await query.edit_message_text(
        "💰 لطفاً مبلغ تراکنش را وارد کنید (عدد بدون کاراکتر خاص):\n"
        "↩️ برای بازگشت به منوی اصلی، /start را ارسال کنید."
    )
    return AMOUNT

async def receive_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت مبلغ تراکنش از کاربر و محاسبه مبلغ کل.
    """
    amount_text = update.message.text.strip()
    if not amount_text.replace('.', '', 1).isdigit():
        await update.message.reply_text("⚠️ لطفاً فقط از اعداد استفاده کنید. دوباره تلاش کنید:")
        return AMOUNT
    
    amount = float(amount_text)
    if amount <= 0:
        await update.message.reply_text("⚠️ مبلغ باید بزرگ‌تر از صفر باشد. دوباره تلاش کنید:")
        return AMOUNT
    
    transaction_type = context.user_data['transaction_type']
    amount_type = context.user_data['amount_type']
    
    db = context.bot_data['db']
    settings = db.query(Settings).first()
    
    if not settings:
        await update.message.reply_text("⚠️ تنظیمات ربات ناقص است. لطفاً بعداً تلاش کنید.")
        return ConversationHandler.END
    
    # محاسبه مبلغ کل بر اساس نوع محاسبه
    if transaction_type == TransactionType.BUY:
        if amount_type == 'toman':
            total_price = amount / settings.buy_rate  # تبدیل تومان به لیر
        else:  # lira
            total_price = amount * settings.buy_rate  # لیر به تومان
        if not settings.buy_enabled:
            await update.message.reply_text("⚠️ خرید لیر در حال حاضر غیرفعال است.")
            return ConversationHandler.END
    else:  # SELL
        if amount_type == 'toman':
            total_price = amount / settings.sell_rate  # تبدیل تومان به لیر
        else:  # lira
            total_price = amount * settings.sell_rate  # لیر به تومان
        if not settings.sell_enabled:
            await update.message.reply_text("⚠️ فروش لیر در حال حاضر غیرفعال است.")
            return ConversationHandler.END
    
    context.user_data['amount'] = amount
    context.user_data['total_price'] = total_price
    
    confirmation_text = (
        f"📋 **تراکنش شما:**\n\n"
        f"💱 **نوع تراکنش:** {'خرید' if transaction_type == TransactionType.BUY else 'فروش'} لیر\n"
        f"🔢 **مقدار:** {amount} {'تومان' if amount_type == 'toman' else 'لیر'}\n"
        f"💰 **مبلغ کل:** {total_price:.2f} تومان\n\n"
        f"✅ آیا مایل به تایید این تراکنش هستید؟"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ تایید", callback_data='confirm_transaction')],
        [InlineKeyboardButton("❌ لغو", callback_data='cancel')],
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        confirmation_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    return CONFIRM_TRANSACTION

async def confirm_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    تایید تراکنش توسط کاربر و ذخیره آن در دیتابیس.
    """
    query = update.callback_query
    await query.answer()
    
    if query.data != 'confirm_transaction':
        await query.edit_message_text("⛔️ تراکنش لغو شد.")
        return ConversationHandler.END
    
    transaction_type = context.user_data['transaction_type']
    amount = context.user_data['amount']
    total_price = context.user_data['total_price']
    user_id = update.effective_user.id
    
    db = context.bot_data['db']
    user = db.query(User).filter_by(telegram_id=user_id).first()
    
    if not user:
        await query.edit_message_text("⚠️ خطا در یافتن اطلاعات شما. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    
    # ایجاد تراکنش جدید
    transaction = Transaction(
        user_id=user.id,
        transaction_type=transaction_type.value,
        amount=amount,
        total_price=total_price,
        status=TransactionStatus.AWAITING_PAYMENT.value
    )
    db.add(transaction)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"❌ خطا در ثبت تراکنش: {e}")
        await query.edit_message_text("⚠️ خطا در ثبت تراکنش. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    
    # ارسال دستورالعمل پرداخت به کاربر
    if transaction_type == TransactionType.BUY:
        admin_bank_info = settings.admin_turkey_bank_account or "🔸 شماره ایبان ترکیه: TRXXXXXXXXXXXXXX\n🔸 نام صاحب حساب: ادمین"
        payment_instruction = (
            f"📥 **دستورالعمل پرداخت:**\n\n"
            f"لطفاً مبلغ **{total_price:.2f} تومان** را به شماره ایبان زیر واریز کنید:\n\n"
            f"{admin_bank_info}\n\n"
            f"📸 پس از واریز، لطفاً فیش پرداخت خود را ارسال کنید."
        )
    else:
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
            f"💱 **نوع تراکنش:** {'خرید' if transaction_type == TransactionType.BUY else 'فروش'} لیر\n"
            f"🔢 **مقدار:** {transaction.amount} لیر\n"
            f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
            f"🔄 **وضعیت:** {transaction.status.capitalize()}.\n\n"
            f"📥 **دستورالعمل پرداخت:**\n{payment_instruction}"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ تایید پرداخت", callback_data=f'approve_payment_{transaction.id}'),
                InlineKeyboardButton("❌ رد پرداخت", callback_data=f'reject_payment_{transaction.id}'),
                InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=transaction_details,
            reply_markup=reply_markup
        )
    return ConversationHandler.END

async def cancel_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    لغو تراکنش توسط کاربر.
    """
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("⛔️ تراکنش لغو شد.")
    return ConversationHandler.END

async def send_payment_proof_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    هندلر برای دریافت فیش پرداخت از کاربر.
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data.startswith('send_payment_proof_'):
        transaction_id = int(data.split('_')[-1])
        db = context.bot_data['db']
        transaction = db.query(Transaction).filter_by(id=transaction_id).first()
        if not transaction or transaction.status != TransactionStatus.AWAITING_PAYMENT.value:
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا در وضعیت مناسبی قرار ندارد.")
            return ConversationHandler.END
        
        # درخواست فیش پرداخت از کاربر
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="📸 لطفاً فیش پرداخت خود را ارسال کنید.\n↩️ برای بازگشت به منوی اصلی، /start را ارسال کنید."
        )
        # ذخیره شناسه تراکنش در context برای مرحله بعد
        context.user_data['current_transaction_id'] = transaction_id
        return SEND_PAYMENT_PROOF
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
        return ConversationHandler.END

async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    دریافت فیش پرداخت از کاربر و ارسال آن به ادمین‌ها برای بررسی.
    """
    user_id = update.message.from_user.id
    db = context.bot_data['db']
    user = db.query(User).filter_by(telegram_id=user_id).first()
    transaction_id = context.user_data.get('current_transaction_id')
    transaction = db.query(Transaction).filter_by(id=transaction_id, user_id=user.id).first()
    
    if not transaction or transaction.status != TransactionStatus.AWAITING_PAYMENT.value:
        await update.message.reply_text("⚠️ تراکنش یافت نشد یا در وضعیت مناسبی قرار ندارد.")
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
    payment_proof_path = os.path.join(PAYMENT_PROOFS_DIR, f"{transaction_id}_payment.jpg")
    if not os.path.exists(PAYMENT_PROOFS_DIR):
        os.makedirs(PAYMENT_PROOFS_DIR)
    await photo_file.download_to_drive(custom_path=payment_proof_path)
    transaction.payment_proof = payment_proof_path
    transaction.status = TransactionStatus.PAYMENT_RECEIVED.value
    db.commit()
    
    await update.message.reply_text("✅ فیش پرداخت شما دریافت شد و در انتظار بررسی ادمین‌ها است.")
    
    # اطلاع رسانی به ادمین‌ها
    for admin_id in ADMIN_IDS:
        transaction_details = (
            f"🔔 **فیش پرداخت برای تراکنش {transaction.id} ارسال شده است.**\n\n"
            f"👤 **کاربر:** {user.name} {user.family_name} (ID: {user.id})\n"
            f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == TransactionType.BUY.value else 'فروش'} لیر\n"
            f"🔢 **مقدار:** {transaction.amount} لیر\n"
            f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
            f"🔄 **وضعیت:** {transaction.status.capitalize()}.\n\n"
            f"📸 **فیش پرداخت کاربر:**"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ تایید پرداخت", callback_data=f'approve_payment_{transaction.id}'),
                InlineKeyboardButton("❌ رد پرداخت", callback_data=f'reject_payment_{transaction.id}'),
                InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='return_to_main')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=transaction_details,
            reply_markup=reply_markup
        )
        with open(payment_proof_path, 'rb') as photo_file_obj:
            await context.bot.send_photo(chat_id=admin_id, photo=photo_file_obj)
    return ConversationHandler.END
