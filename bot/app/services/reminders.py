"""Напоминания через APScheduler. Таймзона Europe/Riga.

- day-5 каждого месяца: если за прошлый месяц нет оплаты → напомнить
- 15 декабря: смена минзарплаты
- через 21 день после first_payment_date: спросить «стаж на latvija.lv вырос?»
- 1 декабря админу: если нет MIN_WAGE_BY_YEAR[next_year]
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import Payment, User
from ..db.session import get_sessionmaker
from ..domain.constants import (
    MIN_WAGE_BY_YEAR,
    STAGE_CHECK_AFTER_DAYS,
    VSAA_CONTRIBUTIONS_PHONE,
)
from ..i18n import t

log = logging.getLogger(__name__)
RIGA_TZ = pytz.timezone("Europe/Riga")


def _prev_month(today: date) -> tuple[int, int]:
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


async def _has_payment_for_prev_month(session: AsyncSession, user: User) -> bool:
    y, m = _prev_month(date.today())
    q = select(Payment.id).where(
        Payment.user_id == user.id, Payment.year == y, Payment.month == m
    )
    return (await session.execute(q)).scalar_one_or_none() is not None


async def job_day5_reminder(bot: Bot) -> None:
    """5-го числа. Пинг тем, кто ещё не отметил прошлый месяц."""
    async with get_sessionmaker()() as session:
        users = await repo.users_with_reminders_enabled(session)
        py, pm = _prev_month(date.today())
        for u in users:
            if u.branch == "A":
                continue  # ветка A не платит
            if await _has_payment_for_prev_month(session, u):
                continue
            try:
                await bot.send_message(
                    u.tg_id,
                    t("reminders.day5", lang=u.lang, year=py, month=f"{pm:02d}"),
                )
            except Exception as e:
                log.warning("day5 send failed for %s: %s", u.tg_id, e)


_MONTHS_RU = ["январь","февраль","март","апрель","май","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"]
_MONTHS_LV = ["janvāri","februāri","martu","aprīli","maiju","jūniju","jūliju","augustu","septembri","oktobri","novembri","decembri"]


async def job_day25_reminder(bot: Bot) -> None:
    """25-го числа. Проактивное напоминание: заплати взнос за текущий месяц."""
    from ..domain.pension import monthly_contribution
    today = date.today()
    async with get_sessionmaker()() as session:
        users = await repo.users_with_reminders_enabled(session)
        for u in users:
            if u.branch == "A":
                continue
            if not u.vsaa_registration_date:
                continue  # ещё не зарегистрирован — нет смысла
            amount = monthly_contribution(today.year, u.monthly_base)
            m_names = _MONTHS_LV if u.lang == "lv" else _MONTHS_RU
            m_name = m_names[today.month - 1]
            try:
                await bot.send_message(
                    u.tg_id,
                    t(
                        "reminders.day25", lang=u.lang,
                        month_name=m_name, year=today.year, amount=amount,
                    ),
                )
            except Exception as e:
                log.warning("day25 send failed for %s: %s", u.tg_id, e)


async def job_dec15_reminder(bot: Bot) -> None:
    """15 декабря. Смена минзарплаты."""
    async with get_sessionmaker()() as session:
        users = await repo.users_with_reminders_enabled(session)
        for u in users:
            if u.branch == "A":
                continue
            try:
                await bot.send_message(u.tg_id, t("reminders.dec15", lang=u.lang))
                u.last_dec15_reminded_at = datetime.utcnow()
            except Exception as e:
                log.warning("dec15 send failed for %s: %s", u.tg_id, e)


async def job_stage_check(bot: Bot) -> None:
    """Через 21 день после first_payment_date спросить, вырос ли стаж."""
    async with get_sessionmaker()() as session:
        users = await repo.users_needing_stage_check(session, days_since=STAGE_CHECK_AFTER_DAYS)
        for u in users:
            fp = u.first_payment_date
            if fp is None:
                continue
            # Показываем «стаж должен был вырасти за месяц оплаты» — берём месяц оплаты
            y = fp.year
            m = fp.month
            try:
                await bot.send_message(
                    u.tg_id,
                    t("reminders.stage_check", lang=u.lang, year=y, month=f"{m:02d}", phone=VSAA_CONTRIBUTIONS_PHONE),
                )
                u.stage_check_sent_at = datetime.utcnow()
            except Exception as e:
                log.warning("stage_check send failed for %s: %s", u.tg_id, e)


async def job_admin_min_wage_alert(bot: Bot) -> None:
    """1 декабря. Проверить что MIN_WAGE_BY_YEAR[next_year] задан."""
    admin_chat = os.getenv("ADMIN_CHAT_ID")
    if not admin_chat:
        return
    next_year = date.today().year + 1
    if next_year in MIN_WAGE_BY_YEAR:
        return
    try:
        await bot.send_message(
            int(admin_chat),
            t("admin.alert.no_min_wage", lang="ru", year=next_year),
        )
    except Exception as e:
        log.warning("admin alert failed: %s", e)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=RIGA_TZ)

    # 5-е число каждого месяца в 10:00 — постфактум пинг за прошлый месяц
    scheduler.add_job(job_day5_reminder, CronTrigger(day=5, hour=10, minute=0), args=[bot], id="day5")
    # 25-е число в 10:00 — проактивно: не забудь заплатить текущий месяц
    scheduler.add_job(job_day25_reminder, CronTrigger(day=25, hour=10, minute=0), args=[bot], id="day25")
    # 15 декабря в 10:00
    scheduler.add_job(job_dec15_reminder, CronTrigger(month=12, day=15, hour=10, minute=0), args=[bot], id="dec15")
    # Ежедневно 11:00 — проверка тех, у кого прошло 21 день
    scheduler.add_job(job_stage_check, CronTrigger(hour=11, minute=0), args=[bot], id="stage_check")
    # 1 декабря 09:00 — админу
    scheduler.add_job(job_admin_min_wage_alert, CronTrigger(month=12, day=1, hour=9, minute=0), args=[bot], id="admin_min_wage")

    return scheduler
