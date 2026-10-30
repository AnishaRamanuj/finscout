from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, JSON, Text, create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"
    ticker = Column(String, primary_key=True)
    yf_symbol = Column(String)
    name = Column(String)
    sector = Column(String)
    industry = Column(String)
    market_cap = Column(Float)
    current_price = Column(Float)
    pct_change_1y = Column(Float)
    pct_change_3m = Column(Float)
    pct_change_1m = Column(Float)
    pros_cons = Column(JSON)                         # {"pros": [...], "cons": [...]}
    shareholding = Column(JSON)                      # {"promoter": .., "fii": .., ...}
    exchange = Column(String, default="NSE")
    updated_at = Column(DateTime, default=datetime.utcnow)


class Financials(Base):
    __tablename__ = "financials"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    period = Column(String)
    revenue = Column(Float)
    gross_profit = Column(Float)
    operating_income = Column(Float)
    net_income = Column(Float)
    total_debt = Column(Float)
    cash = Column(Float)
    pe = Column(Float)
    pb = Column(Float)
    roce = Column(Float)
    raw = Column(JSON)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class Score(Base):
    __tablename__ = "scores"
    ticker = Column(String, primary_key=True)
    growth = Column(Float, default=50)
    profitability = Column(Float, default=50)
    momentum = Column(Float, default=50)
    insider = Column(Float, default=50)
    sentiment = Column(Float, default=50)
    valuation = Column(Float, default=50)
    quality = Column(Float, default=50)
    composite = Column(Float, default=50)
    anomaly_flags = Column(JSON, default=list)
    computed_at = Column(DateTime, default=datetime.utcnow)


class WhyNow(Base):
    __tablename__ = "why_now"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    text = Column(Text)
    model = Column(String)
    generated_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    kind = Column(String)
    message = Column(Text)
    severity = Column(String, default="info")
    created_at = Column(DateTime, default=datetime.utcnow)


class Deal(Base):
    """NSE bulk / block deal records — one row per leg per day."""
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    kind = Column(String)           # "bulk" | "block"
    deal_date = Column(DateTime)
    client_name = Column(String)
    side = Column(String)           # "BUY" | "SELL"
    quantity = Column(Float)
    price = Column(Float)
    remarks = Column(Text)
    captured_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(engine)


def reset_db():
    """Drop and recreate every table — use before a schema change."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
