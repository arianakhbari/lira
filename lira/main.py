# main.py
import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from config import TOKEN, LOG_FILE, ADMIN_IDS
from database import engine, Base, SessionLocal
from models import User, BankAccount, Transaction, Settings
from handlers.user_handlers import (
    start,
    terms_callback,
    get_name,
    get_family_name,
    get_country,
    get_phone,
    get_id_card,
    cancel
)
from handlers.admin_handlers import (
    approve_or_reject_user,
    approve_or_reject_payment
)
from handlers.transaction_handlers import (
    initiate_transaction,
    select_transaction_type,
    select_amount_type,
    receive_amount,
    confirm_transaction_handler,
    cancel_transaction_handler,
    send_payment_proof_handler,
    receive_payment_proof
)

# تنظیمات لاگینگ
if not os.path.exists(os.path.dirname(LOG_FILE)):
    os.makedirs(os.path.dirname(LOG_FILE))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename=LOG_FILE,
    filemode='a'
)
logger = logging.getLogger(__name__)

async def return_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    هندلر برای بازگشت به منوی اصلی.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔙 به منوی اصلی بازگشتید.")
    await start(update, context)
    return ConversationHandler.END

def main():
    # ایجاد جداول در دیتابیس (در صورت عدم وجود)
    Base.metadata.create_all(bind=engine)

    # ایجاد اپلیکیشن تلگرام
    application = Application.builder().token(TOKEN).build()

    # ایجاد نشست دیتابیس و اضافه کردن آن به bot_data
    db_session = SessionLocal()
    application.bot_data['db'] = db_session

    # اضافه کردن ConversationHandler برای کاربران
    user_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_family_name)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_country)],
            3: [MessageHandler(filters.CONTACT, get_phone)],
            4: [MessageHandler(filters.PHOTO & ~filters.COMMAND, get_id_card)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True
    )
    application.add_handler(user_conv_handler)

    # اضافه کردن هندلرهای ادمین‌ها
    application.add_handler(CallbackQueryHandler(approve_or_reject_user, pattern='^(approve|reject)_user_\d+$'))
    application.add_handler(CallbackQueryHandler(approve_or_reject_payment, pattern='^(approve|reject)_payment_\d+$'))

    # اضافه کردن ConversationHandler برای تراکنش‌ها
    transaction_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('buy', initiate_transaction), CommandHandler('sell', initiate_transaction)],
        states={
            SELECT_TRANSACTION_TYPE: [CallbackQueryHandler(select_transaction_type, pattern='^(buy|sell)$')],
            TRANSACTION_AMOUNT_TYPE: [CallbackQueryHandler(select_amount_type, pattern='^(toman|lira)$')],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_amount)],
            CONFIRM_TRANSACTION: [
                CallbackQueryHandler(confirm_transaction_handler, pattern='^confirm_transaction$'),
                CallbackQueryHandler(cancel_transaction_handler, pattern='^cancel$'),
                CallbackQueryHandler(return_to_main, pattern='^return_to_main$')
            ],
            SEND_PAYMENT_PROOF: [CallbackQueryHandler(send_payment_proof_handler, pattern='^send_payment_proof_\d+$')],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True
    )
    application.add_handler(transaction_conv_handler)

    # اضافه کردن ConversationHandler برای فیش پرداخت
    payment_proof_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_payment_proof)],
        states={
            SEND_PAYMENT_PROOF: [MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_payment_proof)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_user=True,
        per_chat=True
    )
    application.add_handler(payment_proof_handler)

    # اضافه کردن هندلر برای بازگشت به منوی اصلی
    application.add_handler(CallbackQueryHandler(return_to_main, pattern='^return_to_main$'))

    # اضافه کردن هندلرهای شرایط و قوانین
    application.add_handler(CallbackQueryHandler(terms_callback, pattern='^(accept_terms|decline_terms)$'))

    # هندلر خطاها
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(msg="Exception while handling an update:", exc_info=context.error)
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ خطایی در سرور رخ داده است. لطفاً بعداً تلاش کنید."
            )
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"⚠️ یک خطا در ربات رخ داده است:\n{context.error}"
            )

    application.add_error_handler(error_handler)

    # شروع polling
    application.run_polling()

    # بستن نشست دیتابیس پس از پایان برنامه
    db_session.close()

if __name__ == '__main__':
    main()
