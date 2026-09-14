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

## Деплой

См. финальный раздел этого README (заполняется на шаге 11).

## Дисклеймер

Всё, что бот показывает — информативно. Правила VSAA меняются. Точные цифры — только в VSAA (`iemaksas@vsaa.gov.lv`, тел. 67600631).
