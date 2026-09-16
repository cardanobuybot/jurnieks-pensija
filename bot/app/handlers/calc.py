"""Калькулятор: прогноз пенсии + долг + сравнение с ETF."""

from __future__ import annotations

from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..domain.pension import (
    annual_contribution,
    etf_alternative,
    monthly_contribution,
    project_pension,
)


from aiogram import F
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

    # Разбивка 1-й / 2-й уровень
    if p.has_right and p.total_capital > 0:
        t1_pct = round(p.tier1_at_retirement / p.total_capital * 100)
        t2_pct = round(p.tier2_at_retirement / p.total_capital * 100)
        lines.append(t("calc.tier_split", lang=lang, t1_pct=t1_pct, t2_pct=t2_pct))

    # Пометка: суммы gross (до налога)
    lines.append(t("calc.gross_note", lang=lang))
    lines.append("")

    # Частный 3-й уровень — отдельной строкой если есть
    if p.tier3_at_retirement > 0:
        lines.append(t("calc.tier3_line", lang=lang, tier3=p.tier3_at_retirement))
        lines.append("")

    # Специфичный hint для ветки С (без взносов)
    if user.branch == "C":
        lines.append(t("calc.branch_c_vsaa_hint", lang=lang))
        lines.append("")

    # Взнос сейчас — форма зависит от ветки
    if user.branch == "A":
        lines.append(t("calc.contribution_now_branch_a", lang=lang))
    else:
        lines.append(t("calc.contribution_now", lang=lang, monthly=monthly, annual=annual))
        lines.append(t("calc.total_paid", lang=lang, total=p.total_paid_in))
    lines.append("")

    if p.is_forecast:
        lines.append(t("calc.forecast_note", lang=lang))
        lines.append("")
    lines.append(t("disclaimer.short", lang=lang))

    # Кнопки: письмо VSAA + «Альтернатива». Отметка оплаты — только через /payments.
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.letter", lang=lang), callback_data="letter:show"),
        InlineKeyboardButton(text=t("btn.alternative", lang=lang), callback_data="alt:show"),
    ]])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(F.data == "alt:show")
async def cb_alternative(cb, user, session) -> None:
    """Показать подробный экран «как копить самому» — ETF + облигации + стратегия."""
    lang = user.lang
    today_year = date.today().year
    monthly = monthly_contribution(today_year, user.monthly_base)

    # Прогноз ETF на монтли-взнос за оставшиеся годы (если есть профиль)
    if user.birth_year:
        p = project_pension(
            birth_year=user.birth_year,
            current_stage_years=user.current_stage_years or 0.0,
            tier1_capital=user.tier1_capital or 0.0,
            tier2_capital=user.tier2_capital or 0.0,
            tier3_capital=user.tier3_capital or 0.0,
            monthly_base=user.monthly_base,
            today_year=today_year,
        )
        etf_cap, etf_inc = etf_alternative(monthly, p.years_until_retirement)
        proj_line = t(
            "alt.projection_line",
            lang=lang,
            monthly=monthly,
            years=p.years_until_retirement,
            capital=etf_cap,
            income=round(etf_inc / 12, 2),
        )
    else:
        proj_line = ""

    # Разбить на 2 сообщения — второе с бондами и стратегией (Telegram 4096 chars/msg).
    part1 = "\n\n".join([
        f"<b>{t('alt.title', lang=lang)}</b>",
        t("alt.intro", lang=lang),
        t("alt.what_is_etf", lang=lang),
        proj_line,
        t("alt.how_seb", lang=lang),
    ]).strip()
    part2 = "\n\n".join([
        t("alt.strategy", lang=lang),
        t("alt.disclaimer", lang=lang),
        t("alt.tip_prompt", lang=lang),
    ])
    tip_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.tip_coffee", lang=lang), url="https://revolut.me/sirjevspavels"),
    ]])
    await cb.message.answer(part1)
    await cb.message.answer(part2, reply_markup=tip_kb)
    await cb.answer()
