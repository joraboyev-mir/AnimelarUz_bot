"""Public entry handlers: /start, main menu, deep-link watch, and subscription verification."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import MAIN_CHANNEL_ID, MAIN_CHANNEL_USERNAME
from database.db import Database
from keyboards.inline import main_menu_kb, subscription_kb, watch_anime_kb
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


async def _check_main_channel_sub(bot: Bot, user_id: int) -> bool:
    """Foydalanuvchi asosiy kanalga obuna bo'lganligini tekshiradi."""
    channel_ref: str | int
    if MAIN_CHANNEL_USERNAME:
        channel_ref = f"@{MAIN_CHANNEL_USERNAME}" if not MAIN_CHANNEL_USERNAME.startswith("@") else MAIN_CHANNEL_USERNAME
    else:
        channel_ref = MAIN_CHANNEL_ID
    return await is_user_subscribed(bot, str(channel_ref), user_id)


@router.message(CommandStart(deep_link=True, deep_link_encoded=False))
async def cmd_start_deep(message: Message, bot: Bot, db: Database, state: FSMContext) -> None:
    """Deep link orqali kelgan /start ni ushlaydi, masalan: /start watch_42."""
    await state.clear()
    user = message.from_user
    if user is None:
        return

    # Foydalanuvchini saqlash
    try:
        await db.upsert_user(
            telegram_id=user.id,
            full_name=user.full_name,
            username=user.username,
        )
    except Exception:
        logger.exception("Foydalanuvchini saqlashda xatolik. user_id=%s", user.id)

    # Deep link parametrini olish
    args = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else ""

    if args.startswith("watch_"):
        # Anime ID ni ajratamiz
        raw_id = args.removeprefix("watch_")
        try:
            anime_id = int(raw_id)
        except ValueError:
            await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
            return

        # Asosiy kanalga obuna tekshiruvi
        is_subscribed = await _check_main_channel_sub(bot, user.id)

        if not is_subscribed:
            # Asosiy kanalga obuna tugmasi ko'rsatiladi
            channel_url = (
                f"https://t.me/{MAIN_CHANNEL_USERNAME}"
                if MAIN_CHANNEL_USERNAME
                else f"https://t.me/c/{str(MAIN_CHANNEL_ID).replace('-100', '')}"
            )
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="📢 Kanalga a'zo bo'lish", url=channel_url)
            builder.button(text="✅ Obunani tasdiqlash", callback_data=f"check_watch_{anime_id}")
            builder.adjust(1)
            await message.answer(
                "🔒 Videoni tomosha qilish uchun avval kanalimizga a'zo bo'ling:",
                reply_markup=builder.as_markup(),
            )
            return

        # Obuna bor – videoni yuboramiz
        await _send_watch_video(message, bot, db, anime_id)
        return

    # Oddiy /start – asosiy menyu
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


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


async def _send_watch_video(
    target: Message,
    bot: Bot,
    db: Database,
    anime_id: int,
) -> None:
    """Berilgan anime ID bo'yicha birinchi qismni foydalanuvchiga yuboradi."""
    from config import BOT_USERNAME
    try:
        record = await db.get_anime_by_id(anime_id)
        if record is None:
            await target.answer(
                "❌ Anime topilmadi. Ehtimol o'chirib yuborilgan bo'lishi mumkin.",
                reply_markup=main_menu_kb(),
            )
            return
        await bot.send_video(
            chat_id=target.chat.id,
            video=record.file_id,
            caption=f"▶️ <b>{record.title}</b> | {record.current_episode}-qism",
            reply_markup=watch_anime_kb(BOT_USERNAME, anime_id),
        )
    except Exception:
        logger.exception("Watch videosini yuborishda xatolik. anime_id=%s", anime_id)
        await target.answer("Videoni yuborishda xatolik yuz berdi.", reply_markup=main_menu_kb())


# ── Obuna tekshiruvi (watch deep link uchun) ────────────────────────────

@router.callback_query(F.data.startswith("check_watch_"))
async def cb_check_watch_sub(callback: CallbackQuery, bot: Bot, db: Database) -> None:
    """Foydalanuvchi kanalga a'zo bo'lgandan so'ng videoni yuboradi."""
    raw_id = (callback.data or "").removeprefix("check_watch_")
    try:
        anime_id = int(raw_id)
    except ValueError:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    user = callback.from_user
    is_subscribed = await _check_main_channel_sub(bot, user.id)

    if not is_subscribed:
        await callback.answer(NOT_SUBSCRIBED, show_alert=True)
        return

    await callback.answer(SUBSCRIBED_OK, show_alert=True)
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await _send_watch_video(callback.message, bot, db, anime_id)


# ── Asosiy menyu ─────────────────────────────────────────────────────────

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


# ── Umumiy obuna tekshiruvi (majburiy kanallar) ──────────────────────────

@router.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, bot: Bot, db: Database) -> None:
    user = callback.from_user
    try:
        channels = await db.get_all_channels()
    except Exception:
        logger.exception("Kanallarni o'qishda xatolik.")
        try:
            await callback.answer("Texnik xatolik yuz berdi. Keyinroq urinib ko'ring.", show_alert=True)
        except Exception:
            pass
        return

    missing_channels = []
    for channel in channels:
        if not await is_user_subscribed(bot, channel.channel_username, user.id):
            missing_channels.append(channel)

    if missing_channels:
        try:
            await callback.answer(NOT_SUBSCRIBED, show_alert=True)
        except Exception:
            pass
        try:
            if callback.message:
                await callback.message.edit_text(
                    "👋 Salom! Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz kerak:",
                    reply_markup=subscription_kb(missing_channels),
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

    try:
        await callback.answer(SUBSCRIBED_OK, show_alert=True)
    except Exception:
        pass
    try:
        if callback.message:
            await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_kb())
    except Exception:
        if callback.message:
            await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())
