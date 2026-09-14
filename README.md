# jurnieks-pensija

Телеграм-бот для латвийских моряков под иностранным флагом: диагностика соц-страхования и калькулятор добровольных пенсионных взносов через VSAA.

## Что это

~9 900 латвийских моряков ходят под иностранным флагом (только 1,1% под латвийским). За большинство пенсионные взносы в Латвии никто не платит: по регламенту ЕС 883/2004 они страхуются в стране флага, а Мадейра/Кипр/Мальта/Панама/Либерия — обычно фикция. С 01.01.2025 для пенсии по возрасту нужно 20 лет стажа; типичный моряк 40+ имеет 3–7 лет и не знает.

Решение — добровольное присоединение через VSAA. Бот проводит от «а что у меня?» до первого платежа.

## Стек

- Python 3.12, aiogram 3.x, APScheduler, SQLAlchemy 2 + asyncpg (локально SQLite)
- Postgres на Railway, лендинг + калькулятор на Vercel
- Локализация RU/LV
- Расчёты — чистые функции в `bot/app/domain/pension.py`, покрыты pytest

## Структура

```
jurnieks-pensija/
├── bot/
│   ├── app/
│   │   ├── domain/       constants.py, pension.py, diagnosis.py
│   │   ├── handlers/     start, diagnosis, profile, calc, payments, admin
│   │   ├── services/     reminders, letters
│   │   ├── db/           models, repo, migrations
│   │   ├── locales/      ru.json, lv.json
│   │   ├── i18n.py
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   ├── railway.json
│   ├── requirements.txt
│   └── .env.example
├── web/
│   ├── index.html
│   ├── calc.js
│   └── vercel.json
├── .github/workflows/ci.yml
└── README.md
```

## Как запустить локально

```
cd bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # заполнить BOT_TOKEN, ADMIN_CHAT_ID
alembic upgrade head
python -m app.main
```

## Тесты

```
cd bot && pytest -q
```

## Деплой за ≈10 минут

**Предпосылки:** аккаунты на Railway (для бота+postgres) и на Vercel (для лендинга). GitHub-репо уже есть — `github.com/cardanobuybot/jurnieks-pensija`.

### Railway — бот + Postgres

1. **New Project → Deploy from GitHub → cardanobuybot/jurnieks-pensija**. Rootpath: `bot/`. Билдер выберется Dockerfile автоматически.
2. **Add Plugin → Postgres**. Railway создаст `DATABASE_URL` в переменных проекта.
3. В переменные сервиса `bot` добавить:
   - `BOT_TOKEN` — от @BotFather (уже есть — @JurnieksBot)
   - `ADMIN_CHAT_ID` — свой Telegram chat_id (узнать: написать боту `/start` и посмотреть в логах, либо @userinfobot)
   - `LOG_LEVEL=INFO`
   - `DATABASE_URL` — Railway подставит от плагина Postgres (Reference variable)
4. **Deploy**. При старте Dockerfile выполнит `alembic upgrade head` и запустит `python -m app.main`.
5. Смок-проверка: написать боту `/start`, пройти диагностику до прогноза.

### Vercel — лендинг

1. **New Project → Import Git Repository → cardanobuybot/jurnieks-pensija**.
2. **Root Directory: `web`**. Framework preset: **Other** (статические файлы).
3. **Deploy**. Через 30 сек лендинг доступен по `<projectname>.vercel.app`.
4. Опционально: **Domains → добавить свой** (например `jurnieks.lv`).

## Полный чеклист готовности (спека)

- [x] pytest зелёный, все эталоны проходят (21/21 локально + CI)
- [ ] Локально с SQLite: `/start` → диагностика → прогноз за ≤6 нажатий — **проверять после запуска на Railway** (Termux не собирает pydantic-core, локальный runtime aiogram не доступен)
- [x] Оба языка, ключи ru↔lv покрыты полностью (тест `test_all_keys_present_in_both_langs`)
- [x] Ветка А не предлагает добровольные взносы (кнопка «Открыть калькулятор» показывается только для B/C)
- [x] Долг по месяцам считается по годам с правильными ставками (эталонный кейс 31 мес / 5 475,36 €)
- [x] Напоминания в scheduler: day5, dec15, stage_check (через 21д), admin_min_wage_alert 1 декабря
- [x] Dockerfile валиден по синтаксису
- [x] Лендинг открывается, `calc.js` — прямой порт формул из `pension.py`
- [x] Репо на GitHub `cardanobuybot/jurnieks-pensija`, CI зелёный
- [x] README объясняет деплой за ≈10 минут (этот раздел)

## Что сделано (11/11 шагов)

1. Скелет репо, `.gitignore`, README
2. `domain/constants.py` + `pension.py` + 7 эталонных тестов
3. `domain/diagnosis.py` + 6 тестов (ветки A/B/C)
4. `locales/ru.json` + `locales/lv.json` + `i18n.py` + 6 i18n-тестов
5. SQLAlchemy 2 async модели (User/Payment/LvEmploymentPeriod), alembic + первая миграция
6. Все aiogram handlers: start / diagnosis / profile / calc / payments / howto / admin + FSM + middleware
7. APScheduler jobs: day5, dec15, stage_check (21д), admin_min_wage_alert
8. `Dockerfile` (python:3.12-slim), `railway.json`, `.env.example`
9. `web/index.html` + `calc.js` (1:1 порт формул) + `vercel.json`
10. GitHub Actions CI: pytest на push/PR
11. Финальный README (этот раздел)

**Реальный ответ VSAA (сентябрь 2026) учтён:**
- Оплата задним числом разрешена — рабочий debt-калькулятор с учётом уже оплаченных месяцев
- Месяцы у LV-работодателя исключаются только при ПОЛНОМ покрытии (см. `_is_month_fully_covered`)
- Реквизиты счёта VSAA зашиты в `constants.py`
- Генератор строки «назначение платежа» (transliteration LV→ASCII, группировка по годам, лимит 140 символов)
- Письмо в VSAA первым шагом при наличии долга (запрашивает список оплаченных/открытых месяцев)
- Через 3 недели после первой оплаты — пинг «стаж на latvija.lv вырос?»

## TODO / открытые вопросы

- **Локальная валидация runtime** — в Termux нет rust для pydantic-core, поэтому aiogram-часть тестировалась только компиляцией (`python -m compileall`). Первый рабочий прогон — на Railway.
- **`ADMIN_CHAT_ID`** — не задан, узнать после первого `/start` в боте.
- **Обновление минзарплаты:** 15 декабря каждого года — вручную дополнить `MIN_WAGE_BY_YEAR` в `bot/app/domain/constants.py` и синхронизировать в `web/calc.js`. Бот 1 декабря пингает админа если следующего года нет.
- **Тесты FSM хендлеров** — не написаны, полагаемся на domain-тесты + ручной прогон. Можно добавить aiogram TestClient позже.

## Env, которые нужно задать

| Ключ | Где | Пример |
|---|---|---|
| `BOT_TOKEN` | Railway | `1234567890:AAAA…` (уже есть) |
| `DATABASE_URL` | Railway | Reference variable от плагина Postgres |
| `ADMIN_CHAT_ID` | Railway | `123456789` (свой chat_id) |
| `LOG_LEVEL` | Railway | `INFO` |

Локально `.env`:
```
BOT_TOKEN=<from @BotFather>
DATABASE_URL=sqlite+aiosqlite:///./bot.db
ADMIN_CHAT_ID=0
LOG_LEVEL=DEBUG
```

## Дисклеймер

Всё, что бот показывает — информативно. Правила VSAA меняются. Точные цифры — только в VSAA (`iemaksas@vsaa.gov.lv`, тел. 67600631).
