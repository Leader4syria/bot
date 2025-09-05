from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    referral_balance = Column(Float, default=0.0)
    is_admin = Column(Boolean, default=False)
    referral_code = Column(String, unique=True, nullable=True)
    referrer_id = Column(Integer, ForeignKey('users.telegram_id'), nullable=True)
    referred_users_count = Column(Integer, default=0)
    registered_at = Column(DateTime, default=datetime.now)

    referred_users = relationship("User", backref="referrer", remote_side=[telegram_id])
    orders = relationship("Order", backref="user", lazy=True)
    payments = relationship("Payment", backref="user", lazy=True)
    withdrawals = relationship("Withdrawal", backref="user", lazy=True)

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}', balance={self.balance}, referral_balance={self.referral_balance}, is_admin={self.is_admin})>"

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey('categories.id'), nullable=True)

    parent = relationship("Category", remote_side=[id], backref="subcategories")
    services = relationship("Service", backref="category", lazy=True)

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', parent_id={self.parent_id})>"

class Service(Base):
    __tablename__ = 'services'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    base_price = Column(Float, nullable=False)
    base_quantity = Column(Integer, nullable=False, default=1000)
    min_quantity = Column(Integer, nullable=False, default=1)
    max_quantity = Column(Integer, nullable=False, default=1000000)
    is_available = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    link_instructions = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Service(id={self.id}, name='{self.name}', price={self.base_price}, category_id={self.category_id})>"

class ServiceProvider(Base):
    __tablename__ = 'service_providers'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    api_url = Column(String, nullable=False)
    api_key = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<ServiceProvider(id={self.id}, name='{self.name}')>"

class ServiceMapping(Base):
    __tablename__ = 'service_mappings'

    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey('services.id'), nullable=False)
    provider_id = Column(Integer, ForeignKey('service_providers.id'), nullable=False)
    provider_service_id = Column(String, nullable=False)
    min_quantity = Column(Integer, default=0)
    max_quantity = Column(Integer, default=1000000)
    price_multiplier = Column(Float, default=1.0)

    service = relationship("Service", backref="service_mappings")
    provider = relationship("ServiceProvider", backref="service_mappings")

    def __repr__(self):
        return f"<ServiceMapping(service_id={self.service_id}, provider_service_id='{self.provider_service_id}')>"

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'), nullable=False)
    service_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    link_or_id = Column(String, nullable=False)
    total_price = Column(Float, nullable=False)
    status = Column(String, default='Pending')
    ordered_at = Column(DateTime, default=datetime.now)
    provider_order_id = Column(String, nullable=True)
    params = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Order(id={self.id}, user_id={self.user_id}, service_id={self.service_id}, status='{self.status}')>"

class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'), nullable=False)
    amount = Column(Float, nullable=False)
    method = Column(String, nullable=False)
    transaction_id = Column(String, nullable=True)
    status = Column(String, default='Pending')
    paid_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Payment(id={self.id}, user_id={self.user_id}, amount={self.amount}, status='{self.status}')>"

class Withdrawal(Base):
    __tablename__ = 'withdrawals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method_info = Column(Text, nullable=False)
    status = Column(String, default='Pending')
    requested_at = Column(DateTime, default=datetime.now)
    processed_at = Column(DateTime, nullable=True)
    withdrawal_type = Column(String, default='referral')

    def __repr__(self):
        return f"<Withdrawal(id={self.id}, user_id={self.user_id}, amount={self.amount}, status='{self.status}')>"

class PaymentMethod(Base):
    __tablename__ = 'payment_methods'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    contact_user = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<PaymentMethod(id={self.id}, name='{self.name}', is_available={self.is_available})>"

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)
session = Session()

order_date_index = Index('ix_orders_ordered_at', Order.ordered_at)
order_user_index = Index('ix_orders_user_id', Order.user_id)
order_status_index = Index('ix_orders_status', Order.status)
user_telegram_index = Index('ix_users_telegram_id', User.telegram_id)
user_registered_index = Index('ix_users_registered_at', User.registered_at)
payment_date_index = Index('ix_payments_paid_at', Payment.paid_at)

def init_db():
    Base.metadata.create_all(engine)

    order_date_index.create(engine, checkfirst=True)
    order_user_index.create(engine, checkfirst=True)
    order_status_index.create(engine, checkfirst=True)
    user_telegram_index.create(engine, checkfirst=True)
    user_registered_index.create(engine, checkfirst=True)
    payment_date_index.create(engine, checkfirst=True)

    print("تم إنشاء جداول وفهارس قاعدة البيانات بنجاح.")
