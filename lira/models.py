# models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    family_name = Column(String, nullable=False)
    country = Column(String, nullable=False)  # 'Iran' یا 'Turkey'
    phone = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    
    # ارتباط با حساب‌های بانکی
    bank_accounts = relationship("BankAccount", back_populates="user")
    
    # ارتباط با تراکنش‌ها
    transactions = relationship("Transaction", back_populates="user")


class BankAccount(Base):
    __tablename__ = 'bank_accounts'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    bank_name = Column(String, nullable=False)
    account_number = Column(String, nullable=False)
    country = Column(String, nullable=False)  # 'Iran' یا 'Turkey'
    is_verified = Column(Boolean, default=False)
    
    # ارتباط با کاربر
    user = relationship("User", back_populates="bank_accounts")


class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    transaction_type = Column(String, nullable=False)  # 'buy' یا 'sell'
    amount = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default='pending')  # وضعیت تراکنش‌ها
    payment_proof = Column(String, nullable=True)
    admin_payment_proof = Column(String, nullable=True)
    
    # ارتباط با کاربر
    user = relationship("User", back_populates="transactions")


class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True, index=True)
    buy_rate = Column(Float, default=1000.0)   # نرخ خرید (تومان به لیر)
    sell_rate = Column(Float, default=950.0)   # نرخ فروش (لیر به تومان)
    buy_enabled = Column(Boolean, default=True)  # فعال یا غیرفعال بودن خرید
    sell_enabled = Column(Boolean, default=True)  # فعال یا غیرفعال بودن فروش
    admin_iran_bank_account = Column(String, nullable=True)  # اطلاعات حساب بانکی ایران ادمین
    admin_turkey_bank_account = Column(String, nullable=True)  # اطلاعات حساب بانکی ترکیه ادمین
