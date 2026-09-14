"""/admin stats — только ADMIN_CHAT_ID."""

from __future__ import annotations

import os

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import repo
from ..i18n import t

router = Router(name="admin")


def _is_admin(chat_id: int) -> bool:
    admin = os.getenv("ADMIN_CHAT_ID")
    if not admin:
        return False
    try:
        return int(admin) == chat_id
    except ValueError:
        return False


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    if not _is_admin(message.chat.id):
        return
    stats = await repo.admin_stats(session)
    header = t("admin.stats.header", lang="ru")
    body = t("admin.stats.body", lang="ru", **stats)
    await message.answer(f"<b>{header}</b>\n\n{body}", parse_mode="HTML")
