"""Handler routers package."""

from aiogram import Dispatcher

from handlers.admin import router as admin_router
from handlers.anime import router as anime_router
from handlers.start import router as start_router


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(anime_router)
