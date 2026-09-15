"""Чистые расчёты пенсии и добровольных взносов. Без aiogram, без БД, без i18n.

Все ставки и константы — из `constants.py`. Ничего не выдумываем.
Округление денежных значений — до 2 знаков (обычное банковское).
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from .constants import (
    BUDGET_CODE,
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
    NOMINAL_INFLATION_RATE,
    PAYMENT_PURPOSE_MAX_LEN,
    RETIREMENT_AGE,
    TIER1_REAL_GROWTH,
    TIER2_REAL_GROWTH,
    VSNP_BY_YEAR,
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

    Формула: MIN_PENSION_BASE × 1.2 + MIN_PENSION_BASE × 0.02 × (стаж - 20).
    Возвращает 0.0 если стажа не хватает для права на пенсию по возрасту.
    """
    if stage_years < MIN_STAGE_YEARS:
        return 0.0
    base = MIN_PENSION_BASE_2026 * MIN_PENSION_MULTIPLIER
    bonus = (stage_years - MIN_STAGE_YEARS) * MIN_PENSION_YEAR_BONUS
    return _round(base + bonus)


def vsnp_for_year(year: int = 2026) -> float:
    """Пособие VSNP (Valsts sociālā nodrošinājuma pabalsts), €/мес.

    Что останется, если нет права на пенсию по возрасту (стаж < 20 лет).
    """
    if year in VSNP_BY_YEAR:
        return VSNP_BY_YEAR[year]
    # для отсутствующих годов — берём последний известный (в UI пометить как прогноз)
    latest = max(VSNP_BY_YEAR.keys())
    return VSNP_BY_YEAR[latest]


@dataclass
class DebtLine:
    year: int
    month: int
    amount: float
    status: str  # "open" | "paid" | "excluded_lv_employment"


@dataclass
class DebtResult:
    months: int         # число ОТКРЫТЫХ месяцев (без paid/excluded)
    total: float        # сумма по открытым месяцам
    lines: list[DebtLine] = field(default_factory=list)  # все месяцы диапазона со статусом


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _is_month_fully_covered(
    year: int, month: int, intervals: Iterable[tuple[date, date]]
) -> bool:
    """True, если хотя бы один интервал полностью покрывает весь месяц.

    Правило VSAA: месяц исключается из добровольных, только если работа
    у LV-работодателя покрывает его ЦЕЛИКОМ. Иначе можно доплатить.
    """
    m_start, m_end = _month_bounds(year, month)
    for iv_start, iv_end in intervals:
        if iv_start <= m_start and iv_end >= m_end:
            return True
    return False


def debt_by_months(
    registration_date: date,
    as_of_year: int,
    as_of_month: int,
    paid_months: set[tuple[int, int]] | None = None,
    lv_employment_intervals: Iterable[tuple[date, date]] | None = None,
    base_monthly: float | None = None,
) -> DebtResult:
    """Открытые месяцы и сумма долга.

    Диапазон: с месяца регистрации (registration_date.year, .month) по (as_of_year, as_of_month)
    включительно. Ставка — минзарплата×23.91% ТОГО ГОДА, к которому относится месяц.

    Исключаются:
      - paid_months: явно оплаченные (VSAA подтвердил или пользователь отметил)
      - месяцы, ЦЕЛИКОМ покрытые интервалами lv_employment_intervals (обязательные
        взносы уже шли, добровольные не принимаются). Неполный месяц НЕ исключается.

    Возвращает DebtResult со всеми месяцами (со статусом) и агрегатами по открытым.
    """
    paid = paid_months or set()
    intervals = list(lv_employment_intervals or [])

    y, m = registration_date.year, registration_date.month
    lines: list[DebtLine] = []
    while (y, m) <= (as_of_year, as_of_month):
        amount = monthly_contribution(y, base_monthly)
        if (y, m) in paid:
            status = "paid"
        elif _is_month_fully_covered(y, m, intervals):
            status = "excluded_lv_employment"
        else:
            status = "open"
        lines.append(DebtLine(year=y, month=m, amount=amount, status=status))
        m += 1
        if m > 12:
            m = 1
            y += 1

    open_lines = [l for l in lines if l.status == "open"]
    total = _round(sum(l.amount for l in open_lines))
    return DebtResult(months=len(open_lines), total=total, lines=lines)


# ---------- Генератор назначения платежа ----------

# LV → ASCII транслитерация (для банковского поля назначения).
_LV_TRANSLIT = str.maketrans({
    "ā": "a", "č": "c", "ē": "e", "ģ": "g", "ī": "i", "ķ": "k",
    "ļ": "l", "ņ": "n", "š": "s", "ū": "u", "ž": "z",
    "Ā": "A", "Č": "C", "Ē": "E", "Ģ": "G", "Ī": "I", "Ķ": "K",
    "Ļ": "L", "Ņ": "N", "Š": "S", "Ū": "U", "Ž": "Z",
})


def transliterate_lv_to_ascii(text: str) -> str:
    """Убирает латышскую диакритику; неизменяет остальное."""
    return text.translate(_LV_TRANSLIT)


@dataclass
class PaymentPurpose:
    text: str
    length: int
    fits_bank_field: bool
    total_amount: float


def payment_purpose(
    months: Iterable[tuple[int, int]],
    full_name: str,
    personas_kods: str,
    max_len: int = PAYMENT_PURPOSE_MAX_LEN,
    base_monthly: float | None = None,
) -> PaymentPurpose:
    """Генератор строки «назначение платежа» для банковского перевода.

    Пример вывода:
      Brivpratiga iemaksa 02110, Janis Berzins, pk 010180-12345,
      2024: 02,03,04 (3x167.37); 2026: 10 (186.50)

    Никакой диакритики. Personas kods передаётся вызывающим, не сохраняется.
    """
    # Группируем по годам, сохраняя порядок.
    by_year: dict[int, list[int]] = {}
    for y, m in sorted(set(months)):
        by_year.setdefault(y, []).append(m)

    parts: list[str] = []
    grand_total = 0.0
    for y, ms in by_year.items():
        rate_year = monthly_contribution(y, base_monthly)
        grand_total += rate_year * len(ms)
        months_str = ",".join(f"{m:02d}" for m in ms)
        if len(ms) == 1:
            parts.append(f"{y}: {months_str} ({rate_year:.2f})")
        else:
            parts.append(f"{y}: {months_str} ({len(ms)}x{rate_year:.2f})")
    tail = "; ".join(parts)

    name_ascii = transliterate_lv_to_ascii(full_name).strip()
    header = f"Brivpratiga iemaksa {BUDGET_CODE}, {name_ascii}, pk {personas_kods}, "
    text = header + tail
    return PaymentPurpose(
        text=text,
        length=len(text),
        fits_bank_field=len(text) <= max_len,
        total_amount=_round(grand_total),
    )


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
    tier3_at_retirement: float         # частный 3-й уровень, ЛИЧНОЕ накопление
    total_capital: float               # tier1 + tier2 (для гос. пенсии)
    monthly_pension: float             # в сегодняшних деньгах (real, 2026 €)
    monthly_pension_nominal: float     # в номинале к году выхода на пенсию
    min_pension_at_stage: float
    vsnp_at_no_right: float            # что останется без права на пенсию
    total_paid_in: float
    is_forecast: bool


def project_pension(
    birth_year: int,
    current_stage_years: float,
    tier1_capital: float,
    tier2_capital: float,
    tier3_capital: float = 0.0,
    monthly_base: float | None = None,
    today_year: int = 2026,
) -> PensionProjection:
    """Прогноз пенсии в сегодняшних (real 2026) €.

    Гос. пенсия считается ТОЛЬКО из tier1 + tier2 (обязательные уровни).
    Tier3 — частный уровень, растёт независимо (5% реальных), показывается
    отдельно.

    Модель: каждый год до 65 лет пользователь платит на базу monthly_base
    (или min, если None). Из базы 15% → tier1, 5% → tier2. Существующий
    капитал растёт в реальных величинах: tier1 +2%/год, tier2 +5%/год.
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

    # Tier3 растёт как ETF/фондовое: 5% реальных, без новых взносов
    # (не спрашиваем, сколько будешь довкладывать).
    t3 = tier3_capital * ((1.0 + ETF_REAL_RETURN) ** years_left)

    total_cap = t1 + t2
    monthly_pension_val = total_cap / G_MONTHS_AT_65 if has_right else 0.0
    # Переводим в номинал к году выхода: today_$ × (1+i)^years_left, i=2%
    nominal_factor = (1.0 + NOMINAL_INFLATION_RATE) ** years_left
    monthly_pension_nominal = monthly_pension_val * nominal_factor

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
        tier3_at_retirement=_round(t3),
        total_capital=_round(total_cap),
        monthly_pension=_round(monthly_pension_val),
        monthly_pension_nominal=_round(monthly_pension_nominal),
        min_pension_at_stage=min_pension(total_stage),
        vsnp_at_no_right=vsnp_for_year(today_year),
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
