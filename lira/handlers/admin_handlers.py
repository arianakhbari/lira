# handlers/admin_handlers.py
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from models import User, Transaction
from keyboards.admin_keyboards import payment_confirmation_keyboard, transaction_completion_keyboard
from utils.helpers import is_admin
from config import ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

# تابع برای تأیید یا رد کاربران جدید
async def approve_or_reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith('approve_user_'):
        user_id = int(data.split('_')[-1])
        db = context.bot_data['db']
        user = db.query(User).filter_by(id=user_id).first()
        if user:
            user.is_verified = True
            db.commit()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text="✅ حساب شما تأیید شد! اکنون می‌توانید از امکانات ربات استفاده کنید."
            )
            await query.edit_message_text("✅ کاربر تأیید شد.")
            logger.info(f"User {user.telegram_id} approved by admin.")
        else:
            await query.edit_message_text("⚠️ کاربر یافت نشد.")
            logger.warning(f"Attempted to approve non-existent user with ID {user_id}.")
    
    elif data.startswith('reject_user_'):
        user_id = int(data.split('_')[-1])
        db = context.bot_data['db']
        user = db.query(User).filter_by(id=user_id).first()
        if user:
            db.delete(user)
            db.commit()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text="❌ حساب شما توسط ادمین رد شد."
            )
            await query.edit_message_text("❌ کاربر رد شد.")
            logger.info(f"User {user.telegram_id} rejected by admin.")
        else:
            await query.edit_message_text("⚠️ کاربر یافت نشد.")
            logger.warning(f"Attempted to reject non-existent user with ID {user_id}.")
    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
        logger.error(f"Unknown callback data received: {data}")

# تابع برای تأیید یا رد پرداخت‌ها
async def approve_or_reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith('approve_payment_'):
        transaction_id = int(data.split('_')[-1])
        db = context.bot_data['db']
        transaction = db.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'payment_received':
            transaction.status = 'confirmed'
            db.commit()
            user = db.query(User).filter_by(id=transaction.user_id).first()

            # ارسال دستورالعمل به کاربر
            settings = db.query(Settings).first()
            if transaction.transaction_type == 'buy':
                admin_bank_info = settings.admin_turkey_bank_account or "🔸 شماره ایبان ترکیه: TRXXXXXXXXXXXXXX\n🔸 نام صاحب حساب: ادمین"
                payment_instruction = (
                    f"📥 **دستورالعمل پرداخت:**\n\n"
                    f"لطفاً مبلغ **{transaction.total_price:.2f} تومان** را به شماره ایبان زیر واریز کنید:\n\n"
                    f"{admin_bank_info}\n\n"
                    f"📸 پس از واریز، لطفاً فیش پرداخت خود را ارسال کنید."
                )
            else:
                admin_bank_info = settings.admin_iran_bank_account or "🔸 شماره شبا ایران: IRXXXXXXXXXXXXXX\n🔸 شماره کارت: XXXXXXXXXXXXXXXX\n🔸 نام صاحب حساب: ادمین"
                payment_instruction = (
                    f"📥 **دستورالعمل پرداخت:**\n\n"
                    f"لطفاً مبلغ **{transaction.total_price:.2f} تومان** را به شماره شبا زیر واریز کنید:\n\n"
                    f"{admin_bank_info}\n\n"
                    f"📸 پس از واریز، لطفاً فیش پرداخت خود را ارسال کنید."
                )

            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=payment_instruction
            )

            await query.edit_message_text("✅ پرداخت تأیید شد. دستورالعمل پرداخت به کاربر ارسال شد.")
            logger.info(f"Transaction {transaction.id} approved by admin.")

        else:
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا قبلاً تأیید شده است.")
            logger.warning(f"Attempted to approve invalid or already processed transaction ID {data}.")

    elif data.startswith('reject_payment_'):
        transaction_id = int(data.split('_')[-1])
        db = context.bot_data['db']
        transaction = db.query(Transaction).filter_by(id=transaction_id).first()
        if transaction and transaction.status == 'payment_received':
            transaction.status = 'canceled'
            db.commit()
            user = db.query(User).filter_by(id=transaction.user_id).first()
            await context.bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"❌ **پرداخت شما رد شد.**\n\n"
                    f"💱 **نوع تراکنش:** {'خرید' if transaction.transaction_type == 'buy' else 'فروش'} لیر\n"
                    f"🔢 **مقدار:** {transaction.amount} لیر\n"
                    f"💰 **مبلغ کل:** {transaction.total_price:.2f} تومان\n"
                    f"🔄 **وضعیت تراکنش:** {transaction.status.capitalize()}."
                )
            )
            await query.edit_message_text("❌ پرداخت رد شد.")
            logger.info(f"Transaction {transaction.id} rejected by admin.")
        else:
            await query.edit_message_text("⚠️ تراکنش معتبر نیست یا قبلاً تأیید شده است.")
            logger.warning(f"Attempted to reject invalid or already processed transaction ID {data}.")

    else:
        await query.edit_message_text("⚠️ گزینه نامعتبری انتخاب شده است.")
        logger.error(f"Unknown callback data received: {data}")
