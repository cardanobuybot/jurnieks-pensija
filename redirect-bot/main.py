"""Мини-бот на старом токене @jurnieks_bot. Любое сообщение → редирект на @JurnieksBot."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

log = logging.getLogger(__name__)
router = Router(name="redirect")

TEXT_RU = (
    "👋 Этот бот <b>переехал</b>.\n\n"
    "Продолжай в новом:\n"
    "👉 @JurnieksBot"
)
TEXT_LV = (
    "👋 Šis bots ir <b>pārcelts</b>.\n\n"
    "Turpini jaunajā:\n"
    "👉 @JurnieksBot"
)

KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="➡️ @JurnieksBot", url="https://t.me/JurnieksBot")
]])


@router.message(F.text)
async def any_message(message: Message) -> None:
    lang_code = (message.from_user.language_code or "").lower() if message.from_user else ""
    is_ru = lang_code.startswith(("ru", "be", "uk", "kk", "ky"))
    await message.answer(TEXT_RU if is_ru else TEXT_LV, reply_markup=KB)


@router.message()
async def any_other(message: Message) -> None:
    await message.answer(TEXT_LV, reply_markup=KB)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    token = os.environ["BOT_TOKEN"]
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)
    log.info("redirect bot polling")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
