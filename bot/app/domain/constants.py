"""Домен-константы: ставки, минзарплаты, пенсионные параметры.

Источники: vsaa.gov.lv, vid.gov.lv, likumi.lv.
Не выдумывать значения — TODO + вопрос владельцу, если данных нет.
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

# Минимальная пенсия 2026: 213 × 1.2 при 20 годах, +4.26 за каждый год свыше 20
MIN_PENSION_BASE_2026 = 213.0
MIN_PENSION_MULTIPLIER = 1.2
MIN_PENSION_YEAR_BONUS = 4.26

# ETF сравнение (реальные)
ETF_REAL_RETURN = 0.06
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

# Флаги: страны, у которых система соц-страхования моряков — фикция
FICTION_EU_FLAGS = {"MAR", "MADEIRA", "CY", "MT"}  # Мадейра, Кипр, Мальта
THIRD_COUNTRY_FLAGS = {"PA", "LR", "MH", "BS"}  # Панама, Либерия, Маршаллы, Багамы
