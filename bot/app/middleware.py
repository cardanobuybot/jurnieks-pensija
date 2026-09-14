"""Middleware: DB-сессия + User в data для каждого handler."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from .db import repo
from .db.session import get_sessionmaker


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
        tg_user: TgUser | None = data.get("event_from_user")
        session = data.get("session")
        if tg_user and session:
            user = await repo.get_or_create_user(
                session, tg_id=tg_user.id, tg_username=tg_user.username
            )
            data["user"] = user
            data["lang"] = user.lang
        return await handler(event, data)
