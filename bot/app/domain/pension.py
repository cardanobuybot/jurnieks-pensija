"""Чистые расчёты пенсии и добровольных взносов. Без aiogram, без БД, без i18n.

Все ставки и константы — из `constants.py`. Ничего не выдумываем.
Округление денежных значений — до 2 знаков (обычное банковское).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .constants import (
    CAPITAL_TIER1_SHARE,
    CAPITAL_TIER2_SHARE,
    CONTRIBUTION_CAP_ANNUAL,
    CONTRIBUTION_RATE,
    EARLY_RETIREMENT_DELTA_YEARS,
    EARLY_RETIREMENT_MIN_STAGE,
    ETF_REAL_RETURN,
    ETF_SAFE_WITHDRAWAL,
    G_MONTHS_AT_65,
    MIN_PENSION_BASE_2026,
    MIN_PENSION_MULTIPLIER,
    MIN_PENSION_YEAR_BONUS,
    MIN_STAGE_YEARS,
    MIN_WAGE_BY_YEAR,
    MIN_WAGE_FORECAST_RATE,
    MONTHS_IN_YEAR,
    RETIREMENT_AGE,
    TIER1_REAL_GROWTH,
    TIER2_REAL_GROWTH,
)


def _round(value: float) -> float:
    return round(value, 2)


def min_wage(year: int) -> tuple[float, bool]:
    """Минзарплата для года. Возвращает (значение, прогноз?).

    Для лет вне таблицы MIN_WAGE_BY_YEAR — экстраполяция +5%/год от последнего
    известного (с пометкой forecast=True).
    """
    if year in MIN_WAGE_BY_YEAR:
        return MIN_WAGE_BY_YEAR[year], False
    known_years = sorted(MIN_WAGE_BY_YEAR.keys())
    last_known = known_years[-1]
    if year > last_known:
        value = MIN_WAGE_BY_YEAR[last_known]
        for _ in range(year - last_known):
            value *= 1.0 + MIN_WAGE_FORECAST_RATE
        return _round(value), True
    # для лет до самого раннего известного — берём то же значение
    return MIN_WAGE_BY_YEAR[known_years[0]], True


def monthly_contribution(year: int, base_monthly: float | None = None) -> float:
    """Ежемесячный взнос при заданной месячной базе.

    Если base_monthly не задан — берётся минзарплата года.
    База не может быть меньше минзарплаты и в сумме за год — больше CONTRIBUTION_CAP_ANNUAL.
    """
    wage, _ = min_wage(year)
    effective = wage if base_monthly is None else max(base_monthly, wage)
    cap_monthly = CONTRIBUTION_CAP_ANNUAL / MONTHS_IN_YEAR
    effective = min(effective, cap_monthly)
    return _round(effective * CONTRIBUTION_RATE)


def annual_contribution(year: int, base_monthly: float | None = None) -> float:
    return _round(monthly_contribution(year, base_monthly) * MONTHS_IN_YEAR)


def min_pension(stage_years: float) -> float:
    """Гарантированная минимальная пенсия для 2026 при данном стаже.

    Возвращает 0.0 если стажа не хватает для права на пенсию по возрасту.
    """
    if stage_years < MIN_STAGE_YEARS:
        return 0.0
    base = MIN_PENSION_BASE_2026 * MIN_PENSION_MULTIPLIER
    bonus = (stage_years - MIN_STAGE_YEARS) * MIN_PENSION_YEAR_BONUS
    return _round(base + bonus)


@dataclass
class DebtLine:
    year: int
    month: int
    amount: float


@dataclass
class DebtResult:
    months: int
    total: float
    lines: list[DebtLine] = field(default_factory=list)


def debt_by_months(
    from_year: int,
    from_month: int,
    to_year: int,
    to_month: int,
    base_monthly: float | None = None,
) -> DebtResult:
    """Долг за диапазон месяцев (включительно), по ставке+минзарплате каждого года.

    base_monthly — если задан, база фиксирована; иначе минзарплата года.
    """
    lines: list[DebtLine] = []
    y, m = from_year, from_month
    while (y, m) <= (to_year, to_month):
        amount = monthly_contribution(y, base_monthly)
        lines.append(DebtLine(year=y, month=m, amount=amount))
        m += 1
        if m > 12:
            m = 1
            y += 1
    total = _round(sum(l.amount for l in lines))
    return DebtResult(months=len(lines), total=total, lines=lines)


@dataclass
class PensionProjection:
    current_age: int
    years_until_retirement: int
    total_stage_years: float
    has_right: bool
    years_missing_for_right: float
    can_retire_early: bool
    tier1_at_retirement: float
    tier2_at_retirement: float
    total_capital: float
    monthly_pension: float
    min_pension_at_stage: float
    total_paid_in: float
    is_forecast: bool


def project_pension(
    birth_year: int,
    current_stage_years: float,
    tier1_capital: float,
    tier2_capital: float,
    monthly_base: float | None = None,
    today_year: int = 2026,
) -> PensionProjection:
    """Прогноз пенсии в сегодняшних (real 2026) €.

    Модель: каждый год до 65 лет пользователь платит на базу monthly_base
    (или min, если None). Из базы 15% → tier1, 5% → tier2. Существующий
    капитал растёт в реальных величинах: tier1 +2%/год, tier2 +5%/год.
    В сегодняшних деньгах min-base фиксируем на 2026, форкаст не применяем
    (rationale: мы уже говорим в present-value € 2026).
    """
    current_age = today_year - birth_year
    years_left = max(0, RETIREMENT_AGE - current_age)
    total_stage = current_stage_years + years_left

    has_right = total_stage >= MIN_STAGE_YEARS
    years_missing = 0.0 if has_right else _round(MIN_STAGE_YEARS - total_stage)

    can_early = (
        current_stage_years + years_left - EARLY_RETIREMENT_DELTA_YEARS
        >= EARLY_RETIREMENT_MIN_STAGE
    )

    wage_2026, is_fc = min_wage(today_year)
    effective_base = wage_2026 if monthly_base is None else max(monthly_base, wage_2026)
    cap_monthly = CONTRIBUTION_CAP_ANNUAL / MONTHS_IN_YEAR
    effective_base = min(effective_base, cap_monthly)

    annual_base = effective_base * MONTHS_IN_YEAR
    tier1_yearly_add = annual_base * CAPITAL_TIER1_SHARE
    tier2_yearly_add = annual_base * CAPITAL_TIER2_SHARE

    t1 = tier1_capital
    t2 = tier2_capital
    for _ in range(years_left):
        t1 = t1 * (1.0 + TIER1_REAL_GROWTH) + tier1_yearly_add
        t2 = t2 * (1.0 + TIER2_REAL_GROWTH) + tier2_yearly_add

    total_cap = t1 + t2
    monthly_pension_val = total_cap / G_MONTHS_AT_65 if has_right else 0.0

    total_paid = effective_base * CONTRIBUTION_RATE * MONTHS_IN_YEAR * years_left

    return PensionProjection(
        current_age=current_age,
        years_until_retirement=years_left,
        total_stage_years=_round(total_stage),
        has_right=has_right,
        years_missing_for_right=years_missing,
        can_retire_early=can_early,
        tier1_at_retirement=_round(t1),
        tier2_at_retirement=_round(t2),
        total_capital=_round(total_cap),
        monthly_pension=_round(monthly_pension_val),
        min_pension_at_stage=min_pension(total_stage),
        total_paid_in=_round(total_paid),
        is_forecast=is_fc,
    )


def reverse_calc_base(target_pension: float, years_left: int, existing_capital: float = 0.0) -> float | None:
    """Сколько платить в месяц, чтобы получить target_pension в 65.

    Возвращает None если target недостижим при потолке базы.
    Модель упрощена: рост капитала берём как среднее между tier1/tier2 (~3.5% real).
    """
    if years_left <= 0:
        return None
    target_capital = target_pension * G_MONTHS_AT_65 - existing_capital
    if target_capital <= 0:
        return 0.0
    growth = (TIER1_REAL_GROWTH * CAPITAL_TIER1_SHARE + TIER2_REAL_GROWTH * CAPITAL_TIER2_SHARE) / (
        CAPITAL_TIER1_SHARE + CAPITAL_TIER2_SHARE
    )
    # geometric sum: A*((1+g)^n - 1)/g = target_capital, где A = annual_add
    factor = ((1.0 + growth) ** years_left - 1.0) / growth if growth > 0 else years_left
    annual_add_needed = target_capital / factor
    annual_base_needed = annual_add_needed / (CAPITAL_TIER1_SHARE + CAPITAL_TIER2_SHARE)
    monthly = annual_base_needed / MONTHS_IN_YEAR
    cap = CONTRIBUTION_CAP_ANNUAL / MONTHS_IN_YEAR
    if monthly > cap:
        return None
    return _round(monthly)


def etf_alternative(monthly_amount: float, years: int) -> tuple[float, float]:
    """Тот же денежный поток в ETF под 6% реальных → (капитал, годовой доход при 4%)."""
    if years <= 0 or monthly_amount <= 0:
        return 0.0, 0.0
    annual = monthly_amount * MONTHS_IN_YEAR
    factor = ((1.0 + ETF_REAL_RETURN) ** years - 1.0) / ETF_REAL_RETURN
    capital = annual * factor
    return _round(capital), _round(capital * ETF_SAFE_WITHDRAWAL)
