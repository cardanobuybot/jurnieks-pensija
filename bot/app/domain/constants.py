"""Домен-константы: ставки, минзарплаты, пенсионные параметры.

Источники: vsaa.gov.lv, vid.gov.lv, likumi.lv.
Не выдумывать значения — TODO + вопрос владельцу, если данных нет.

⚠️ ЕЖЕГОДНАЯ РЕВИЗИЯ (к 15 декабря): MIN_WAGE_BY_YEAR, VSNP_BY_YEAR,
MIN_PENSION_BASE_BY_YEAR — эти три словаря дополняются на следующий год.
Ставка CONTRIBUTION_RATE и структурные константы (G, доли tier1/tier2)
меняются редко — сверять с likumi.lv.
"""

# Ставка добровольных взносов на пенсионное страхование
CONTRIBUTION_RATE = 0.2391

# Минимальная зарплата по годам (€/мес). Обновляется руками к 15 декабря.
MIN_WAGE_BY_YEAR: dict[int, float] = {
    2023: 620.0,
    2024: 700.0,
    2025: 740.0,
    2026: 780.0,
}

# Пособие VSNP (Valsts sociālā nodrošinājuma pabalsts) — что остаётся, если
# нет права на пенсию по возрасту (стаж < 20 лет). €/мес.
VSNP_BY_YEAR: dict[int, float] = {
    2026: 187.0,
}

# База минимальной пенсии (P) — 213 € в 2026. Минпенсия = P × 1.2 + P × 0.02 × (стаж − 20).
MIN_PENSION_BASE_BY_YEAR: dict[int, float] = {
    2026: 213.0,
}

# Реальная годовая инфляция для перевода today's money → nominal at retirement.
# «Инфляция для перевода», сумма из капитала в номинал: используем 2%.
NOMINAL_INFLATION_RATE = 0.02

# Экстраполяция для лет, для которых минзарплата ещё не утверждена.
# Пометка «прогноз» на UI обязательна.
MIN_WAGE_FORECAST_RATE = 0.05  # +5% в год

# Годовая база: не меньше 12×минзарплат, не больше «потолка».
CONTRIBUTION_CAP_ANNUAL = 105_300.0
MONTHS_IN_YEAR = 12

# Пенсионная система
RETIREMENT_AGE = 65
MIN_STAGE_YEARS = 20  # с 01.01.2025
EARLY_RETIREMENT_DELTA_YEARS = 2  # -2 года при 30 годах стажа
EARLY_RETIREMENT_MIN_STAGE = 30

# Из взносов идёт 20% в пенсионный капитал: 15% в 1-й уровень, 5% во 2-й.
CAPITAL_TOTAL_SHARE = 0.20
CAPITAL_TIER1_SHARE = 0.15
CAPITAL_TIER2_SHARE = 0.05

# Реальный рост капитала (в реальных €, для прогноза)
TIER1_REAL_GROWTH = 0.02  # +2%/год
TIER2_REAL_GROWTH = 0.05  # +5%/год

# Делитель G (месяцев дожития) для 65 лет
G_MONTHS_AT_65 = 200

# Минимальная пенсия: база×1.2 при 20 годах, +база×0.02 за каждый год свыше 20.
MIN_PENSION_BASE_2026 = 213.0  # legacy-константа, использует MIN_PENSION_BASE_BY_YEAR[2026]
MIN_PENSION_MULTIPLIER = 1.2
MIN_PENSION_YEAR_BONUS = 4.26  # = 213 × 0.02

# ETF сравнение (реальные). 5% — консервативнее исторического 6%.
ETF_REAL_RETURN = 0.05
ETF_SAFE_WITHDRAWAL = 0.04

# Статистика для приветствия (по годам)
SEAFARERS_STATS = {
    2026: {
        "total": 9891,
        "eu_flag_pct": 51.9,
        "third_country_pct": 46.9,
        "lv_flag_pct": 1.1,
        "source": "Latvijas Jūrnieku reģistrs",
    },
}

# VSAA контакты
VSAA_CONTRIBUTIONS_EMAIL = "iemaksas@vsaa.gov.lv"
VSAA_CONTRIBUTIONS_PHONE = "67600631"
VSAA_GENERAL_PHONE = "64507020"

# VSAA банковские реквизиты для добровольных взносов (стандартные, обновляются редко)
VSAA_RECIPIENT_NAME = "Valsts sociālās apdrošināšanas aģentūra"
VSAA_REG_NUMBER = "90001669496"
VSAA_ACCOUNT = "LV07TREL5180453053000"
VSAA_BANK_NAME = "VALSTS KASE"
VSAA_SWIFT = "TRELLV22"
BUDGET_CODE = "02110"

# Ограничение поля «назначение платежа» в латвийских банках
PAYMENT_PURPOSE_MAX_LEN = 140

# Через сколько дней после первой оплаты бот проверяет «стаж на latvija.lv вырос?»
STAGE_CHECK_AFTER_DAYS = 21

# Флаги: страны, у которых система соц-страхования моряков — фикция
FICTION_EU_FLAGS = {"MAR", "MADEIRA", "CY", "MT"}  # Мадейра, Кипр, Мальта
THIRD_COUNTRY_FLAGS = {"PA", "LR", "MH", "BS"}  # Панама, Либерия, Маршаллы, Багамы
