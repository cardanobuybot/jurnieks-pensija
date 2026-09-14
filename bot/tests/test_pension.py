"""Эталонные тесты из спеки. Не менять ожидаемые значения — они привязаны
к утверждённым цифрам VSAA."""

from app.domain.pension import (
    debt_by_months,
    min_pension,
    monthly_contribution,
    project_pension,
)


def test_monthly_contribution_2026():
    assert monthly_contribution(2026) == 186.50


def test_monthly_contribution_2024():
    assert monthly_contribution(2024) == 167.37


def test_projection_stage_5_2_has_right():
    """birth 1982 (44), stage 5.2, first_cap 9442, second_cap 2006,
    платит на мин.базе → стаж 26.2, пенсия 340-380, право есть."""
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
    """birth 1989 (37), stage 0, капитал 0 → стаж 28, пенсия 380-430."""
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


def test_debt_dec_2023_to_aug_2026_min_base():
    """12.2023 – 08.2026 при мин.базе → 33 месяца, ≈5 770 €."""
    r = debt_by_months(2023, 12, 2026, 8, base_monthly=None)
    assert r.months == 33
    assert 5760.0 <= r.total <= 5780.0


def test_min_pension_at_26_years():
    """min_pension(26) → 281.16"""
    assert min_pension(26) == 281.16
