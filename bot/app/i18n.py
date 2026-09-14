"""Простая локализация: RU/LV словари, обращение по ключу.

Использование:
    from app.i18n import t
    t("welcome.title", lang="ru")
    t("welcome.stats", lang="lv", total=9891, lv_pct=1.1)

Отсутствующий ключ → возвращает сам ключ (заметно в UI, легко чинить).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

Lang = Literal["ru", "lv"]

_LOCALES_DIR = Path(__file__).parent / "locales"
_CACHE: dict[str, dict[str, str]] = {}


def _load(lang: Lang) -> dict[str, str]:
    if lang not in _CACHE:
        path = _LOCALES_DIR / f"{lang}.json"
        with path.open(encoding="utf-8") as f:
            _CACHE[lang] = json.load(f)
    return _CACHE[lang]


def t(key: str, lang: Lang = "ru", **params: object) -> str:
    strings = _load(lang)
    value = strings.get(key, key)
    if params:
        try:
            return value.format(**params)
        except (KeyError, IndexError):
            return value
    return value


def available_langs() -> list[Lang]:
    return ["ru", "lv"]


def normalize_lang(raw: str | None) -> Lang:
    """Нормализует произвольную строку в Lang. По умолчанию ru."""
    if raw and raw.lower().startswith("lv"):
        return "lv"
    return "ru"
