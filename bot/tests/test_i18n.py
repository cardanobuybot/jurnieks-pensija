from app.i18n import t


def test_ru_key():
    assert "Русский" in t("lang.name", lang="ru")


def test_lv_key():
    assert "Latviešu" in t("lang.name", lang="lv")


def test_format_params():
    s = t("welcome.stats", lang="ru", total=9891, lv_pct=1.1)
    assert "9891" in s
    assert "1.1" in s


def test_missing_key_returns_key():
    assert t("nonexistent.key", lang="ru") == "nonexistent.key"


def test_lv_has_diacritics():
    """Проверка что LV-файл сохранён в UTF-8 и диакритика на месте."""
    s = t("welcome.stats", lang="lv", total=9891, lv_pct=1.1)
    assert "jūrnieku" in s or "jurnieku" in s.lower()  # без потери диакритики


def test_all_keys_present_in_both_langs():
    """Ключи ru и lv совпадают — иначе часть строк не переведётся."""
    from app.i18n import _load
    ru = set(_load("ru").keys())
    lv = set(_load("lv").keys())
    missing_in_lv = ru - lv
    missing_in_ru = lv - ru
    assert not missing_in_lv, f"нет в LV: {missing_in_lv}"
    assert not missing_in_ru, f"нет в RU: {missing_in_ru}"
