"""Диагностика: 4 вопроса → ветка A/B/C (или UNSURE).

Порядок:
    q0: LV-контракт / dual contract  (перекрывает всё, если да)
    q1: страна работодателя по основному контракту
    q2: флаг судна
    q3: LV A1
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..domain.diagnosis import (
    A1Status,
    Branch,
    Employer,
    Flag,
    LvContract,
    diagnose,
)
from ..i18n import t

router = Router(name="diagnosis")


class DiagFSM(StatesGroup):
    q0 = State()   # LV contract (dual)
    q1 = State()   # employer country
    q2 = State()   # flag
    q3 = State()   # A1


def _kb(options: list[tuple[str, str]], back: bool = False, lang: str = "lv") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=text, callback_data=data)] for text, data in options]
    if back:
        rows.append([InlineKeyboardButton(text=t("btn.back", lang=lang), callback_data="diag:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Граф «назад» для диагностики
_PREV_DIAG = {
    "q1": "q0",
    "q2": "q1",
    "q3": "q2",
}


# ---------- Q0: LV contract ----------


@router.callback_query(F.data == "diag:start")
async def start_diagnosis(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    await state.set_state(DiagFSM.q0)
    kb = _kb([
        (t("diag.q0.yes", lang=lang), "d0:YES"),
        (t("diag.q0.no", lang=lang), "d0:NO"),
        (t("diag.q0.unsure", lang=lang), "d0:UNSURE"),
    ])
    await cb.message.answer(t("diag.q0.title", lang=lang), parse_mode="HTML", reply_markup=kb)
    await cb.answer()


@router.callback_query(DiagFSM.q0, F.data.startswith("d0:"))
async def answer_q0(cb: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    _, lv_c = cb.data.split(":", 1)
    lang = user.lang

    # UNSURE — не идём дальше, показываем подсказку про выписку.
    if lv_c == "UNSURE":
        await state.clear()
        await cb.message.answer(t("diag.q0.unsure_hint", lang=lang), parse_mode="HTML")
        await cb.answer()
        return

    # YES — сразу ветка А без остальных вопросов.
    if lv_c == "YES":
        result = diagnose(
            has_lv_contract=LvContract.YES,
            employer_country=Employer.UNKNOWN,
            flag=Flag.UNKNOWN,
            has_a1_or_vsaa=A1Status.UNKNOWN,
        )
        await _finalize(cb, user, session, state, result)
        return

    # NO — продолжаем с Q1 (работодатель).
    await state.update_data(lv_contract="NO")
    await state.set_state(DiagFSM.q1)
    kb = _kb([
        (t("diag.q2.lv", lang=lang), "d1:LV"),
        (t("diag.q2.eu_other", lang=lang), "d1:EU_OTHER"),
        (t("diag.q2.non_eu", lang=lang), "d1:NON_EU"),
        (t("diag.q2.unknown", lang=lang), "d1:UNKNOWN"),
    ], back=True, lang=lang)
    await cb.message.answer(t("diag.q2.title", lang=lang), reply_markup=kb)
    await cb.answer()


# ---------- Q1: employer ----------


@router.callback_query(DiagFSM.q1, F.data.startswith("d1:"))
async def answer_q1(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    _, emp = cb.data.split(":", 1)
    await state.update_data(employer=emp)
    lang = user.lang
    await state.set_state(DiagFSM.q2)
    kb = _kb([
        (t("diag.q1.lv", lang=lang), "d2:LV"),
        (t("diag.q1.eu_other", lang=lang), "d2:EU_OTHER"),
        (t("diag.q1.no_nis", lang=lang), "d2:NO_NIS"),
        (t("diag.q1.third", lang=lang), "d2:THIRD_COUNTRY"),
        (t("diag.q1.unknown", lang=lang), "d2:UNKNOWN"),
    ], back=True, lang=lang)
    await cb.message.answer(t("diag.q1.title", lang=lang), reply_markup=kb)
    await cb.answer()


# ---------- Q2: flag ----------


@router.callback_query(DiagFSM.q2, F.data.startswith("d2:"))
async def answer_q2(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    _, flag = cb.data.split(":", 1)
    await state.update_data(flag=flag)
    lang = user.lang
    await state.set_state(DiagFSM.q3)
    kb = _kb([
        (t("diag.q3.yes", lang=lang), "d3:YES"),
        (t("diag.q3.no", lang=lang), "d3:NO"),
        (t("diag.q3.unknown", lang=lang), "d3:UNKNOWN"),
        (t("btn.what_is_a1", lang=lang), "diag:a1_info"),
    ], back=True, lang=lang)
    await cb.message.answer(t("diag.q3.title", lang=lang), reply_markup=kb)
    await cb.answer()


# ---------- Q3: A1 ----------


@router.callback_query(DiagFSM.q3, F.data.startswith("d3:"))
async def answer_q3(cb: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    _, a1 = cb.data.split(":", 1)
    data = await state.get_data()
    lv_c = LvContract(data.get("lv_contract", "NO"))
    emp = Employer(data["employer"])
    flag = Flag(data["flag"])
    a1_st = A1Status(a1)

    result = diagnose(
        has_lv_contract=lv_c,
        employer_country=emp,
        flag=flag,
        has_a1_or_vsaa=a1_st,
    )
    await _finalize(cb, user, session, state, result)


# ---------- back navigation ----------


@router.callback_query(F.data == "diag:back")
async def diag_back(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    cur = await state.get_state()
    # cur: 'DiagFSM:q1'|'q2'|'q3'
    key = cur.split(":", 1)[1] if cur else ""
    prev = _PREV_DIAG.get(key)
    if prev is None:
        await cb.answer()
        return
    if prev == "q0":
        await state.set_state(DiagFSM.q0)
        kb = _kb([
            (t("diag.q0.yes", lang=lang), "d0:YES"),
            (t("diag.q0.no", lang=lang), "d0:NO"),
            (t("diag.q0.unsure", lang=lang), "d0:UNSURE"),
        ])
        await cb.message.answer(t("diag.q0.title", lang=lang), reply_markup=kb)
    elif prev == "q1":
        await state.set_state(DiagFSM.q1)
        kb = _kb([
            (t("diag.q2.lv", lang=lang), "d1:LV"),
            (t("diag.q2.eu_other", lang=lang), "d1:EU_OTHER"),
            (t("diag.q2.non_eu", lang=lang), "d1:NON_EU"),
            (t("diag.q2.unknown", lang=lang), "d1:UNKNOWN"),
        ], back=True, lang=lang)
        await cb.message.answer(t("diag.q2.title", lang=lang), reply_markup=kb)
    elif prev == "q2":
        await state.set_state(DiagFSM.q2)
        kb = _kb([
            (t("diag.q1.lv", lang=lang), "d2:LV"),
            (t("diag.q1.eu_other", lang=lang), "d2:EU_OTHER"),
            (t("diag.q1.no_nis", lang=lang), "d2:NO_NIS"),
            (t("diag.q1.third", lang=lang), "d2:THIRD_COUNTRY"),
            (t("diag.q1.unknown", lang=lang), "d2:UNKNOWN"),
        ], back=True, lang=lang)
        await cb.message.answer(t("diag.q1.title", lang=lang), reply_markup=kb)
    await cb.answer()


# ---------- A1 info popup ----------


@router.callback_query(F.data == "diag:a1_info")
async def a1_info(cb: CallbackQuery, user: User) -> None:
    await cb.message.answer(t("diag.a1.explain", lang=user.lang), parse_mode="HTML")
    await cb.answer()


@router.message(Command("a1"))
async def cmd_a1(message: Message, user: User) -> None:
    await message.answer(t("diag.a1.explain", lang=user.lang), parse_mode="HTML")


# ---------- финал ----------


async def _finalize(
    cb: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    result,
) -> None:
    """Показать результат ветки, сохранить в БД, дать кнопку в калькулятор."""
    if result.branch != Branch.UNSURE:
        await repo.set_diagnosis(session, user, result.branch.value, is_fiction=result.is_fiction)
    await state.clear()

    lang = user.lang
    body = t(result.reason_key, lang=lang)
    if result.action_key:
        body += "\n\n" + t(result.action_key, lang=lang)
    body += "\n\n" + t("disclaimer.short", lang=lang)

    # Кнопка в калькулятор только для веток B/C (в A — добровольные не разрешены).
    next_kb = None
    if result.branch in (Branch.B, Branch.C):
        next_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t("btn.open_calc", lang=lang), callback_data="calc:profile_start")
        ]])
    await cb.message.answer(body, parse_mode="HTML", reply_markup=next_kb)
    await cb.answer()
