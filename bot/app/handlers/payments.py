"""/payments — отметить месяц, история."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..domain.pension import monthly_contribution
from ..i18n import t

router = Router(name="payments")


class PayFSM(StatesGroup):
    month = State()


def _pay_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.mark_paid", lang=lang), callback_data="pay:mark"),
        InlineKeyboardButton(text=t("btn.history", lang=lang), callback_data="pay:history"),
    ]])


@router.message(Command("payments"))
async def cmd_payments(message: Message, user: User) -> None:
    lang = user.lang
    await message.answer(t("payments.title", lang=lang), reply_markup=_pay_kb(lang))


@router.callback_query(F.data == "pay:mark")
async def cb_mark(cb: CallbackQuery, user: User, state: FSMContext) -> None:
    await state.set_state(PayFSM.month)
    await cb.message.answer(t("payments.mark_prompt", lang=user.lang))
    await cb.answer()


@router.message(PayFSM.month, F.text)
async def enter_month(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    raw = message.text.strip()
    try:
        y_str, m_str = raw.split("-")
        y = int(y_str)
        m = int(m_str)
        if not 1 <= m <= 12 or y < 2020 or y > 2035:
            raise ValueError
    except ValueError:
        await message.answer(t("payments.parse_error", lang=lang))
        return
    amount = monthly_contribution(y, user.monthly_base)
    await repo.mark_payment(session, user, y, m, amount)
    await state.clear()
    await message.answer(t("payments.marked", lang=lang, year=y, month=f"{m:02d}", amount=amount))


@router.callback_query(F.data == "pay:history")
async def cb_history(cb: CallbackQuery, user: User, session: AsyncSession) -> None:
    lang = user.lang
    ps = await repo.get_payments(session, user)
    if not ps:
        await cb.message.answer(t("payments.history_empty", lang=lang))
        await cb.answer()
        return
    total = sum(p.amount for p in ps)
    lines = [t("payments.history_row", lang=lang, year=p.year, month=f"{p.month:02d}", amount=p.amount) for p in ps]
    lines.append("")
    lines.append(t("payments.history_total", lang=lang, count=len(ps), total=round(total, 2)))
    await cb.message.answer("\n".join(lines))
    await cb.answer()
