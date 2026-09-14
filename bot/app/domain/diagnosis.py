"""Диагностика: в какой стране моряка страхуют.

Ветки:
- A: взносы идут в Латвии, добровольные не разрешены (и не нужны).
- B: взносы в другой стране ЕС по 883/2004 ст.11(4), стаж суммируется. Нужен A1.
- C: не платит никто → добровольные взносы через VSAA.

Три вопроса пользователю:
    flag: под каким флагом судно
    employer_country: где зарегистрирован работодатель
    has_a1_or_vsaa: есть ли A1 или взносы в выписке VSAA

Целевая аудитория — латвийские резиденты, поэтому «живёт в LV» подразумевается.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Flag(str, Enum):
    LV = "LV"
    EU_OTHER = "EU_OTHER"           # любой другой ЕС-флаг (в т.ч. MAR/CY/MT-«фикция»)
    NO_NIS = "NO_NIS"               # Норвегия, регистр NIS
    THIRD_COUNTRY = "THIRD_COUNTRY" # Панама/Либерия/Маршаллы/Багамы
    UNKNOWN = "UNKNOWN"


class Employer(str, Enum):
    LV = "LV"
    EU_OTHER = "EU_OTHER"
    NON_EU = "NON_EU"
    UNKNOWN = "UNKNOWN"


class A1Status(str, Enum):
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class Branch(str, Enum):
    A = "A"  # Латвия платит
    B = "B"  # другая страна ЕС платит
    C = "C"  # никто не платит → добровольные


@dataclass
class DiagnosisResult:
    branch: Branch
    reason_key: str            # ключ строки для i18n
    is_fiction: bool = False   # флаг ЕС, но фактически фикция
    needs_action: bool = False # нужно что-то проверить/запросить у работодателя
    action_key: str | None = None


def diagnose(
    flag: Flag,
    employer_country: Employer,
    has_a1_or_vsaa: A1Status,
) -> DiagnosisResult:
    # 1. Латвийский флаг — Латвия и страхует.
    if flag == Flag.LV:
        return DiagnosisResult(branch=Branch.A, reason_key="diag.a.lv_flag")

    # 2. Работодатель зарегистрирован в LV (и резидент LV — подразумевается)
    #    → исключение из 883/2004: страхование в LV.
    if employer_country == Employer.LV:
        return DiagnosisResult(branch=Branch.A, reason_key="diag.a.lv_employer_exception")

    # 3. Норвежский регистр NIS — соглашение Латвия-Норвегия, страхование в LV.
    if flag == Flag.NO_NIS:
        return DiagnosisResult(
            branch=Branch.A,
            reason_key="diag.a.no_nis_agreement",
            needs_action=True,
            action_key="diag.action.request_a1",
        )

    # 4. Флаг третьей страны — никто не платит.
    if flag == Flag.THIRD_COUNTRY:
        return DiagnosisResult(branch=Branch.C, reason_key="diag.c.third_country")

    # 5. Флаг ЕС (не LV) — по ст.11(4) страхование в стране флага.
    if flag == Flag.EU_OTHER:
        if has_a1_or_vsaa == A1Status.YES:
            return DiagnosisResult(branch=Branch.B, reason_key="diag.b.eu_flag_a1_ok")
        if has_a1_or_vsaa == A1Status.NO:
            # Флаг ЕС, но выписка пустая и A1 нет → «фикция» (MAR/CY/MT-паттерн).
            return DiagnosisResult(
                branch=Branch.C,
                reason_key="diag.c.eu_fiction",
                is_fiction=True,
            )
        # UNKNOWN — нужно проверить
        return DiagnosisResult(
            branch=Branch.B,
            reason_key="diag.b.eu_flag_check_a1",
            needs_action=True,
            action_key="diag.action.request_a1",
        )

    # 6. Флаг UNKNOWN — направляем куда посмотреть.
    return DiagnosisResult(
        branch=Branch.C,
        reason_key="diag.unknown.check_docs",
        needs_action=True,
        action_key="diag.action.check_sea_and_latvija_lv",
    )
