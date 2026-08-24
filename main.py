"""AnimeUz Telegram bot entry point."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from config import BOT_TOKEN, setup_logging, validate_config
from database.db import Database
from handlers import register_handlers
from middlewares.subscription import SubscriptionMiddleware

logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish / Asosiy menyu"),
        BotCommand(command="help", description="Yordam va muammoni adminga yuborish"),
        BotCommand(command="top", description="Eng ommabop animelar reytingi"),
        BotCommand(command="search", description="Anime qidirish"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot buyruqlari o'rnatildi.")
    except Exception:
        logger.exception("Bot buyruqlarini o'rnatishda xatolik.")


async def on_startup(bot: Bot) -> None:
    me = await bot.get_me()
    logger.info("Bot ishga tushdi: @%s (id=%s)", me.username, me.id)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        logger.exception("Webhook ni o'chirishda xatolik.")
    await set_bot_commands(bot)



async def on_shutdown(bot: Bot) -> None:
    logger.info("Bot to'xtatilmoqda...")
    try:
        await bot.session.close()
    except Exception:
        logger.exception("Bot sessiyasini yopishda xatolik.")


async def main() -> None:
    setup_logging()
    validate_config()

    db = Database()
    await db.init()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.workflow_data.update(db=db)

    subscription = SubscriptionMiddleware(db)
    dp.message.middleware(subscription)
    dp.callback_query.middleware(subscription)

    register_handlers(dp)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    @dp.error()
    async def on_error(event: ErrorEvent) -> None:
        logger.exception("Ushlanmagan xatolik: %s", event.exception)

    logger.info("Polling boshlandi.")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Bot klaviatura orqali to'xtatildi.")
