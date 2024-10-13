# keyboards/admin_keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def user_approval_keyboard(user_id):
    """
    تعریف کیبورد تأیید یا رد کاربران برای ادمین‌ها.
    
    Args:
        user_id (int): شناسه‌ی کاربر.
    
    Returns:
        InlineKeyboardMarkup: کیبورد تأیید یا رد کاربر.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ تأیید", callback_data=f'approve_user_{user_id}'),
            InlineKeyboardButton("❌ رد", callback_data=f'reject_user_{user_id}')
        ],
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def payment_confirmation_keyboard(transaction_id):
    """
    تعریف کیبورد تأیید یا رد پرداخت برای ادمین‌ها.
    
    Args:
        transaction_id (int): شناسه‌ی تراکنش.
    
    Returns:
        InlineKeyboardMarkup: کیبورد تأیید یا رد پرداخت.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ تایید پرداخت", callback_data=f'approve_payment_{transaction_id}'),
            InlineKeyboardButton("❌ رد پرداخت", callback_data=f'reject_payment_{transaction_id}')
        ],
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def transaction_completion_keyboard(transaction_id):
    """
    تعریف کیبورد تکمیل یا لغو تراکنش برای ادمین‌ها.
    
    Args:
        transaction_id (int): شناسه‌ی تراکنش.
    
    Returns:
        InlineKeyboardMarkup: کیبورد تکمیل یا لغو تراکنش.
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ تکمیل تراکنش", callback_data=f'complete_transaction_{transaction_id}'),
            InlineKeyboardButton("❌ لغو تراکنش", callback_data=f'cancel_transaction_{transaction_id}')
        ],
        [InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)
