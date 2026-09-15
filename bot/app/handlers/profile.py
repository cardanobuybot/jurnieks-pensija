"""Профиль: год рождения, стаж (лет + месяцев), капитал tier1/tier2, дата VSAA.

Стаж вводится ДВУМЯ вопросами (полные годы + месяцы 0-11) — иначе
пользователи путают «5.2» = 5.2 года vs 5 лет 2 месяца.

Парсер терпимый: из ответа «5 лет» / «5» / «5,5» извлекает первое число.
"""

from __future__ import annotations

import re
from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..i18n import t

router = Router(name="profile")


class ProfileFSM(StatesGroup):
    birth_year = State()
    stage_years = State()
    stage_months = State()
    tier1 = State()
    tier2 = State()
    vsaa_date = State()


_NUM_RE = re.compile(r"-?\d+[.,]?\d*")


def _extract_number(text: str) -> float | None:
    """Достаёт первое число из строки: «5 лет» → 5.0, «5,5» → 5.5, «12» → 12.0."""
    m = _NUM_RE.search(text.replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", "."))
    except ValueError:
        return None


@router.callback_query(F.data == "calc:profile_start")
async def start_profile(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    await state.set_state(ProfileFSM.birth_year)
    await cb.message.answer(
        f"<b>{t('profile.title', lang=lang)}</b>\n\n"
        f"{t('profile.explain', lang=lang)}\n\n"
        f"<i>{t('profile.oneline_hint', lang=lang)}</i>\n\n"
        f"{t('profile.ask_birth_year', lang=lang)}"
    )
    await cb.answer()


def _try_parse_oneline(text: str) -> tuple[int, float, float, float] | None:
    parts = text.strip().split()
    if len(parts) != 4:
        return None
    try:
        by = int(parts[0])
        st = float(parts[1].replace(",", "."))
        t1 = float(parts[2].replace(",", "."))
        t2 = float(parts[3].replace(",", "."))
        return by, st, t1, t2
    except (ValueError, TypeError):
        return None


@router.message(ProfileFSM.birth_year, F.text)
async def enter_birth_year(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    oneline = _try_parse_oneline(message.text)
    if oneline:
        by, st, t1, t2 = oneline
        await repo.set_profile(session, user, birth_year=by, stage_years=st, tier1=t1, tier2=t2)
        await state.clear()
        from .calc import send_projection
        await send_projection(message, user, session)
        return
    n = _extract_number(message.text)
    if n is None or int(n) < 1900 or int(n) > 2020:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, birth_year=int(n))
    await state.set_state(ProfileFSM.stage_years)
    await message.answer(t("profile.ask_stage_years", lang=lang))


@router.message(ProfileFSM.stage_years, F.text)
async def enter_stage_years(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    n = _extract_number(message.text)
    if n is None or n < 0 or n > 60:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    # Полные годы: сохраняем в state, ждём месяцев
    await state.update_data(stage_years_int=int(n))
    await state.set_state(ProfileFSM.stage_months)
    await message.answer(t("profile.ask_stage_months", lang=lang))


@router.message(ProfileFSM.stage_months, F.text)
async def enter_stage_months(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    n = _extract_number(message.text)
    if n is None or n < 0 or n > 11:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    data = await state.get_data()
    years = data.get("stage_years_int", 0)
    stage_total = years + n / 12.0
    await repo.set_profile(session, user, stage_years=stage_total)
    await state.set_state(ProfileFSM.tier1)
    await message.answer(t("profile.ask_tier1", lang=lang))


@router.message(ProfileFSM.tier1, F.text)
async def enter_tier1(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    n = _extract_number(message.text)
    if n is None or n < 0:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, tier1=n)
    await state.set_state(ProfileFSM.tier2)
    await message.answer(t("profile.ask_tier2", lang=lang))


@router.message(ProfileFSM.tier2, F.text)
async def enter_tier2(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    n = _extract_number(message.text)
    if n is None or n < 0:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, tier2=n)
    await state.set_state(ProfileFSM.vsaa_date)
    await message.answer(t("profile.ask_vsaa_date", lang=lang))


@router.message(ProfileFSM.vsaa_date, F.text)
async def enter_vsaa_date(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    raw = message.text.strip().lower()
    if raw not in ("нет", "nav", "no", "-", "не", "n"):
        try:
            y, m, d = raw.split("-")
            await repo.set_profile(session, user, vsaa_reg_date=date(int(y), int(m), int(d)))
        except (ValueError, TypeError):
            await message.answer(t("profile.parse_error", lang=lang))
            return
    await state.clear()
    from .calc import send_projection
    await send_projection(message, user, session)
