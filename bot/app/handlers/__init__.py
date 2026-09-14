from aiogram import Dispatcher

from . import admin, calc, diagnosis, howto, payments, profile, start


def setup_routers(dp: Dispatcher) -> None:
    dp.include_router(start.router)
    dp.include_router(diagnosis.router)
    dp.include_router(profile.router)
    dp.include_router(calc.router)
    dp.include_router(payments.router)
    dp.include_router(howto.router)
    dp.include_router(admin.router)
