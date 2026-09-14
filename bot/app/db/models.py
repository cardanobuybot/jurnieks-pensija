"""SQLAlchemy 2 модели.

Правила:
- Не хранить personas kods, полное имя, паспортные данные, точные адреса.
- Хранить только год рождения, стаж, капитал, флаг ветки, оплаченные месяцы,
  периоды LV-работодателя (нужны для расчёта долга).
- lang в users, birth_year (без даты), current_stage_years — минимум для расчёта.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    tg_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lang: Mapped[str] = mapped_column(String(2), default="ru")

    # Диагностика (последнее состояние)
    branch: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)  # 'A' | 'B' | 'C'
    is_fiction: Mapped[bool] = mapped_column(Boolean, default=False)

    # Профиль
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_stage_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tier1_capital: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tier2_capital: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vsaa_registration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    monthly_base: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Отметка первого платежа (для reminders.stage_check через 3 недели)
    first_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    stage_check_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Управление напоминаниями
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_dec15_reminded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="user", cascade="all, delete-orphan"
    )
    lv_periods: Mapped[list["LvEmploymentPeriod"]] = relationship(
        "LvEmploymentPeriod", back_populates="user", cascade="all, delete-orphan"
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("user_id", "year", "month", name="uq_payment_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    marked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship("User", back_populates="payments")


class LvEmploymentPeriod(Base):
    """Интервал трудоустройства у латвийского работодателя.

    Нужен для расчёта долга: месяц исключается из добровольных, если
    он ЦЕЛИКОМ покрыт таким интервалом.
    """

    __tablename__ = "lv_employment_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    user: Mapped[User] = relationship("User", back_populates="lv_periods")
