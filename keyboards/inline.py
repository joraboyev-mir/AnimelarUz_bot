"""Inline keyboard builders for AnimeUz."""

from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import AdminRecord, AnimeCatalogItem, ChannelRecord


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📺 Anime ro'yxati", callback_data="anime_page_0")
    builder.button(text="🔍 Qidirish", callback_data="anime_search")
    builder.adjust(1)
    return builder.as_markup()


def subscription_kb(channels: Sequence[ChannelRecord]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.button(text=f"📢 {channel.channel_title}", url=channel.channel_url)
    builder.button(text="✅ Obunani tasdiqlash", callback_data="check_sub")
    builder.adjust(1)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="admin_cancel")
    return builder.as_markup()


def admin_panel_kb(*, is_super_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Anime qo'shish", callback_data="admin_add_anime")
    builder.button(text="📢 Kanallarni boshqarish", callback_data="admin_channels")
    builder.button(text="👥 Adminlarni boshqarish", callback_data="admin_admins")
    builder.button(text="📊 Statistika", callback_data="admin_stats")
    builder.adjust(1)
    _ = is_super_admin
    return builder.as_markup()


def channels_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Kanal qo'shish", callback_data="channel_add")
    builder.button(text="🗑 Kanalni o'chirish", callback_data="channel_remove_menu")
    builder.button(text="📋 Kanallar ro'yxati", callback_data="channel_list")
    builder.button(text="⬅️ Orqaga", callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()


def channels_delete_kb(channels: Sequence[ChannelRecord]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.button(
            text=f"❌ {channel.channel_title}",
            callback_data=f"channel_del_{channel.id}",
        )
    builder.button(text="⬅️ Orqaga", callback_data="admin_channels")
    builder.adjust(1)
    return builder.as_markup()


def admins_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Adminlar ro'yxati", callback_data="admins_list")
    builder.button(text="➕ Admin qo'shish", callback_data="admin_add_user")
    builder.button(text="❌ Adminni o'chirish", callback_data="admin_remove_user")
    builder.button(text="⬅️ Orqaga", callback_data="admin_back")
    builder.adjust(1)
    return builder.as_markup()


def admins_delete_kb(admins: Sequence[AdminRecord], super_admin_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for admin in admins:
        if admin.telegram_id == super_admin_id:
            continue
        builder.button(
            text=f"❌ {admin.full_name} ({admin.telegram_id})",
            callback_data=f"admin_del_{admin.telegram_id}",
        )
    builder.button(text="⬅️ Orqaga", callback_data="admin_admins")
    builder.adjust(1)
    return builder.as_markup()


def back_to_admin_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Admin panel", callback_data="admin_back")
    return builder.as_markup()


def catalog_kb(
    items: Sequence[AnimeCatalogItem],
    page: int,
    total_pages: int,
    *,
    search: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=f"▶️ {item.title} ({item.available_episodes} qism)",
            callback_data=f"open_anime_{item.sample_id}",
        )
    builder.adjust(1)

    prefix = "search_page_" if search else "anime_page_"
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}{page - 1}")
        )
    if page + 1 < total_pages:
        nav.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}{page + 1}")
        )
    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="main_menu"))
    return builder.as_markup()


def episode_nav_kb(
    anime_id: int,
    current_episode: int,
    total_episodes: int,
    download_url: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"prev_ep_{anime_id}"),
        InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"next_ep_{anime_id}"),
    )
    builder.row(
        InlineKeyboardButton(
            text=f"📺 Qismlar: {current_episode}/{total_episodes}",
            callback_data="episode_info",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📥 Barcha qismlarni yuklab olish",
            url=download_url,
        )
    )
    builder.row(InlineKeyboardButton(text="📺 Anime ro'yxati", callback_data="anime_page_0"))
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Asosiy menyu", callback_data="main_menu")
    return builder.as_markup()


def confirm_post_kb(post_id: str) -> InlineKeyboardMarkup:
    """Admin preview ostida: tasdiqlash yoki bekor qilish tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Kanalga yuborish (Tasdiqlash)",
            callback_data=f"post_confirm_{post_id}",
        ),
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data=f"post_cancel_{post_id}",
        ),
    )
    return builder.as_markup()


def watch_anime_kb(bot_username: str, anime_id: int) -> InlineKeyboardMarkup:
    """Kanalga yuboriladigan post ostidagi 'Tomosha Qilish' tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✨ Tomosha Qilish ✨",
        url=f"https://t.me/{bot_username}?start=watch_{anime_id}",
    )
    return builder.as_markup()

