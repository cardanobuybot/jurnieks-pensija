from app.domain.diagnosis import (
    A1Status,
    Branch,
    Employer,
    Flag,
    diagnose,
)


def test_pt_flag_de_employer_no_a1_is_branch_c_fiction():
    """PT (EU_OTHER, вероятно Madeira MAR) + работодатель DE + нет A1
    → В с пометкой «фикция»."""
    r = diagnose(
        flag=Flag.EU_OTHER,
        employer_country=Employer.EU_OTHER,
        has_a1_or_vsaa=A1Status.NO,
    )
    assert r.branch == Branch.C
    assert r.is_fiction is True


def test_lv_flag_is_branch_a():
    r = diagnose(
        flag=Flag.LV,
        employer_country=Employer.UNKNOWN,
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.A


def test_no_nis_is_branch_a():
    """NO + NIS-регистр → А (соглашение Латвия-Норвегия)."""
    r = diagnose(
        flag=Flag.NO_NIS,
        employer_country=Employer.EU_OTHER,
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.A


def test_cy_flag_lv_employer_is_branch_a():
    """CY + работодатель LV + живёт LV (подразумевается) → А (исключение)."""
    r = diagnose(
        flag=Flag.EU_OTHER,       # CY
        employer_country=Employer.LV,
        has_a1_or_vsaa=A1Status.UNKNOWN,
    )
    assert r.branch == Branch.A


def test_eu_flag_with_a1_is_branch_b():
    r = diagnose(
        flag=Flag.EU_OTHER,
        employer_country=Employer.EU_OTHER,
        has_a1_or_vsaa=A1Status.YES,
    )
    assert r.branch == Branch.B
    assert r.is_fiction is False


def test_third_country_flag_is_branch_c():
    r = diagnose(
        flag=Flag.THIRD_COUNTRY,
        employer_country=Employer.NON_EU,
        has_a1_or_vsaa=A1Status.NO,
    )
    assert r.branch == Branch.C
