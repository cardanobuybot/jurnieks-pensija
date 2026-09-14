"""Middleware: DB-сессия + User в data для каждого handler."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from .db import repo
from .db.session import get_sessionmaker

log = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with get_sessionmaker()() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class UserMiddleware(BaseMiddleware):
    """Достаёт (или создаёт) User по event.from_user, кладёт в data['user']."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # В aiogram 3 у Message/CallbackQuery есть from_user напрямую
        tg_user = getattr(event, "from_user", None) or data.get("event_from_user")
        session = data.get("session")
        if tg_user is None or session is None:
            log.warning(
                "UserMiddleware skipped: tg_user=%s session=%s event=%s",
                tg_user, session, type(event).__name__,
            )
            return await handler(event, data)
        user = await repo.get_or_create_user(
            session, tg_id=tg_user.id, tg_username=tg_user.username
        )
        data["user"] = user
        data["lang"] = user.lang
        log.debug("UserMiddleware: user=%s lang=%s branch=%s", user.id, user.lang, user.branch)
        return await handler(event, data)
