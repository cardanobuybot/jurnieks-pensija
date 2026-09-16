/*
 * Порт формул из bot/app/domain/pension.py, 1:1.
 * Числа должны совпадать с backend'ом. При изменении констант в constants.py —
 * править и здесь.
 */

const JP = (function () {

  // ---- constants (sync с bot/app/domain/constants.py) ----
  const CONTRIBUTION_RATE = 0.2391;
  const MIN_WAGE_BY_YEAR = { 2023: 620.0, 2024: 700.0, 2025: 740.0, 2026: 780.0 };
  const MIN_WAGE_FORECAST_RATE = 0.05;
  const CONTRIBUTION_CAP_ANNUAL = 105300.0;
  const MONTHS_IN_YEAR = 12;

  const RETIREMENT_AGE = 65;
  const MIN_STAGE_YEARS = 20;
  const EARLY_RETIREMENT_DELTA_YEARS = 2;
  const EARLY_RETIREMENT_MIN_STAGE = 30;

  const CAPITAL_TIER1_SHARE = 0.15;
  const CAPITAL_TIER2_SHARE = 0.05;
  const FIRST_LEVEL_NOMINAL_GROWTH = 0.04;   // калибр VSAA sept-2026
  const SECOND_LEVEL_NOMINAL_GROWTH = 0.07;
  const INFLATION_RATE = 0.02;
  const G_MONTHS_AT_65 = 200;

  const MIN_PENSION_BASE_2026 = 213.0;
  const MIN_PENSION_MULTIPLIER = 1.2;
  const MIN_PENSION_YEAR_BONUS = 4.26;

  const ETF_REAL_RETURN = 0.05;
  const ETF_SAFE_WITHDRAWAL = 0.04;

  // ---- helpers ----
  function round2(x) { return Math.round(x * 100) / 100; }

  function min_wage(year) {
    if (MIN_WAGE_BY_YEAR[year] !== undefined) return [MIN_WAGE_BY_YEAR[year], false];
    const known = Object.keys(MIN_WAGE_BY_YEAR).map(Number).sort();
    const last = known[known.length - 1];
    if (year > last) {
      let v = MIN_WAGE_BY_YEAR[last];
      for (let i = 0; i < (year - last); i++) v *= (1 + MIN_WAGE_FORECAST_RATE);
      return [round2(v), true];
    }
    return [MIN_WAGE_BY_YEAR[known[0]], true];
  }

  function monthly_contribution(year, base_monthly) {
    const [wage, _] = min_wage(year);
    let eff = (base_monthly == null) ? wage : Math.max(base_monthly, wage);
    const cap = CONTRIBUTION_CAP_ANNUAL / MONTHS_IN_YEAR;
    eff = Math.min(eff, cap);
    return round2(eff * CONTRIBUTION_RATE);
  }

  function annual_contribution(year, base_monthly) {
    return round2(monthly_contribution(year, base_monthly) * MONTHS_IN_YEAR);
  }

  function min_pension(stage_years) {
    if (stage_years < MIN_STAGE_YEARS) return 0.0;
    const base = MIN_PENSION_BASE_2026 * MIN_PENSION_MULTIPLIER;
    const bonus = (stage_years - MIN_STAGE_YEARS) * MIN_PENSION_YEAR_BONUS;
    return round2(base + bonus);
  }

  function project_pension(args) {
    // Модель калибрована по официальному VSAA калькулятору sept-2026.
    // Нормальный рост капитала: tier1 = 4%/год, tier2 = 7%/год.
    // Взнос — начало года (annuity due). Real = nominal ÷ (1+2%)^n.
    const {
      birth_year, current_stage_years, tier1_capital, tier2_capital,
      monthly_base = null, today_year = 2026,
    } = args;

    const current_age = today_year - birth_year;
    const years_left = Math.max(0, RETIREMENT_AGE - current_age);

    const [wage_now, is_fc] = min_wage(today_year);
    let effective_base;
    let contributes;
    if (monthly_base == null) { effective_base = wage_now; contributes = true; }
    else if (monthly_base <= 0) { effective_base = 0; contributes = false; }
    else {
      const cap = CONTRIBUTION_CAP_ANNUAL / MONTHS_IN_YEAR;
      effective_base = Math.min(Math.max(monthly_base, wage_now), cap);
      contributes = true;
    }

    const total_stage = current_stage_years + (contributes ? years_left : 0);
    const has_right = total_stage >= MIN_STAGE_YEARS;
    const years_missing = has_right ? 0 : round2(MIN_STAGE_YEARS - total_stage);
    const can_early = (current_stage_years + years_left - EARLY_RETIREMENT_DELTA_YEARS) >= EARLY_RETIREMENT_MIN_STAGE;

    const annual_base = effective_base * MONTHS_IN_YEAR;
    const t1_add = contributes ? annual_base * CAPITAL_TIER1_SHARE : 0;
    const t2_add = contributes ? annual_base * CAPITAL_TIER2_SHARE : 0;

    let t1_nom = tier1_capital;
    let t2_nom = tier2_capital;
    for (let i = 0; i < years_left; i++) {
      t1_nom = (t1_nom + t1_add) * (1 + FIRST_LEVEL_NOMINAL_GROWTH);
      t2_nom = (t2_nom + t2_add) * (1 + SECOND_LEVEL_NOMINAL_GROWTH);
    }

    const total_cap_nom = t1_nom + t2_nom;
    const monthly_pension_nom = has_right ? total_cap_nom / G_MONTHS_AT_65 : 0;
    const inflation_factor = Math.pow(1 + INFLATION_RATE, years_left);
    const monthly_pension_real = monthly_pension_nom / inflation_factor;

    const total_paid = effective_base * CONTRIBUTION_RATE * MONTHS_IN_YEAR * years_left;

    return {
      current_age,
      years_until_retirement: years_left,
      total_stage_years: round2(total_stage),
      has_right,
      years_missing_for_right: years_missing,
      can_retire_early: can_early,
      tier1_at_retirement: round2(t1_nom / inflation_factor),
      tier2_at_retirement: round2(t2_nom / inflation_factor),
      total_capital: round2(total_cap_nom / inflation_factor),
      monthly_pension: round2(monthly_pension_real),
      monthly_pension_nominal: round2(monthly_pension_nom),
      min_pension_at_stage: min_pension(total_stage),
      total_paid_in: round2(total_paid),
      is_forecast: is_fc,
    };
  }

  // Линейная быстрая оценка (для 21 года до пенсии, аннуитет-дью, tier1 4% / tier2 7%):
  // pension_nominal ≈ (first × 1.04^21 + second × 1.07^21) / 200 + 0.508 × monthly_base
  function pension_nominal_linear(first, second, monthly_base) {
    const years = 21;
    const base_from_capital = (first * Math.pow(1.04, years) + second * Math.pow(1.07, years)) / G_MONTHS_AT_65;
    return round2(base_from_capital + 0.508 * monthly_base);
  }

  function etf_alternative(monthly_amount, years) {
    if (years <= 0 || monthly_amount <= 0) return [0, 0];
    const annual = monthly_amount * MONTHS_IN_YEAR;
    const factor = (Math.pow(1 + ETF_REAL_RETURN, years) - 1) / ETF_REAL_RETURN;
    const capital = annual * factor;
    return [round2(capital), round2(capital * ETF_SAFE_WITHDRAWAL)];
  }

  return { monthly_contribution, annual_contribution, min_pension, project_pension, pension_nominal_linear, etf_alternative, min_wage };
})();
