"""Калькулятор: прогноз пенсии + долг + сравнение с ETF."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..domain.pension import (
    annual_contribution,
    debt_by_months,
    etf_alternative,
    min_wage,
    monthly_contribution,
    project_pension,
)
from ..i18n import t

router = Router(name="calc")


@router.message(Command("calc"))
async def cmd_calc(message: Message, user: User, session: AsyncSession) -> None:
    if user.birth_year is None:
        lang = user.lang
        await message.answer(
            f"{t('profile.title', lang=lang)}: " + t("profile.explain", lang=lang) + "\n\n/start"
        )
        return
    await send_projection(message, user, session)


async def send_projection(message: Message, user: User, session: AsyncSession) -> None:
    lang = user.lang
    today_year = 2026  # берётся из спеки; можно date.today().year
    monthly = monthly_contribution(today_year, user.monthly_base)
    annual = annual_contribution(today_year, user.monthly_base)

    p = project_pension(
        birth_year=user.birth_year,
        current_stage_years=user.current_stage_years or 0.0,
        tier1_capital=user.tier1_capital or 0.0,
        tier2_capital=user.tier2_capital or 0.0,
        monthly_base=user.monthly_base,
        today_year=today_year,
    )

    lines: list[str] = [f"<b>{t('calc.title', lang=lang)}</b>", ""]
    lines.append(t("calc.contribution_now", lang=lang, monthly=monthly, annual=annual))
    lines.append("")

    if p.has_right:
        lines.append(t("calc.stage_ok", lang=lang, stage=p.total_stage_years))
        lines.append(t("calc.pension", lang=lang, pension=p.monthly_pension))
        lines.append(t("calc.min_pension", lang=lang, min_pension=p.min_pension_at_stage))
    else:
        lines.append(t("calc.stage_missing", lang=lang, stage=p.total_stage_years, missing=p.years_missing_for_right))
        lines.append(t("calc.no_right", lang=lang))

    lines.append(t("calc.total_paid", lang=lang, total=p.total_paid_in))

    # ETF-сравнение
    if p.years_until_retirement > 0:
        etf_cap, etf_inc = etf_alternative(monthly, p.years_until_retirement)
        lines.append("")
        lines.append(t("calc.etf_title", lang=lang))
        lines.append(t("calc.etf_result", lang=lang, years=p.years_until_retirement, capital=etf_cap, income=round(etf_inc / 12, 2)))

    # Долг, если есть дата регистрации VSAA и она в прошлом
    if user.vsaa_registration_date:
        paid = await repo.get_paid_months(session, user)
        lv_intervals = await repo.get_lv_periods(session, user)
        r = debt_by_months(
            registration_date=user.vsaa_registration_date,
            as_of_year=today_year,
            as_of_month=9,  # по спеке, calc as of сентябрь 2026
            paid_months=paid,
            lv_employment_intervals=lv_intervals,
            base_monthly=user.monthly_base,
        )
        if r.months > 0:
            lines.append("")
            lines.append(f"<b>{t('calc.debt_title', lang=lang)}</b>")
            # По годам
            by_year: dict[int, list] = {}
            for line in r.lines:
                if line.status == "open":
                    by_year.setdefault(line.year, []).append(line)
            for y, ls in sorted(by_year.items()):
                total_year = sum(l.amount for l in ls)
                lines.append(
                    t("calc.debt_row", lang=lang, year=y, months=len(ls), monthly=ls[0].amount, total=round(total_year, 2))
                )
            lines.append(t("calc.debt_total", lang=lang, months=r.months, total=r.total))
            lines.append("")
            lines.append(t("letter.hint_verify_first", lang=lang))

    if p.is_forecast:
        lines.append("")
        lines.append(t("calc.forecast_note", lang=lang))
    lines.append("")
    lines.append(t("disclaimer.short", lang=lang))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.letter", lang=lang), callback_data="letter:show"),
        InlineKeyboardButton(text=t("btn.mark_paid", lang=lang), callback_data="pay:mark"),
    ]])
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb)
