"""Эталонные тесты из спеки. Не менять ожидаемые значения — они привязаны
к утверждённым цифрам VSAA."""

from datetime import date

from app.domain.pension import (
    debt_by_months,
    min_pension,
    monthly_contribution,
    payment_purpose,
    project_pension,
)


def test_monthly_contribution_2026():
    assert monthly_contribution(2026) == 186.50


def test_monthly_contribution_2024():
    assert monthly_contribution(2024) == 167.37


def test_projection_stage_5_2_has_right():
    """birth 1982 (44), stage 5.2, first_cap 9442, second_cap 2006,
    платит на мин.базе → стаж 26.2, пенсия сегодня 340-380€."""
    p = project_pension(
        birth_year=1982,
        current_stage_years=5.2,
        tier1_capital=9442.0,
        tier2_capital=2006.0,
        monthly_base=None,  # мин
        today_year=2026,
    )
    assert p.total_stage_years == 26.2
    assert p.has_right is True
    assert 340.0 <= p.monthly_pension <= 380.0


def test_projection_zero_capital_young():
    """birth 1989 (37), stage 0, капитал 0 → стаж 28, пенсия 380-430€ сегодня."""
    p = project_pension(
        birth_year=1989,
        current_stage_years=0.0,
        tier1_capital=0.0,
        tier2_capital=0.0,
        monthly_base=None,
        today_year=2026,
    )
    assert p.total_stage_years == 28.0
    assert p.has_right is True
    assert 380.0 <= p.monthly_pension <= 430.0


def test_no_contributions_no_stage_growth():
    """monthly_base=0 → стаж НЕ растёт, права нет если < 20."""
    p = project_pension(
        birth_year=1982,
        current_stage_years=5.17,
        tier1_capital=9442.76,
        tier2_capital=2023.93,
        monthly_base=0,
        today_year=2026,
    )
    assert p.total_stage_years == 5.17
    assert p.has_right is False
    assert p.monthly_pension == 0.0


def test_projection_old_no_right():
    """birth 1970 (56), stage 3 → права нет даже при полной оплате,
    не хватает ~8 лет."""
    p = project_pension(
        birth_year=1970,
        current_stage_years=3.0,
        tier1_capital=0.0,
        tier2_capital=0.0,
        monthly_base=None,
        today_year=2026,
    )
    assert p.has_right is False
    # 65 - 56 = 9 лет остаётся; 3 + 9 = 12; 20 - 12 = 8 → «не хватает ~8»
    assert 7.5 <= p.years_missing_for_right <= 8.5


def test_debt_real_case_with_paid_and_lv_employment():
    """Регистрация 04.12.2023, оплачены дек 2023 и янв 2024,
    работа у LV-работодателя 25.04–10.06.2024, 22.08–26.09.2024,
    17.02–15.03.2025, расчёт на сентябрь 2026.

    Открытых месяцев: 31, сумма 5 475,36 € (10×167.37 + 12×176.93 + 9×186.50).
    Май 2024 исключён (полностью покрыт работой), август/сентябрь 2024
    включены (не полное покрытие).

    Реальный ответ VSAA — сентябрь 2026.
    """
    r = debt_by_months(
        registration_date=date(2023, 12, 4),
        as_of_year=2026,
        as_of_month=9,
        paid_months={(2023, 12), (2024, 1)},
        lv_employment_intervals=[
            (date(2024, 4, 25), date(2024, 6, 10)),
            (date(2024, 8, 22), date(2024, 9, 26)),
            (date(2025, 2, 17), date(2025, 3, 15)),
        ],
    )
    assert r.months == 31
    assert r.total == 5475.36

    # Май 2024 должен быть excluded_lv_employment
    may_2024 = next(l for l in r.lines if (l.year, l.month) == (2024, 5))
    assert may_2024.status == "excluded_lv_employment"

    # Август/сентябрь 2024 — открыты (не полное покрытие)
    aug_2024 = next(l for l in r.lines if (l.year, l.month) == (2024, 8))
    assert aug_2024.status == "open"
    sep_2024 = next(l for l in r.lines if (l.year, l.month) == (2024, 9))
    assert sep_2024.status == "open"

    # Оплаченные не считаются в total
    dec_2023 = next(l for l in r.lines if (l.year, l.month) == (2023, 12))
    assert dec_2023.status == "paid"


def test_payment_purpose_multi_year_no_diacritics():
    """Генератор назначения: группировка по годам, ставка по году,
    LV-диакритика уходит в ASCII."""
    p = payment_purpose(
        months=[(2024, 2), (2024, 3), (2024, 4), (2026, 10)],
        full_name="Jānis Bērziņš",
        personas_kods="010180-12345",
    )
    assert "Bērziņš" not in p.text          # диакритики нет
    assert "Berzins" in p.text
    assert "Brivpratiga iemaksa 02110" in p.text
    assert "pk 010180-12345" in p.text
    assert "2024: 02,03,04 (3x167.37)" in p.text
    assert "2026: 10 (186.50)" in p.text
    # 3×167.37 + 1×186.50 = 502.11 + 186.50 = 688.61
    assert p.total_amount == 688.61
    assert p.fits_bank_field is True
    assert p.length <= 140


def test_payment_purpose_single_month():
    p = payment_purpose(
        months=[(2026, 9)],
        full_name="Anna Ozola",
        personas_kods="150590-11111",
    )
    assert "2026: 09 (186.50)" in p.text
    assert p.total_amount == 186.50


def test_min_pension_at_26_years():
    """min_pension(26) → 281.16"""
    assert min_pension(26) == 281.16
