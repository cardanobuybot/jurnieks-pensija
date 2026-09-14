from app.domain.diagnosis import (
    A1Status,
    Branch,
    Employer,
    Flag,
    LvContract,
    diagnose,
)


# ---------- новые эталонные кейсы (двойные контракты) ----------


def test_dual_contract_lv_agency_overrides_third_country_flag():
    """Параллельный LV-контракт = да, основной GB, флаг PA → А
    (двойной контракт: VSAOI идут через LV-агентство)."""
    r = diagnose(
        has_lv_contract=LvContract.YES,
        employer_country=Employer.NON_EU,   # GB
        flag=Flag.THIRD_COUNTRY,             # PA
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.A
    assert r.reason_key == "diag.a.lv_agency_active"


def test_no_dual_de_pt_no_a1_is_fiction():
    """Параллельного нет, основной DE, флаг PT, A1 нет → В «фикция»."""
    r = diagnose(
        has_lv_contract=LvContract.NO,
        employer_country=Employer.EU_OTHER,
        flag=Flag.EU_OTHER,
        has_a1_or_vsaa=A1Status.NO,
    )
    assert r.branch == Branch.C
    assert r.is_fiction is True


def test_no_dual_de_pt_a1_yes_is_branch_b():
    """Параллельного нет, основной DE, флаг PT, A1 есть → Б."""
    r = diagnose(
        has_lv_contract=LvContract.NO,
        employer_country=Employer.EU_OTHER,
        flag=Flag.EU_OTHER,
        has_a1_or_vsaa=A1Status.YES,
    )
    assert r.branch == Branch.B
    assert r.is_fiction is False


def test_lv_contract_unsure_defers_diagnosis():
    """«Не уверен» — ветку НЕ определяем, показываем подсказку про выписку."""
    r = diagnose(
        has_lv_contract=LvContract.UNSURE,
        employer_country=Employer.EU_OTHER,
        flag=Flag.THIRD_COUNTRY,
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.UNSURE
    assert r.reason_key == "diag.unsure.check_lv_agency"


# ---------- существующие кейсы (двойной контракт = NO) ----------


def test_pt_flag_de_employer_no_a1_is_branch_c_fiction():
    r = diagnose(
        has_lv_contract=LvContract.NO,
        flag=Flag.EU_OTHER,
        employer_country=Employer.EU_OTHER,
        has_a1_or_vsaa=A1Status.NO,
    )
    assert r.branch == Branch.C
    assert r.is_fiction is True


def test_lv_flag_is_branch_a():
    r = diagnose(
        has_lv_contract=LvContract.NO,
        flag=Flag.LV,
        employer_country=Employer.UNKNOWN,
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.A


def test_no_nis_is_branch_a():
    r = diagnose(
        has_lv_contract=LvContract.NO,
        flag=Flag.NO_NIS,
        employer_country=Employer.EU_OTHER,
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.A


def test_cy_flag_lv_employer_is_branch_a():
    r = diagnose(
        has_lv_contract=LvContract.NO,
        flag=Flag.EU_OTHER,       # CY
        employer_country=Employer.LV,
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.A


def test_eu_flag_with_a1_is_branch_b():
    r = diagnose(
        has_lv_contract=LvContract.NO,
        flag=Flag.EU_OTHER,
        employer_country=Employer.EU_OTHER,
        has_a1_or_vsaa=A1Status.YES,
    )
    assert r.branch == Branch.B
    assert r.is_fiction is False


def test_third_country_flag_is_branch_c():
    r = diagnose(
        has_lv_contract=LvContract.NO,
        flag=Flag.THIRD_COUNTRY,
        employer_country=Employer.NON_EU,
        has_a1_or_vsaa=A1Status.NO,
    )
    assert r.branch == Branch.C
