"""Точка входа: aiogram polling + APScheduler."""

from __future__ import annotations

import asyncio
import logging
import os
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from dotenv import load_dotenv

from .handlers import setup_routers
from .middleware import DbSessionMiddleware, UserMiddleware
from .services.reminders import setup_scheduler

log = logging.getLogger(__name__)


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format='{"level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
    )


async def _global_error_handler(event: ErrorEvent) -> None:
    """Логируем ЛЮБУЮ ошибку handler'а с traceback, иначе aiogram молчит."""
    log.error(
        "handler exception: %s\n%s",
        event.exception,
        "".join(traceback.format_exception(event.exception)),
    )


async def main() -> None:
    load_dotenv()
    _configure_logging()

    token = os.environ["BOT_TOKEN"]
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher(storage=MemoryStorage())

    # Raw-update logger: ловит вообще ЛЮБОЙ входящий апдейт до маршрутизации
    from aiogram import BaseMiddleware
    from aiogram.types import Update

    class RawUpdateLog(BaseMiddleware):
        async def __call__(self, handler, event, data):
            try:
                if isinstance(event, Update):
                    kind = "?"
                    for k in ("message", "callback_query", "edited_message"):
                        if getattr(event, k, None):
                            kind = k
                            break
                    log.info("RAW UPDATE id=%s kind=%s", event.update_id, kind)
            except Exception as e:
                log.warning("RawUpdateLog error: %s", e)
            return await handler(event, data)

    dp.update.outer_middleware(RawUpdateLog())

    # Middleware — на update-level, чтобы гарантированно попасть до FSM/handler-resolution
    db_mw = DbSessionMiddleware()
    usr_mw = UserMiddleware()
    for observer in (dp.message, dp.callback_query):
        observer.middleware(db_mw)
        observer.middleware(usr_mw)

    # Глобальный error-handler
    dp.errors.register(_global_error_handler)

    setup_routers(dp)

    scheduler = setup_scheduler(bot)
    scheduler.start()

    log.info("bot starting polling (log_level=%s)", os.getenv("LOG_LEVEL", "INFO"))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
