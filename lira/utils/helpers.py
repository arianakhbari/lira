# utils/helpers.py
from config import ADMIN_IDS

def is_admin(user_id):
    """
    بررسی می‌کند که آیا کاربر با آیدی داده شده ادمین است یا خیر.
    
    Args:
        user_id (int): آیدی تلگرام کاربر.
    
    Returns:
        bool: True اگر کاربر ادمین است، در غیر این صورت False.
    """
    return user_id in ADMIN_IDS

def sanitize_phone_number(phone_number):
    """
    پاک‌سازی شماره تلفن با حذف کاراکترهای غیرعددی.
    
    Args:
        phone_number (str): شماره تلفن ورودی.
    
    Returns:
        str: شماره تلفن پاک‌سازی شده.
    """
    return ''.join(filter(str.isdigit, phone_number))
