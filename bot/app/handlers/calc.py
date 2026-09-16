"""Калькулятор: прогноз пенсии + долг + сравнение с ETF."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
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

# Инфографика «стратегия для моряка» + file_id-кеш.
_STRATEGY_IMG = Path(__file__).resolve().parent.parent / "assets" / "strategy.png"
_STRATEGY_FILE_ID: dict[str, str] = {}
_SWEDBANK_IMG = Path(__file__).resolve().parent.parent / "assets" / "swedbank_robur.jpg"
_SWEDBANK_FILE_ID: dict[str, str] = {}


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
    today = date.today()
    today_year = today.year
    monthly = monthly_contribution(today_year, user.monthly_base)
    annual = annual_contribution(today_year, user.monthly_base)

    # СЦЕНАРИЙ A — без взносов: monthly_base=0, стаж не растёт
    p_no = project_pension(
        birth_year=user.birth_year,
        current_stage_years=user.current_stage_years or 0.0,
        tier1_capital=user.tier1_capital or 0.0,
        tier2_capital=user.tier2_capital or 0.0,
        monthly_base=0,
        today_year=today_year,
    )
    # СЦЕНАРИЙ B — с добровольными взносами каждый месяц до 65
    p_with = project_pension(
        birth_year=user.birth_year,
        current_stage_years=user.current_stage_years or 0.0,
        tier1_capital=user.tier1_capital or 0.0,
        tier2_capital=user.tier2_capital or 0.0,
        monthly_base=user.monthly_base,
        today_year=today_year,
    )
    retirement_year = today_year + p_with.years_until_retirement

    # «Следующий месяц» на языке юзера — простые названия месяцев
    next_month_idx = today.month % 12 + 1
    next_month_year = today_year + (1 if today.month == 12 else 0)
    months_ru = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
    months_lv = ["janvāra","februāra","marta","aprīļa","maija","jūnija","jūlija","augusta","septembra","oktobra","novembra","decembra"]
    m_names = months_ru if lang == "ru" else months_lv
    next_month_str = f"{m_names[next_month_idx-1]} {next_month_year}"

    lines: list[str] = [f"<b>{t('calc.title', lang=lang)}</b>", ""]

    # === СЦЕНАРИЙ A: без взносов ===
    lines.append(t("calc.scenario_a_title", lang=lang))
    if not p_no.has_right:
        lines.append(t(
            "calc.scenario_a_stage_no_right", lang=lang,
            stage=p_no.total_stage_years, vsnp=p_no.vsnp_at_no_right,
        ))
    else:
        lines.append(t(
            "calc.scenario_a_stage_has_right", lang=lang,
            stage=p_no.total_stage_years,
            min_pension=p_no.min_pension_at_stage,
            pension=p_no.monthly_pension,
        ))
    lines.append("")

    # === СЦЕНАРИЙ B: с добровольными до 65 ===
    lines.append(t("calc.scenario_b_title", lang=lang, next_month=next_month_str))
    lines.append(t(
        "calc.scenario_b_body", lang=lang,
        stage=p_with.total_stage_years,
        min_pension=p_with.min_pension_at_stage,
        pension=p_with.monthly_pension,
        pension_nominal=p_with.monthly_pension_nominal,
        retirement_year=retirement_year,
    ))
    lines.append("")

    # VSAA калькулятор hint
    lines.append(t("calc.vsaa_calc_hint", lang=lang, pension_nominal=p_with.monthly_pension_nominal))

    # Разбивка 1-й / 2-й уровень
    if p_with.has_right and p_with.total_capital > 0:
        t1_pct = round(p_with.tier1_at_retirement / p_with.total_capital * 100)
        t2_pct = round(p_with.tier2_at_retirement / p_with.total_capital * 100)
        lines.append(t("calc.tier_split", lang=lang, t1_pct=t1_pct, t2_pct=t2_pct))

    lines.append(t("calc.gross_note", lang=lang))
    lines.append("")

    # Взнос сейчас — зависит от ветки
    if user.branch == "A":
        lines.append(t("calc.contribution_now_branch_a", lang=lang))
    else:
        lines.append(t("calc.contribution_now", lang=lang, monthly=monthly, annual=annual))
        lines.append(t("calc.total_paid", lang=lang, total=p_with.total_paid_in))
    lines.append("")

    if p_with.is_forecast:
        lines.append(t("calc.forecast_note", lang=lang))
        lines.append("")
    lines.append(t("disclaimer.short", lang=lang))
    p = p_with  # для кнопок ниже

    # На прогнозе — только «Альтернатива». Письмо VSAA перенесено в конец Альтернативы.
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.alternative", lang=lang), callback_data="alt:show"),
    ]])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("alt:tier3_"))
async def cb_tier3(cb, user, session) -> None:
    _, key = cb.data.split(":", 1)
    lang = user.lang
    text_key = {
        "tier3_yes": "alt.tier3_yes",
        "tier3_no": "alt.tier3_no",
        "tier3_dontknow": "alt.tier3_dontknow",
    }.get(key)
    if text_key:
        await cb.message.answer(t(text_key, lang=lang))
    await cb.answer()


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

    # Разбиваем на короткие сообщения, чтобы Telegram не скроллил к концу.
    intro_msg = "\n\n".join([
        f"<b>{t('alt.title', lang=lang)}</b>",
        t("alt.intro", lang=lang),
        t("alt.what_is_etf", lang=lang),
    ]).strip()
    seb_intro = t("alt.how_seb", lang=lang)
    seb_costs = t("alt.how_seb_costs", lang=lang)
    seb_steps = t("alt.how_seb_steps", lang=lang)
    seb_warnings = t("alt.how_seb_warnings", lang=lang)
    example_msg = "\n\n".join(x for x in [
        t("alt.projection_example", lang=lang),
        proj_line,
    ] if x)
    strategy_caption = "\n\n".join([
        t("alt.strategy", lang=lang),
        t("alt.disclaimer", lang=lang),
    ])
    # На финале Альтернативы — кнопка «📮 Письмо в VSAA».
    tip_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.letter", lang=lang), callback_data="letter:show"),
    ]])

    tier3_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn.tier3_yes", lang=lang), callback_data="alt:tier3_yes")],
        [InlineKeyboardButton(text=t("btn.tier3_no", lang=lang), callback_data="alt:tier3_no")],
        [InlineKeyboardButton(text=t("btn.tier3_dontknow", lang=lang), callback_data="alt:tier3_dontknow")],
    ])

    await cb.message.answer(intro_msg)

    # Фото фонда Swedbank Robur — file_id кеш + fallback
    key = str(_SWEDBANK_IMG)
    photo = _SWEDBANK_FILE_ID.get(key) or FSInputFile(key)
    try:
        sent = await cb.message.answer_photo(
            photo=photo,
            caption=t("alt.swedbank_photo_caption", lang=lang),
        )
        if sent and getattr(sent, "photo", None):
            _SWEDBANK_FILE_ID[key] = sent.photo[-1].file_id
    except Exception:
        pass  # без фото — не падаем

    # Карточка Swedbank Robur разбита на 4 коротких сообщения, чтобы Telegram
    # не скроллил в футер длинного текста.
    await cb.message.answer(seb_intro)
    await cb.message.answer(seb_costs)
    await cb.message.answer(seb_steps)
    await cb.message.answer(seb_warnings)
    if example_msg:
        await cb.message.answer(example_msg)

    # Карточка «Третий уровень» — перед стратегией
    await cb.message.answer(t("alt.tier3_intro", lang=lang), reply_markup=tier3_kb)

    # Стратегия с картинкой (file_id-кеш + fallback).
    key = str(_STRATEGY_IMG)
    photo = _STRATEGY_FILE_ID.get(key) or FSInputFile(key)
    try:
        sent = await cb.message.answer_photo(photo=photo, caption=strategy_caption, reply_markup=tip_kb)
        if sent and getattr(sent, "photo", None):
            _STRATEGY_FILE_ID[key] = sent.photo[-1].file_id
    except Exception:
        await cb.message.answer(strategy_caption, reply_markup=tip_kb)
    await cb.answer()
