"""Диагностика: 3 вопроса → ветка A/B/C."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..domain.diagnosis import A1Status, Branch, Employer, Flag, diagnose
from ..i18n import t

router = Router(name="diagnosis")


class DiagFSM(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()


def _kb(options: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)] for text, data in options]
    )


@router.callback_query(F.data == "diag:start")
async def start_diagnosis(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    lang = user.lang
    await state.set_state(DiagFSM.q1)
    kb = _kb([
        (t("diag.q1.lv", lang=lang), "d1:LV"),
        (t("diag.q1.eu_other", lang=lang), "d1:EU_OTHER"),
        (t("diag.q1.no_nis", lang=lang), "d1:NO_NIS"),
        (t("diag.q1.third", lang=lang), "d1:THIRD_COUNTRY"),
        (t("diag.q1.unknown", lang=lang), "d1:UNKNOWN"),
    ])
    await cb.message.answer(t("diag.q1.title", lang=lang), reply_markup=kb)
    await cb.answer()


@router.callback_query(DiagFSM.q1, F.data.startswith("d1:"))
async def answer_q1(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    _, flag = cb.data.split(":", 1)
    await state.update_data(flag=flag)
    lang = user.lang
    await state.set_state(DiagFSM.q2)
    kb = _kb([
        (t("diag.q2.lv", lang=lang), "d2:LV"),
        (t("diag.q2.eu_other", lang=lang), "d2:EU_OTHER"),
        (t("diag.q2.non_eu", lang=lang), "d2:NON_EU"),
        (t("diag.q2.unknown", lang=lang), "d2:UNKNOWN"),
    ])
    await cb.message.answer(t("diag.q2.title", lang=lang), reply_markup=kb)
    await cb.answer()


@router.callback_query(DiagFSM.q2, F.data.startswith("d2:"))
async def answer_q2(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    _, emp = cb.data.split(":", 1)
    await state.update_data(employer=emp)
    lang = user.lang
    await state.set_state(DiagFSM.q3)
    kb = _kb([
        (t("diag.q3.yes", lang=lang), "d3:YES"),
        (t("diag.q3.no", lang=lang), "d3:NO"),
        (t("diag.q3.unknown", lang=lang), "d3:UNKNOWN"),
    ])
    await cb.message.answer(t("diag.q3.title", lang=lang), reply_markup=kb)
    await cb.answer()


@router.callback_query(DiagFSM.q3, F.data.startswith("d3:"))
async def answer_q3(cb: CallbackQuery, user: User, session: AsyncSession, state: FSMContext) -> None:
    _, a1 = cb.data.split(":", 1)
    data = await state.get_data()
    flag = Flag(data["flag"])
    emp = Employer(data["employer"])
    a1_st = A1Status(a1)

    result = diagnose(flag=flag, employer_country=emp, has_a1_or_vsaa=a1_st)
    await repo.set_diagnosis(session, user, result.branch.value, is_fiction=result.is_fiction)
    await state.clear()

    lang = user.lang
    body = t(result.reason_key, lang=lang)
    if result.action_key:
        body += "\n\n" + t(result.action_key, lang=lang)
    body += "\n\n" + t("disclaimer.short", lang=lang)

    # Что дальше
    next_kb = None
    if result.branch == Branch.C or result.branch == Branch.B:
        next_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t("btn.open_calc", lang=lang), callback_data="calc:profile_start")
        ]])
    await cb.message.answer(body, reply_markup=next_kb)
    await cb.answer()
