"""Dynamic force-subscribe middleware driven by the mandatory_channels table."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from database.db import ChannelRecord, Database
from keyboards.inline import subscription_kb

logger = logging.getLogger(__name__)

SUBSCRIBE_TEXT = (
    "👋 Salom! Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz kerak:"
)
ALLOWED_MEMBER_STATUSES = frozenset(
    {"creator", "administrator", "member", "restricted"}
)


class SubscriptionMiddleware(BaseMiddleware):
    """Blocks private-chat usage until the user joins every required channel."""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user, chat_type, callback = self._extract_context(event)
        if user is None or user.is_bot:
            return await handler(event, data)

        if chat_type != "private":
            return await handler(event, data)

        if callback is not None and callback.data == "check_sub":
            return await handler(event, data)

        try:
            if await self.db.is_admin(user.id):
                return await handler(event, data)
        except Exception:
            logger.exception("Admin holatini tekshirishda xatolik. user_id=%s", user.id)

        try:
            channels = await self.db.get_all_channels()
        except Exception:
            logger.exception("Majburiy kanallar ro'yxatini o'qib bo'lmadi.")
            return await handler(event, data)

        if not channels:
            return await handler(event, data)

        bot: Bot = data["bot"]
        missing = await self._missing_channels(bot, user.id, channels)
        if not missing:
            return await handler(event, data)

        markup = subscription_kb(missing)
        try:
            if callback is not None:
                try:
                    await callback.answer()
                except Exception:
                    pass
                if callback.message:
                    await callback.message.edit_text(SUBSCRIBE_TEXT, reply_markup=markup)
                else:
                    await bot.send_message(user.id, SUBSCRIBE_TEXT, reply_markup=markup)
            elif isinstance(event, Message):
                await event.answer(SUBSCRIBE_TEXT, reply_markup=markup)
        except Exception as exc:
            if "message is not modified" in str(exc).lower():
                return None
            logger.exception("Obuna xabarini yuborishda xatolik. user_id=%s", user.id)
            try:
                await bot.send_message(user.id, SUBSCRIBE_TEXT, reply_markup=markup)
            except Exception:
                logger.exception("Obuna xabarini qayta yuborib bo'lmadi.")
        return None

    @staticmethod
    def _extract_context(
        event: TelegramObject,
    ) -> tuple[Optional[User], Optional[str], Optional[CallbackQuery]]:
        if isinstance(event, Message):
            return event.from_user, event.chat.type if event.chat else None, None
        if isinstance(event, CallbackQuery):
            chat_type = event.message.chat.type if event.message and event.message.chat else "private"
            return event.from_user, chat_type, event
        return None, None, None

    async def _missing_channels(
        self,
        bot: Bot,
        user_id: int,
        channels: list[ChannelRecord],
    ) -> list[ChannelRecord]:
        missing: list[ChannelRecord] = []
        for channel in channels:
            if not await is_user_subscribed(bot, channel.channel_username, user_id):
                missing.append(channel)
        return missing


async def is_user_subscribed(bot: Bot, channel_ref: str, user_id: int) -> bool:
    """Return True when the user is a member of the given channel."""
    chat_id: str | int = channel_ref
    if channel_ref.lstrip("-").isdigit():
        chat_id = int(channel_ref)
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        status = getattr(member, "status", None)
        if status is None:
            return False
        status_value = status.value if hasattr(status, "value") else str(status)
        if status_value in {"left", "kicked"}:
            return False
        return status_value in ALLOWED_MEMBER_STATUSES
    except Exception as exc:
        logger.warning(
            "Obunani tekshirib bo'lmadi. channel=%s user=%s error=%s",
            channel_ref,
            user_id,
            exc,
        )
        return True
