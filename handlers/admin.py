"""Admin panel: anime upload FSM, mandatory channels, and admin management."""

from __future__ import annotations

import html
import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from config import MAIN_CHANNEL_ID, SUPER_ADMIN_ID
from database.db import Database
from keyboards.inline import (
    admin_panel_kb,
    admins_delete_kb,
    admins_menu_kb,
    back_to_admin_kb,
    cancel_kb,
    channels_delete_kb,
    channels_menu_kb,
)
from states.admin_states import AddAnimeSG, AdminManageSG, ChannelSG

logger = logging.getLogger(__name__)
router = Router(name="admin")

CHANNEL_CAPTION = (
    "▶️ Anime: {title}\n"
    "[🎬] Qismi: {current_episode}/{total_episodes}\n"
    "[🎙] Ovoz berdi: AnimeUz Jamoasi\n"
    "[💯] Hashtag: #{hashtag}\n"
    "[📌] Kanal: @animeuz_rasmiy_bot"
)


def _is_super(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID


async def _ensure_admin(user: Optional[User], db: Database) -> bool:
    if user is None:
        return False
    try:
        return await db.is_admin(user.id)
    except Exception:
        logger.exception("Admin huquqini tekshirishda xatolik. user_id=%s", user.id)
        return _is_super(user.id)


def _panel_text() -> str:
    return (
        "🛠 <b>Admin panel</b>\n\n"
        "Kerakli bo'limni tanlang. Anime qo'shish, majburiy obuna kanallarini "
        "va administratorlarni shu yerdan boshqarasiz."
    )


async def _show_panel(target: Message | CallbackQuery, db: Database) -> None:
    user = target.from_user
    if user is None:
        return
    markup = admin_panel_kb(is_super_admin=_is_super(user.id))
    if isinstance(target, CallbackQuery):
        await target.answer()
        if target.message:
            try:
                await target.message.edit_text(_panel_text(), reply_markup=markup)
                return
            except TelegramAPIError:
                await target.message.answer(_panel_text(), reply_markup=markup)
                return
    else:
        await target.answer(_panel_text(), reply_markup=markup)


@router.message(Command("admin"))
async def cmd_admin(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    if not await _ensure_admin(message.from_user, db):
        await message.answer("⛔️ Bu buyruq faqat administratorlar uchun.")
        return
    await _show_panel(message, db)


@router.callback_query(F.data == "admin_back")
async def cb_admin_back(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.clear()
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await _show_panel(callback, db)


@router.callback_query(F.data == "admin_cancel")
async def cb_admin_cancel(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.clear()
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("Bekor qilindi.")
        return
    await callback.answer("Amal bekor qilindi.")
    await _show_panel(callback, db)


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, db: Database) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    try:
        stats = await db.get_stats()
        text = (
            "📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{stats['users']}</b>\n"
            f"🎌 Anime soni: <b>{stats['anime']}</b>\n"
            f"🎞 Qismlar: <b>{stats['episodes']}</b>\n"
            f"👁 Ko'rishlar: <b>{stats['views']}</b>\n"
            f"📢 Majburiy kanallar: <b>{stats['channels']}</b>\n"
            f"🛡 Adminlar: <b>{stats['admins']}</b>"
        )
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(text, reply_markup=back_to_admin_kb())
    except Exception:
        logger.exception("Statistikani yig'ishda xatolik.")
        await callback.answer("Statistikani olishda xatolik yuz berdi.", show_alert=True)


# ── Anime FSM ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_add_anime")
async def cb_add_anime(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AddAnimeSG.title)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "➕ <b>Anime qo'shish</b>\n\nAnime nomini yuboring:",
            reply_markup=cancel_kb(),
        )


@router.message(StateFilter(AddAnimeSG.title), F.text)
async def anime_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("Anime nomi juda qisqa. Qaytadan yuboring:", reply_markup=cancel_kb())
        return
    await state.update_data(title=title)
    await state.set_state(AddAnimeSG.current_episode)
    await message.answer(
        f"✅ Nom: <b>{html.escape(title)}</b>\n\nHozirgi qism raqamini yuboring (masalan, 1):",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(AddAnimeSG.current_episode), F.text)
async def anime_current_episode(message: Message, state: FSMContext) -> None:
    try:
        current = int((message.text or "").strip())
        if current < 1:
            raise ValueError
    except ValueError:
        await message.answer("Qism raqami musbat butun son bo'lishi kerak. Qaytadan yuboring:", reply_markup=cancel_kb())
        return
    await state.update_data(current_episode=current)
    await state.set_state(AddAnimeSG.total_episodes)
    await message.answer(
        f"✅ Joriy qism: <b>{current}</b>\n\nJami qismlar sonini yuboring:",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(AddAnimeSG.total_episodes), F.text)
async def anime_total_episodes(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        total = int((message.text or "").strip())
        if total < 1:
            raise ValueError
        if total < int(data.get("current_episode", 1)):
            await message.answer(
                "Jami qismlar soni joriy qismdan kichik bo'lishi mumkin emas. Qaytadan yuboring:",
                reply_markup=cancel_kb(),
            )
            return
    except ValueError:
        await message.answer("Jami qismlar musbat butun son bo'lishi kerak. Qaytadan yuboring:", reply_markup=cancel_kb())
        return
    await state.update_data(total_episodes=total)
    await state.set_state(AddAnimeSG.hashtag)
    await message.answer(
        f"✅ Jami qismlar: <b>{total}</b>\n\nHashtag yuboring (# belgisiz, masalan: <code>naruto</code>):",
        reply_markup=cancel_kb(),
    )


@router.message(StateFilter(AddAnimeSG.hashtag), F.text)
async def anime_hashtag(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(" ", "")
    hashtag = raw.lstrip("#")
    if len(hashtag) < 2:
        await message.answer("Hashtag juda qisqa. Qaytadan yuboring:", reply_markup=cancel_kb())
        return
    await state.update_data(hashtag=hashtag)
    await state.set_state(AddAnimeSG.video)
    await message.answer(
        f"✅ Hashtag: <b>#{html.escape(hashtag)}</b>\n\n"
        "Videoni yuboring yoki asosiy kanaldan forward qiling. "
        "Bot <code>file_id</code> ni avtomatik oladi.",
        reply_markup=cancel_kb(),
    )


def _extract_file_id(message: Message) -> Optional[str]:
    if message.video:
        return message.video.file_id
    if message.document and message.document.mime_type and message.document.mime_type.startswith("video/"):
        return message.document.file_id
    if message.animation:
        return message.animation.file_id
    return None


@router.message(StateFilter(AddAnimeSG.video))
async def anime_video(message: Message, bot: Bot, db: Database, state: FSMContext) -> None:
    file_id = _extract_file_id(message)
    if not file_id:
        await message.answer(
            "Video topilmadi. Iltimos, video fayl yuboring yoki forward qiling:",
            reply_markup=cancel_kb(),
        )
        return

    data = await state.get_data()
    title = str(data.get("title", "")).strip()
    current_episode = int(data.get("current_episode", 1))
    total_episodes = int(data.get("total_episodes", 1))
    hashtag = str(data.get("hashtag", "")).strip()
    caption = CHANNEL_CAPTION.format(
        title=title,
        current_episode=current_episode,
        total_episodes=total_episodes,
        hashtag=hashtag,
    )

    channel_ok = False
    try:
        await bot.send_video(
            chat_id=MAIN_CHANNEL_ID,
            video=file_id,
            caption=caption,
        )
        channel_ok = True
    except TelegramAPIError as exc:
        logger.exception("Asosiy kanalga video yuborilmadi: %s", exc)
        await message.answer(
            "⚠️ Videoni asosiy kanalga yuborib bo'lmadi. "
            "Bot kanalda admin ekanligini va MAIN_CHANNEL_ID to'g'riligini tekshiring.\n"
            "Qism baribir bazaga saqlanadi."
        )

    try:
        anime_id = await db.add_anime(
            title=title,
            current_episode=current_episode,
            total_episodes=total_episodes,
            file_id=file_id,
            hashtag=hashtag,
        )
    except Exception:
        logger.exception("Anime ni bazaga yozishda xatolik.")
        await message.answer("❌ Bazaga yozishda xatolik. Qaytadan urinib ko'ring.", reply_markup=cancel_kb())
        return

    await state.clear()
    channel_line = "✅ Asosiy kanalga yuborildi." if channel_ok else "⚠️ Kanalga yuborilmadi."
    await message.answer(
        "🎉 <b>Anime qismi saqlandi!</b>\n\n"
        f"🆔 ID: <code>{anime_id}</code>\n"
        f"▶️ Nomi: <b>{html.escape(title)}</b>\n"
        f"🎬 Qism: <b>{current_episode}/{total_episodes}</b>\n"
        f"#️⃣ Hashtag: <b>#{html.escape(hashtag)}</b>\n"
        f"{channel_line}",
        reply_markup=back_to_admin_kb(),
    )


# ── Channels ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_channels")
async def cb_channels_menu(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "📢 <b>Majburiy obuna kanallari</b>\n\n"
            "Foydalanuvchilar botdan foydalanishidan oldin shu kanallarga a'zo bo'lishi shart.",
            reply_markup=channels_menu_kb(),
        )


@router.callback_query(F.data == "channel_list")
async def cb_channel_list(callback: CallbackQuery, db: Database) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    channels = await db.get_all_channels()
    if not channels:
        text = "Hozircha majburiy kanal qo'shilmagan."
    else:
        lines = ["📋 <b>Majburiy kanallar:</b>\n"]
        for idx, channel in enumerate(channels, start=1):
            lines.append(
                f"{idx}. <b>{html.escape(channel.channel_title)}</b>\n"
                f"   {html.escape(channel.channel_username)}\n"
                f"   {html.escape(channel.channel_url)}"
            )
        text = "\n".join(lines)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=channels_menu_kb())


@router.callback_query(F.data == "channel_add")
async def cb_channel_add(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(ChannelSG.add_channel)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "➕ <b>Kanal qo'shish</b>\n\n"
            "Kanal username ini yuboring (<code>@kanal</code>) yoki kanal ID sini "
            "(<code>-100...</code>). Bot ushbu kanalda admin bo'lishi shart.",
            reply_markup=cancel_kb(),
        )


@router.message(StateFilter(ChannelSG.add_channel), F.text)
async def channel_add_process(message: Message, bot: Bot, db: Database, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("Kanal username yoki ID yuboring:", reply_markup=cancel_kb())
        return

    chat_ref: str | int = raw
    numeric = raw.lstrip("-")
    if numeric.isdigit():
        chat_ref = int(raw)
    elif not raw.startswith("@"):
        chat_ref = f"@{raw}"

    try:
        chat = await bot.get_chat(chat_ref)
    except TelegramAPIError as exc:
        logger.warning("Kanal topilmadi: %s (%s)", raw, exc)
        await message.answer(
            "❌ Kanal topilmadi. Username/ID ni tekshiring va botni kanalga admin qiling.",
            reply_markup=cancel_kb(),
        )
        return

    username = f"@{chat.username}" if chat.username else str(chat.id)
    title = chat.title or chat.username or str(chat.id)
    url = f"https://t.me/{chat.username}" if chat.username else ""
    if not url:
        try:
            invite = await bot.create_chat_invite_link(chat.id)
            url = invite.invite_link
        except TelegramAPIError:
            url = f"https://t.me/c/{str(chat.id).replace('-100', '')}"

    try:
        await db.add_channel(username=username, title=title, url=url)
    except Exception:
        logger.exception("Kanalni bazaga yozishda xatolik.")
        await message.answer("❌ Bazaga yozishda xatolik.", reply_markup=cancel_kb())
        return

    await state.clear()
    await message.answer(
        f"✅ Kanal qo'shildi: <b>{html.escape(title)}</b>\n{html.escape(username)}",
        reply_markup=channels_menu_kb(),
    )


@router.callback_query(F.data == "channel_remove_menu")
async def cb_channel_remove_menu(callback: CallbackQuery, db: Database) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    channels = await db.get_all_channels()
    await callback.answer()
    if not channels:
        if callback.message:
            await callback.message.edit_text(
                "O'chirish uchun kanal yo'q.",
                reply_markup=channels_menu_kb(),
            )
        return
    if callback.message:
        await callback.message.edit_text(
            "🗑 O'chirmoqchi bo'lgan kanalni tanlang:",
            reply_markup=channels_delete_kb(channels),
        )


@router.callback_query(F.data.startswith("channel_del_"))
async def cb_channel_delete(callback: CallbackQuery, db: Database) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    try:
        channel_id = int((callback.data or "").rsplit("_", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return
    try:
        await db.remove_channel(channel_id)
    except Exception:
        logger.exception("Kanalni o'chirishda xatolik.")
        await callback.answer("O'chirishda xatolik.", show_alert=True)
        return
    await callback.answer("Kanal o'chirildi.")
    channels = await db.get_all_channels()
    if callback.message:
        if channels:
            await callback.message.edit_text(
                "🗑 Yana o'chirmoqchi bo'lgan kanalni tanlang:",
                reply_markup=channels_delete_kb(channels),
            )
        else:
            await callback.message.edit_text(
                "Majburiy kanallar ro'yxati bo'sh.",
                reply_markup=channels_menu_kb(),
            )


# ── Admins ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_admins")
async def cb_admins_menu(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "👥 <b>Adminlarni boshqarish</b>\n\n"
            "Yangi admin qo'shish yoki mavjud adminni olib tashlash mumkin. "
            "Super adminni o'chirish mumkin emas.",
            reply_markup=admins_menu_kb(),
        )


@router.callback_query(F.data == "admins_list")
async def cb_admins_list(callback: CallbackQuery, db: Database) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    admins = await db.get_all_admins()
    lines = ["📋 <b>Hozirgi adminlar:</b>\n"]
    for admin in admins:
        badge = " 👑 Super" if admin.telegram_id == SUPER_ADMIN_ID else ""
        uname = html.escape(admin.full_name)
        lines.append(f"• {uname} — <code>{admin.telegram_id}</code>{badge}")
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("\n".join(lines), reply_markup=admins_menu_kb())


@router.callback_query(F.data == "admin_add_user")
async def cb_admin_add_user(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminManageSG.add_admin)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "➕ <b>Admin qo'shish</b>\n\n"
            "Foydalanuvchining Telegram ID raqamini yuboring.\n"
            "ID ni @userinfobot orqali olish mumkin.",
            reply_markup=cancel_kb(),
        )


@router.message(StateFilter(AdminManageSG.add_admin), F.text)
async def admin_add_process(message: Message, bot: Bot, db: Database, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        telegram_id = int(raw)
        if telegram_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Telegram ID musbat butun son bo'lishi kerak. Qaytadan yuboring:", reply_markup=cancel_kb())
        return

    full_name = f"Admin {telegram_id}"
    try:
        chat = await bot.get_chat(telegram_id)
        full_name = chat.full_name or chat.username or full_name
    except TelegramAPIError:
        logger.info("Admin ismini olish imkoni bo'lmadi, ID saqlanadi: %s", telegram_id)

    try:
        await db.add_admin(telegram_id=telegram_id, full_name=full_name)
    except Exception:
        logger.exception("Adminni bazaga yozishda xatolik.")
        await message.answer("❌ Bazaga yozishda xatolik.", reply_markup=cancel_kb())
        return

    await state.clear()
    await message.answer(
        f"✅ Admin qo'shildi: <b>{html.escape(full_name)}</b>\nID: <code>{telegram_id}</code>",
        reply_markup=admins_menu_kb(),
    )


@router.callback_query(F.data == "admin_remove_user")
async def cb_admin_remove_user(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    await state.set_state(AdminManageSG.remove_admin)
    admins = await db.get_all_admins()
    removable = [a for a in admins if a.telegram_id != SUPER_ADMIN_ID]
    await callback.answer()
    if callback.message:
        if not removable:
            await callback.message.edit_text(
                "O'chirish mumkin bo'lgan admin yo'q (super admin o'chirilmaydi).",
                reply_markup=admins_menu_kb(),
            )
            await state.clear()
            return
        await callback.message.edit_text(
            "❌ O'chirmoqchi bo'lgan adminni tanlang yoki Telegram ID yuboring:",
            reply_markup=admins_delete_kb(admins, SUPER_ADMIN_ID),
        )


@router.callback_query(F.data.startswith("admin_del_"))
async def cb_admin_delete(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    if not await _ensure_admin(callback.from_user, db):
        await callback.answer("⛔️ Ruxsat yo'q.", show_alert=True)
        return
    try:
        telegram_id = int((callback.data or "").rsplit("_", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return
    if telegram_id == SUPER_ADMIN_ID:
        await callback.answer("Super adminni o'chirish mumkin emas.", show_alert=True)
        return
    ok = await db.remove_admin(telegram_id)
    await state.clear()
    if not ok:
        await callback.answer("O'chirib bo'lmadi.", show_alert=True)
        return
    await callback.answer("Admin o'chirildi.")
    admins = await db.get_all_admins()
    if callback.message:
        await callback.message.edit_text(
            "✅ Admin o'chirildi. Yana o'chirish uchun tanlang:",
            reply_markup=admins_delete_kb(admins, SUPER_ADMIN_ID),
        )


@router.message(StateFilter(AdminManageSG.remove_admin), F.text)
async def admin_remove_by_id(message: Message, db: Database, state: FSMContext) -> None:
    try:
        telegram_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Telegram ID ni to'g'ri yuboring:", reply_markup=cancel_kb())
        return
    if telegram_id == SUPER_ADMIN_ID:
        await message.answer("Super adminni o'chirish mumkin emas.", reply_markup=admins_menu_kb())
        await state.clear()
        return
    ok = await db.remove_admin(telegram_id)
    await state.clear()
    if ok:
        await message.answer(f"✅ Admin o'chirildi: <code>{telegram_id}</code>", reply_markup=admins_menu_kb())
    else:
        await message.answer("Admin topilmadi yoki o'chirib bo'lmadi.", reply_markup=admins_menu_kb())
