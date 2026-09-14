"""/start, /lang, /help, /stop."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..db.models import User
from ..domain.constants import SEAFARERS_STATS
from ..i18n import t

log = logging.getLogger(__name__)
router = Router(name="start")


def _lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇱🇻 Latviešu", callback_data="lang:lv"),
            ]
        ]
    )


def _start_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn.start_diagnosis", lang=lang), callback_data="diag:start")]
        ]
    )


@router.message(Command("start"))
async def cmd_start(message: Message, user: User, session: AsyncSession) -> None:
    log.info("cmd_start: user_id=%s tg_id=%s branch=%s lang=%s", user.id, user.tg_id, user.branch, user.lang)
    # Первый /start (нет диагноза и не менял язык): показываем язык.
    if user.branch is None:
        await message.answer(t("lang.prompt"), reply_markup=_lang_kb())
        return
    await _send_welcome(message, user.lang)


@router.callback_query(F.data.startswith("lang:"))
async def choose_lang(cb: CallbackQuery, user: User, session: AsyncSession) -> None:
    _, lang = cb.data.split(":", 1)
    await repo.set_lang(session, user, lang)
    await cb.message.answer(t("lang.switched", lang=user.lang))
    await _send_welcome(cb.message, user.lang)
    await cb.answer()


async def _send_welcome(message: Message, lang: str) -> None:
    stats = SEAFARERS_STATS.get(max(SEAFARERS_STATS.keys()))
    text = (
        f"<b>{t('welcome.title', lang=lang)}</b>\n\n"
        f"{t('welcome.stats', lang=lang, total=stats['total'], lv_pct=stats['lv_flag_pct'])}\n\n"
        f"<i>{t('welcome.consent', lang=lang)}</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=_start_kb(lang))


@router.message(Command("lang"))
async def cmd_lang(message: Message) -> None:
    await message.answer(t("lang.prompt"), reply_markup=_lang_kb())


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    lang = user.lang
    lines = [
        "/start — начать заново",
        "/lang — сменить язык",
        "/calc — калькулятор пенсии",
        "/payments — оплаты",
        "/howto — как платить",
        "/letter — письмо в VSAA",
        "/stop — отключить напоминания",
        "/help — эта справка",
    ]
    if lang == "lv":
        lines = [
            "/start — sākt no jauna",
            "/lang — mainīt valodu",
            "/calc — pensijas kalkulators",
            "/payments — maksājumi",
            "/howto — kā maksāt",
            "/letter — vēstule VSAA",
            "/stop — atslēgt atgādinājumus",
            "/help — šī palīdzība",
        ]
    await message.answer("\n".join(lines))


@router.message(Command("stop"))
async def cmd_stop(message: Message, user: User, session: AsyncSession) -> None:
    user.reminders_enabled = False
    lang = user.lang
    msg = "Напоминания отключены. /start чтобы включить." if lang == "ru" else "Atgādinājumi atslēgti. /start lai ieslēgtu atpakaļ."
    await message.answer(msg)
