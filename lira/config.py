# config.py
import os

# توکن ربات تلگرام
TOKEN = os.getenv('TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')

# آیدی‌های ادمین‌ها (لیست اعداد)
ADMIN_IDS = [179044957]  # جایگزین با آیدی‌های ادمین‌ها

# تنظیمات دیتابیس
DATABASE_URL = 'sqlite:///bot.db'

# مسیرهای ذخیره‌سازی فایل‌ها
USER_DATA_DIR = 'user_data'
PAYMENT_PROOFS_DIR = 'payment_proofs'
ADMIN_PAYMENT_PROOFS_DIR = 'admin_payment_proofs'

# مسیر فایل لاگینگ
LOG_FILE = 'logs/bot.log'
