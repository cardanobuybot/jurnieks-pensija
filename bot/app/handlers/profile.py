"""Профиль: год рождения, стаж, капитал tier1/tier2, дата VSAA.

Парсер терпимый: из ответа «5 лет» / «5» / «5,5» извлекает первое число.
Каждый шаг имеет кнопку «◀ Назад» — возврат к предыдущему вопросу.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)



from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..i18n import t

router = Router(name="profile")

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_IMG_SEARCH = _ASSETS / "latvija_search.png"
_IMG_SERVICE = _ASSETS / "latvija_service.png"
_IMG_MANA_PENSIJA = _ASSETS / "latvija_mana_pensija.png"

# Кеш file_id — после первой отправки Telegram выдаёт id, дальше не грузим 300кб.
_FILE_ID: dict[str, str] = {}


def _photo(path):
    """Вернуть file_id (если уже в кеше) или FSInputFile."""
    key = str(path)
    return _FILE_ID.get(key) or FSInputFile(key)


def _cache_from_message(path, msg) -> None:
    if msg and getattr(msg, "photo", None):
        _FILE_ID[str(path)] = msg.photo[-1].file_id


def _cache_from_messages(paths, msgs) -> None:
    for path, m in zip(paths, msgs or []):
        _cache_from_message(path, m)


class ProfileFSM(StatesGroup):
    birth_year = State()
    stage_years = State()
    tier1 = State()
    tier2 = State()
    tier3 = State()
    vsaa_date = State()


# Граф «назад»: state → предыдущее
_PREV_STATE = {
    ProfileFSM.stage_years: ProfileFSM.birth_year,
    ProfileFSM.tier1: ProfileFSM.stage_years,
    ProfileFSM.tier2: ProfileFSM.tier1,
    ProfileFSM.tier3: ProfileFSM.tier2,
    ProfileFSM.vsaa_date: ProfileFSM.tier3,
}

# Какой вопрос показывать в state
_ASK_KEY = {
    ProfileFSM.birth_year: "profile.ask_birth_year",
    ProfileFSM.stage_years: "profile.ask_stage_years",
    ProfileFSM.tier1: "profile.ask_tier1",
    ProfileFSM.tier2: "profile.ask_tier2",
    ProfileFSM.tier3: "profile.ask_tier3",
    ProfileFSM.vsaa_date: "profile.ask_vsaa_date",
}


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


def _back_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.back", lang=lang), callback_data="prof:back")
    ]])


@router.callback_query(F.data == "calc:profile_start")
async def start_profile(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    await state.set_state(ProfileFSM.birth_year)
    intro_caption = (
        f"<b>{t('profile.title', lang=lang)}</b>\n\n"
        f"{t('profile.explain', lang=lang)}\n\n"
        f"{t('profile.latvija_lv_steps', lang=lang)}"
    )
    # Media group [search, service] — file_id-кеш если уже есть, иначе загрузка.
    media = [
        InputMediaPhoto(media=_photo(_IMG_SEARCH), caption=intro_caption),
        InputMediaPhoto(media=_photo(_IMG_SERVICE)),
    ]
    try:
        sent = await cb.message.answer_media_group(media=media)
        _cache_from_messages([_IMG_SEARCH, _IMG_SERVICE], sent)
    except Exception:
        # если Telegram зависает — идём без фото, лишь бы юзер прошёл дальше
        await cb.message.answer(intro_caption)

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.found_it", lang=lang), callback_data="prof:found"),
    ]])
    await cb.message.answer(t("profile.found_it_prompt", lang=lang), reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "prof:found")
async def profile_found_it(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    await state.set_state(ProfileFSM.birth_year)
    q_caption = (
        f"<i>{t('profile.oneline_hint', lang=lang)}</i>\n\n"
        f"{t('profile.ask_birth_year', lang=lang)}"
    )
    try:
        sent = await cb.message.answer_photo(photo=_photo(_IMG_MANA_PENSIJA), caption=q_caption)
        _cache_from_message(_IMG_MANA_PENSIJA, sent)
    except Exception:
        await cb.message.answer(q_caption)
    await cb.answer()


@router.callback_query(F.data == "prof:back")
async def profile_back(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    current = await state.get_state()
    target = None
    for st in _PREV_STATE:
        if st.state == current:
            target = _PREV_STATE[st]
            break
    if target is None:
        await cb.answer()
        return
    await state.set_state(target)
    kb = _back_kb(lang) if target != ProfileFSM.birth_year else None
    await cb.message.answer(t(_ASK_KEY[target], lang=lang), reply_markup=kb)
    await cb.answer()


def _try_parse_oneline(text: str) -> tuple[int, float, float, float, float] | None:
    """4 или 5 чисел: год стаж tier1 tier2 [tier3]. Tier3 по умолчанию 0."""
    parts = text.strip().split()
    if len(parts) not in (4, 5):
        return None
    try:
        by = int(parts[0])
        st = float(parts[1].replace(",", "."))
        t1 = float(parts[2].replace(",", "."))
        t2 = float(parts[3].replace(",", "."))
        t3 = float(parts[4].replace(",", ".")) if len(parts) == 5 else 0.0
        return by, st, t1, t2, t3
    except (ValueError, TypeError):
        return None


@router.message(ProfileFSM.birth_year, F.text)
async def enter_birth_year(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    oneline = _try_parse_oneline(message.text)
    if oneline:
        by, st, t1, t2, t3 = oneline
        await repo.set_profile(session, user, birth_year=by, stage_years=st, tier1=t1, tier2=t2, tier3=t3)
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
    await repo.set_profile(session, user, stage_years=float(n))
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
    await state.set_state(ProfileFSM.tier3)
    await message.answer(t("profile.ask_tier3", lang=lang))


@router.message(ProfileFSM.tier3, F.text)
async def enter_tier3(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    n = _extract_number(message.text)
    if n is None or n < 0:
        await message.answer(t("profile.parse_error", lang=lang))
        return
    await repo.set_profile(session, user, tier3=n)
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
