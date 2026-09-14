"""Профиль: год рождения, стаж, капитал tier1/tier2, дата регистрации VSAA."""

from __future__ import annotations

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
    stage = State()
    tier1 = State()
    tier2 = State()
    vsaa_date = State()


@router.callback_query(F.data == "calc:profile_start")
async def start_profile(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    await state.set_state(ProfileFSM.birth_year)
    await cb.message.answer(
        f"<b>{t('profile.title', lang=lang)}</b>\n\n"
        f"{t('profile.explain', lang=lang)}\n\n"
        f"<i>{t('profile.oneline_hint', lang=lang)}</i>\n\n"
        f"{t('profile.ask_birth_year', lang=lang)}",
        parse_mode="HTML",
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
        await message.answer(t("profile.saved", lang=lang))
        from .calc import send_projection
        await send_projection(message, user, session)
        return
    try:
        by = int(message.text.strip())
        if by < 1900 or by > 2020:
            raise ValueError
    except ValueError:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, birth_year=by)
    await state.set_state(ProfileFSM.stage)
    await message.answer(t("profile.ask_stage", lang=lang))


@router.message(ProfileFSM.stage, F.text)
async def enter_stage(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    try:
        st = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, stage_years=st)
    await state.set_state(ProfileFSM.tier1)
    await message.answer(t("profile.ask_tier1", lang=lang))


@router.message(ProfileFSM.tier1, F.text)
async def enter_tier1(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    try:
        v = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, tier1=v)
    await state.set_state(ProfileFSM.tier2)
    await message.answer(t("profile.ask_tier2", lang=lang))


@router.message(ProfileFSM.tier2, F.text)
async def enter_tier2(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    try:
        v = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, tier2=v)
    await state.set_state(ProfileFSM.vsaa_date)
    await message.answer(t("profile.ask_vsaa_date", lang=lang))


@router.message(ProfileFSM.vsaa_date, F.text)
async def enter_vsaa_date(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    raw = message.text.strip().lower()
    if raw not in ("нет", "nav", "no", "-"):
        try:
            y, m, d = raw.split("-")
            await repo.set_profile(session, user, vsaa_reg_date=date(int(y), int(m), int(d)))
        except (ValueError, TypeError):
            await message.answer(t("profile.parse_error", lang=lang))
            return
    await state.clear()
    await message.answer(t("profile.saved", lang=lang))
    from .calc import send_projection
    await send_projection(message, user, session)
