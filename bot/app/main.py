"""Точка входа: aiogram polling + APScheduler."""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from .handlers import setup_routers
from .middleware import DbSessionMiddleware, UserMiddleware
from .services.reminders import setup_scheduler


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format='{"level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
    )


async def main() -> None:
    load_dotenv()
    _configure_logging()

    token = os.environ["BOT_TOKEN"]
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())

    # middleware порядок: DB-сессия → User
    db_mw = DbSessionMiddleware()
    usr_mw = UserMiddleware()
    for observer in (dp.message, dp.callback_query):
        observer.middleware(db_mw)
        observer.middleware(usr_mw)

    setup_routers(dp)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    logging.info("bot starting polling")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
