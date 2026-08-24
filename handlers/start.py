"""Public entry handlers: /start, main menu, and subscription verification."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.db import Database
from keyboards.inline import main_menu_kb, subscription_kb
from middlewares.subscription import is_user_subscribed

logger = logging.getLogger(__name__)
router = Router(name="start")

WELCOME_TEXT = (
    "🎌 <b>AnimeUz</b> rasmiy botiga xush kelibsiz!\n\n"
    "Bu yerda sevimli animelaringizni o'zbek tilida tomosha qilishingiz mumkin.\n"
    "Ro'yxatdan anime tanlang yoki qidiruvdan foydalaning."
)
NOT_SUBSCRIBED = "❗️ Hali barcha kanallarga a'zo emassiz. Iltimos, obunani yakunlang."
SUBSCRIBED_OK = "✅ Obuna tasdiqlandi! Endi botdan bemalol foydalanishingiz mumkin."


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    if user is None:
        return
    try:
        await db.upsert_user(
            telegram_id=user.id,
            full_name=user.full_name,
            username=user.username,
        )
    except Exception:
        logger.exception("Foydalanuvchini saqlashda xatolik. user_id=%s", user.id)

    try:
        await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
    except Exception:
        logger.exception("/start javobini yuborishda xatolik. user_id=%s", user.id)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if not callback.message:
        return
    try:
        await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    except Exception:
        try:
            await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
        except Exception:
            logger.exception("Asosiy menyuni ko'rsatishda xatolik.")


@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot, db: Database) -> None:
    user = callback.from_user
    try:
        channels = await db.get_all_channels()
    except Exception:
        logger.exception("Kanallarni o'qishda xatolik.")
        await callback.answer("Texnik xatolik yuz berdi. Keyinroq urinib ko'ring.", show_alert=True)
        return

    missing = False
    for channel in channels:
        if not await is_user_subscribed(bot, channel.channel_username, user.id):
            missing = True
            break

    if missing:
        await callback.answer(NOT_SUBSCRIBED, show_alert=True)
        try:
            if callback.message:
                await callback.message.edit_text(
                    "👋 Salom! Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz kerak:",
                    reply_markup=subscription_kb(channels),
                )
        except Exception:
            logger.debug("Obuna xabarini tahrirlab bo'lmadi (o'zgarishsiz bo'lishi mumkin).")
        return

    try:
        await db.upsert_user(
            telegram_id=user.id,
            full_name=user.full_name,
            username=user.username,
        )
    except Exception:
        logger.exception("Tasdiqlashdan keyin foydalanuvchini saqlab bo'lmadi.")

    await callback.answer(SUBSCRIBED_OK, show_alert=True)
    try:
        if callback.message:
            await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    except Exception:
        if callback.message:
            await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
