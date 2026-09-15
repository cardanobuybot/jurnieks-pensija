"""Калькулятор: прогноз пенсии + долг + сравнение с ETF."""

from __future__ import annotations

from datetime import date

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
    today_year = date.today().year
    monthly = monthly_contribution(today_year, user.monthly_base)
    annual = annual_contribution(today_year, user.monthly_base)

    p = project_pension(
        birth_year=user.birth_year,
        current_stage_years=user.current_stage_years or 0.0,
        tier1_capital=user.tier1_capital or 0.0,
        tier2_capital=user.tier2_capital or 0.0,
        tier3_capital=user.tier3_capital or 0.0,
        monthly_base=user.monthly_base,
        today_year=today_year,
    )

    retirement_year = today_year + p.years_until_retirement

    lines: list[str] = [f"<b>{t('calc.title', lang=lang)}</b>", ""]

    # Стаж
    missing_note = ""
    if not p.has_right:
        missing_note = t("calc.stage_missing_suffix", lang=lang, missing=p.years_missing_for_right)
    lines.append(t("calc.stage_summary", lang=lang, stage=p.total_stage_years, missing_note=missing_note))
    lines.append("")

    # Три ключевые цифры
    if not p.has_right:
        lines.append(t("calc.no_right_line", lang=lang, vsnp=p.vsnp_at_no_right))
    if p.has_right:
        lines.append(t("calc.min_pension_line", lang=lang, min_pension=p.min_pension_at_stage))
    lines.append(
        t(
            "calc.pension_line",
            lang=lang,
            pension=p.monthly_pension,
            pension_nominal=p.monthly_pension_nominal,
            retirement_year=retirement_year,
        )
    )
    lines.append("")
    lines.append(t("calc.vsaa_calc_hint", lang=lang, pension_nominal=p.monthly_pension_nominal))
    lines.append("")

    # Частный 3-й уровень — отдельной строкой если есть
    if p.tier3_at_retirement > 0:
        lines.append(t("calc.tier3_line", lang=lang, tier3=p.tier3_at_retirement))
        lines.append("")

    # Взнос сейчас + сколько внесёшь
    lines.append(t("calc.contribution_now", lang=lang, monthly=monthly, annual=annual))
    lines.append(t("calc.total_paid", lang=lang, total=p.total_paid_in))
    lines.append("")

    # Нельзя платить за прошлые годы
    lines.append(t("calc.no_past_years", lang=lang))
    lines.append("")

    # Долг, если есть дата регистрации VSAA
    if user.vsaa_registration_date:
        paid = await repo.get_paid_months(session, user)
        lv_intervals = await repo.get_lv_periods(session, user)
        r = debt_by_months(
            registration_date=user.vsaa_registration_date,
            as_of_year=today_year,
            as_of_month=date.today().month,
            paid_months=paid,
            lv_employment_intervals=lv_intervals,
            base_monthly=user.monthly_base,
        )
        if r.months > 0:
            lines.append(f"<b>{t('calc.debt_title', lang=lang)}</b>")
            by_year: dict[int, list] = {}
            for line in r.lines:
                if line.status == "open":
                    by_year.setdefault(line.year, []).append(line)
            for y, ls in sorted(by_year.items()):
                total_year = sum(l.amount for l in ls)
                lines.append(
                    t(
                        "calc.debt_row",
                        lang=lang,
                        year=y,
                        months=len(ls),
                        monthly=ls[0].amount,
                        total=round(total_year, 2),
                    )
                )
            lines.append(t("calc.debt_total", lang=lang, months=r.months, total=r.total))
            lines.append("")
            lines.append(t("letter.hint_verify_first", lang=lang))
            lines.append("")

    # ETF-сравнение (5% реальных)
    if p.years_until_retirement > 0:
        etf_cap, etf_inc = etf_alternative(monthly, p.years_until_retirement)
        lines.append(t("calc.etf_title", lang=lang))
        lines.append(
            t(
                "calc.etf_result",
                lang=lang,
                years=p.years_until_retirement,
                capital=etf_cap,
                income=round(etf_inc / 12, 2),
            )
        )
        lines.append(t("calc.etf_disclaimer", lang=lang))
        lines.append("")

    if p.is_forecast:
        lines.append(t("calc.forecast_note", lang=lang))
        lines.append("")
    lines.append(t("disclaimer.short", lang=lang))

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn.letter", lang=lang), callback_data="letter:show"),
                InlineKeyboardButton(text=t("btn.mark_paid", lang=lang), callback_data="pay:mark"),
            ]
        ]
    )
    await message.answer("\n".join(lines), reply_markup=kb)
