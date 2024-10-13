# keyboards/user_keyboards.py
from telegram import KeyboardButton, ReplyKeyboardMarkup

def main_menu_keyboard(is_admin=False):
    """
    تعریف کیبورد منوی اصلی برای کاربران.
    
    Args:
        is_admin (bool): اگر True باشد، گزینه پنل مدیریت اضافه می‌شود.
    
    Returns:
        ReplyKeyboardMarkup: کیبورد منوی اصلی.
    """
    keyboard = [
        ["💱 لیر"],
        ["🏦 مدیریت حساب‌های بانکی"],
        ["📜 تاریخچه تراکنش‌ها"],
        ["📞 پشتیبانی"]
    ]
    if is_admin:
        keyboard.append(["⚙️ پنل مدیریت"])
    # اضافه کردن دکمه بازگشت به منوی اصلی
    keyboard.append(["↩️ بازگشت به منوی اصلی"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def country_selection_keyboard():
    """
    تعریف کیبورد انتخاب کشور برای کاربران.
    
    Returns:
        ReplyKeyboardMarkup: کیبورد انتخاب کشور.
    """
    keyboard = [
        [KeyboardButton("🇮🇷 ایران"), KeyboardButton("🇹🇷 ترکیه")],
        ["↩️ بازگشت به منوی اصلی"]  # اضافه کردن دکمه بازگشت
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

def contact_keyboard():
    """
    تعریف کیبورد ارسال شماره تلفن برای کاربران.
    
    Returns:
        ReplyKeyboardMarkup: کیبورد ارسال شماره تلفن.
    """
    keyboard = [
        [KeyboardButton("📞 ارسال شماره تلفن", request_contact=True)],
        ["↩️ بازگشت به منوی اصلی"]  # اضافه کردن دکمه بازگشت
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
