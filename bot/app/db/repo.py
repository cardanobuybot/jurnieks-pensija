"""Репозиторий: чистые CRUD-функции над моделями.

Хендлеры не пишут SQL сами — только через repo.*.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import LvEmploymentPeriod, Payment, User


# ---------- users ----------


async def get_or_create_user(
    session: AsyncSession, tg_id: int, tg_username: str | None = None
) -> User:
    q = select(User).where(User.tg_id == tg_id)
    user = (await session.execute(q)).scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id, tg_username=tg_username)
        session.add(user)
        await session.flush()
    elif tg_username and user.tg_username != tg_username:
        user.tg_username = tg_username
    return user


async def set_lang(session: AsyncSession, user: User, lang: str) -> None:
    user.lang = "lv" if lang.startswith("lv") else "ru"


async def set_diagnosis(
    session: AsyncSession, user: User, branch: str, is_fiction: bool = False
) -> None:
    user.branch = branch
    user.is_fiction = is_fiction


async def set_profile(
    session: AsyncSession,
    user: User,
    *,
    birth_year: int | None = None,
    stage_years: float | None = None,
    tier1: float | None = None,
    tier2: float | None = None,
    vsaa_reg_date: date | None = None,
    monthly_base: float | None = None,
) -> None:
    if birth_year is not None:
        user.birth_year = birth_year
    if stage_years is not None:
        user.current_stage_years = stage_years
    if tier1 is not None:
        user.tier1_capital = tier1
    if tier2 is not None:
        user.tier2_capital = tier2
    if vsaa_reg_date is not None:
        user.vsaa_registration_date = vsaa_reg_date
    if monthly_base is not None:
        user.monthly_base = monthly_base


# ---------- payments ----------


async def mark_payment(
    session: AsyncSession, user: User, year: int, month: int, amount: float
) -> Payment:
    q = select(Payment).where(
        Payment.user_id == user.id, Payment.year == year, Payment.month == month
    )
    p = (await session.execute(q)).scalar_one_or_none()
    if p is None:
        p = Payment(user_id=user.id, year=year, month=month, amount=amount)
        session.add(p)
    else:
        p.amount = amount
    # первый платёж — фиксируем дату для 3-недельной проверки стажа
    if user.first_payment_date is None:
        user.first_payment_date = date.today()
    await session.flush()
    return p


async def get_payments(session: AsyncSession, user: User) -> list[Payment]:
    q = (
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.year, Payment.month)
    )
    return list((await session.execute(q)).scalars())


async def get_paid_months(session: AsyncSession, user: User) -> set[tuple[int, int]]:
    q = select(Payment.year, Payment.month).where(Payment.user_id == user.id)
    return {(y, m) for (y, m) in (await session.execute(q)).all()}


# ---------- lv employment periods ----------


async def add_lv_period(
    session: AsyncSession, user: User, start: date, end: date
) -> LvEmploymentPeriod:
    p = LvEmploymentPeriod(user_id=user.id, start_date=start, end_date=end)
    session.add(p)
    await session.flush()
    return p


async def get_lv_periods(
    session: AsyncSession, user: User
) -> list[tuple[date, date]]:
    q = select(LvEmploymentPeriod.start_date, LvEmploymentPeriod.end_date).where(
        LvEmploymentPeriod.user_id == user.id
    )
    return [(s, e) for (s, e) in (await session.execute(q)).all()]


async def clear_lv_periods(session: AsyncSession, user: User) -> None:
    from sqlalchemy import delete
    await session.execute(
        delete(LvEmploymentPeriod).where(LvEmploymentPeriod.user_id == user.id)
    )


# ---------- admin ----------


async def admin_stats(session: AsyncSession) -> dict:
    total = (await session.execute(select(func.count(User.id)))).scalar_one()

    async def _count_where(cond) -> int:
        return (await session.execute(select(func.count(User.id)).where(cond))).scalar_one()

    a = await _count_where(User.branch == "A")
    b = await _count_where(User.branch == "B")
    c = await _count_where(User.branch == "C")
    none = await _count_where(User.branch.is_(None))
    ru = await _count_where(User.lang == "ru")
    lv = await _count_where(User.lang == "lv")

    paid_users = (await session.execute(
        select(func.count(func.distinct(Payment.user_id)))
    )).scalar_one() or 0

    return {
        "total": total,
        "a": a, "b": b, "c": c, "none": none,
        "ru": ru, "lv": lv,
        "paid": paid_users,
    }


# ---------- reminders scan ----------


async def users_needing_stage_check(session: AsyncSession, days_since: int) -> list[User]:
    """Пользователи с first_payment_date >= days_since дней назад, ещё не оповещённые."""
    from datetime import timedelta
    cutoff = date.today() - timedelta(days=days_since)
    q = select(User).where(
        User.first_payment_date.isnot(None),
        User.first_payment_date <= cutoff,
        User.stage_check_sent_at.is_(None),
    )
    return list((await session.execute(q)).scalars())


async def users_with_reminders_enabled(session: AsyncSession) -> list[User]:
    q = select(User).where(User.reminders_enabled.is_(True))
    return list((await session.execute(q)).scalars())
