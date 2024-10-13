# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DATABASE_URL

# ایجاد موتور دیتابیس
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})

# ایجاد کلاس پایه برای مدل‌ها
Base = declarative_base()

# ایجاد کلاس SessionLocal برای نشست‌های دیتابیس
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    """
    ایجاد و بازگرداندن یک نشست دیتابیس. اطمینان حاصل می‌کند که نشست پس از استفاده بسته می‌شود.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
