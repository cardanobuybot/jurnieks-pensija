"""/howto — инструкция и генератор назначения платежа. /letter — письмо VSAA."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..domain.constants import (
    PAYMENT_PURPOSE_MAX_LEN,
    VSAA_CONTRIBUTIONS_EMAIL,
    VSAA_CONTRIBUTIONS_PHONE,
    VSAA_GENERAL_PHONE,
)
from ..domain.pension import payment_purpose
from ..i18n import t

router = Router(name="howto")


class PurposeFSM(StatesGroup):
    name = State()
    kods = State()


@router.message(Command("howto"))
async def cmd_howto(message: Message, user: User) -> None:
    lang = user.lang
    body = "\n\n".join([
        f"<b>{t('howto.title', lang=lang)}</b>",
        t("howto.bank_details", lang=lang),
        t("howto.steps", lang=lang, vsaa_email=VSAA_CONTRIBUTIONS_EMAIL, year="…", month_lv="…", name="…", code="…"),
        t("howto.contacts", lang=lang, vsaa_email=VSAA_CONTRIBUTIONS_EMAIL, phone1=VSAA_CONTRIBUTIONS_PHONE, phone2=VSAA_GENERAL_PHONE),
    ])
    await message.answer(body, parse_mode="HTML")


@router.message(Command("purpose"))
async def cmd_purpose(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    lang = user.lang
    paid = await repo.get_payments(session, user)
    if not paid:
        await message.answer(t("payments.history_empty", lang=lang))
        return
    await state.update_data(months=[(p.year, p.month) for p in paid])
    await state.set_state(PurposeFSM.name)
    await message.answer(t("howto.purpose_generator_ask_name", lang=lang))


@router.message(PurposeFSM.name, F.text)
async def purpose_name(message: Message, user: User, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(PurposeFSM.kods)
    await message.answer(t("howto.purpose_generator_ask_code", lang=user.lang))


@router.message(PurposeFSM.kods, F.text)
async def purpose_kods(message: Message, user: User, state: FSMContext) -> None:
    lang = user.lang
    data = await state.get_data()
    p = payment_purpose(
        months=data["months"],
        full_name=data["name"],
        personas_kods=message.text.strip(),
        base_monthly=user.monthly_base,
    )
    await state.clear()
    if not p.fits_bank_field:
        await message.answer(t("howto.purpose_too_long", lang=lang, length=p.length, max_len=PAYMENT_PURPOSE_MAX_LEN))
        return
    await message.answer(
        t("howto.purpose_result", lang=lang, text=p.text, length=p.length, max_len=PAYMENT_PURPOSE_MAX_LEN),
        parse_mode="HTML",
    )


@router.message(Command("letter"))
async def cmd_letter(message: Message, user: User) -> None:
    lang = user.lang
    from datetime import date as _date
    subj = t("letter.subject", lang=lang)
    body = t("letter.body", lang=lang, name="___", code="___", year=_date.today().year)
    intro = t(
        "letter.intro_hint",
        lang=lang,
        phone1=VSAA_CONTRIBUTIONS_PHONE,
        phone2=VSAA_GENERAL_PHONE,
    )
    # Письмо — одним сообщением, «Угостить кофе» — отдельным ниже.
    await message.answer(
        f"{intro}\n\n"
        f"<b>To:</b> {VSAA_CONTRIBUTIONS_EMAIL}\n"
        f"<b>Subject:</b> {subj}\n\n"
        f"<code>{body}</code>"
    )
    tip_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn.tip_coffee", lang=lang), url="https://revolut.me/sirjevspavels"),
    ]])
    await message.answer(t("alt.tip_prompt", lang=lang), reply_markup=tip_kb)


@router.callback_query(F.data == "letter:show")
async def cb_letter(cb: CallbackQuery, user: User) -> None:
    await cmd_letter(cb.message, user)
    await cb.answer()
