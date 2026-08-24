"""Anime catalog, episode navigation, and file_id delivery."""

from __future__ import annotations

import html
import logging
import math
from typing import Optional
from urllib.parse import quote

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaVideo, Message

from config import MAIN_CHANNEL_ID, MAIN_CHANNEL_USERNAME, PAGE_SIZE
from database.db import AnimeRecord, Database
from keyboards.inline import back_to_menu_kb, catalog_kb, episode_nav_kb, main_menu_kb
from states.admin_states import SearchSG

logger = logging.getLogger(__name__)
router = Router(name="anime")

_channel_username_cache: Optional[str] = None


async def resolve_channel_username(bot: Bot) -> str:
    global _channel_username_cache
    if MAIN_CHANNEL_USERNAME:
        return MAIN_CHANNEL_USERNAME
    if _channel_username_cache:
        return _channel_username_cache
    try:
        chat = await bot.get_chat(MAIN_CHANNEL_ID)
        if chat.username:
            _channel_username_cache = chat.username
            return chat.username
    except TelegramAPIError as exc:
        logger.warning("Asosiy kanal username olinmadi: %s", exc)
    return ""


def build_download_url(channel_username: str, hashtag: str) -> str:
    tag = hashtag.lstrip("#")
    if channel_username:
        return f"https://t.me/{channel_username}?q={quote('#' + tag)}"
    return f"https://t.me/anime_uz_rasmiy_kanal"


def episode_caption(item: AnimeRecord) -> str:
    return f"▶️ {html.escape(item.title)} | {item.current_episode}-qism"


async def send_episode(
    bot: Bot,
    chat_id: int,
    item: AnimeRecord,
    db: Database,
    *,
    edit_message: Optional[Message] = None,
) -> None:
    try:
        await db.increment_views(item.id)
    except Exception:
        logger.exception("Ko'rishlar sonini oshirishda xatolik. id=%s", item.id)

    username = await resolve_channel_username(bot)
    markup = episode_nav_kb(
        anime_id=item.id,
        current_episode=item.current_episode,
        total_episodes=item.total_episodes,
        download_url=build_download_url(username, item.hashtag),
    )
    caption = episode_caption(item)

    try:
        if edit_message is not None:
            await edit_message.edit_media(
                media=InputMediaVideo(media=item.file_id, caption=caption),
                reply_markup=markup,
            )
            return
    except TelegramAPIError:
        logger.debug("Videoni tahrirlab bo'lmadi, yangi xabar yuboriladi. id=%s", item.id)

    await bot.send_video(
        chat_id=chat_id,
        video=item.file_id,
        caption=caption,
        reply_markup=markup,
    )


async def render_catalog(
    callback: CallbackQuery,
    db: Database,
    page: int,
    *,
    query: Optional[str] = None,
) -> None:
    total = await db.count_unique_anime(query)
    if total == 0:
        text = (
            "🔍 Hech narsa topilmadi. Boshqa nom bilan qidirib ko'ring."
            if query
            else "Hozircha anime qo'shilmagan. Tez orada yangilanadi."
        )
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(text, reply_markup=back_to_menu_kb())
        return

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    items = await db.get_catalog_page(page, PAGE_SIZE, query)
    header = "🔍 <b>Qidiruv natijalari</b>" if query else "📺 <b>Anime ro'yxati</b>"
    if query:
        header += f"\nSo'rov: <code>{html.escape(query)}</code>"
    text = (
        f"{header}\n\n"
        f"Sahifa: <b>{page + 1}/{total_pages}</b> • Jami: <b>{total}</b>\n"
        "Tomosha qilish uchun animeni tanlang."
    )
    await callback.answer()
    if callback.message:
        try:
            await callback.message.edit_text(
                text,
                reply_markup=catalog_kb(items, page, total_pages, search=bool(query)),
            )
        except TelegramAPIError:
            await callback.message.answer(
                text,
                reply_markup=catalog_kb(items, page, total_pages, search=bool(query)),
            )


@router.callback_query(F.data.startswith("anime_page_"))
async def cb_anime_page(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.clear()
    try:
        page = int((callback.data or "").rsplit("_", maxsplit=1)[-1])
    except ValueError:
        page = 0
    try:
        await render_catalog(callback, db, page)
    except Exception:
        logger.exception("Anime ro'yxatini ko'rsatishda xatolik.")
        await callback.answer("Ro'yxatni yuklab bo'lmadi.", show_alert=True)


@router.callback_query(F.data.startswith("search_page_"))
async def cb_search_page(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    query = str(data.get("search_query", "")).strip()
    try:
        page = int((callback.data or "").rsplit("_", maxsplit=1)[-1])
    except ValueError:
        page = 0
    try:
        await render_catalog(callback, db, page, query=query or None)
    except Exception:
        logger.exception("Qidiruv sahifasini ko'rsatishda xatolik.")
        await callback.answer("Qidiruvni yuklab bo'lmadi.", show_alert=True)


@router.callback_query(F.data == "anime_search")
async def cb_anime_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchSG.query)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "🔍 <b>Qidirish</b>\n\nAnime nomi yoki hashtag yuboring:",
            reply_markup=back_to_menu_kb(),
        )


@router.message(StateFilter(SearchSG.query), F.text)
async def search_query(message: Message, db: Database, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Qidiruv so'rovi juda qisqa. Kamida 2 ta belgi yuboring.")
        return
    await state.update_data(search_query=query)
    try:
        total = await db.count_unique_anime(query)
        if total == 0:
            await message.answer(
                "🔍 Hech narsa topilmadi. Boshqa nom bilan urinib ko'ring.",
                reply_markup=back_to_menu_kb(),
            )
            return
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        items = await db.get_catalog_page(0, PAGE_SIZE, query)
        await message.answer(
            "🔍 <b>Qidiruv natijalari</b>\n"
            f"So'rov: <code>{html.escape(query)}</code>\n"
            f"Sahifa: <b>1/{total_pages}</b> • Jami: <b>{total}</b>",
            reply_markup=catalog_kb(items, 0, total_pages, search=True),
        )
    except Exception:
        logger.exception("Qidiruvda xatolik.")
        await message.answer("Qidiruvda xatolik yuz berdi.", reply_markup=main_menu_kb())


@router.callback_query(F.data.startswith("open_anime_"))
async def cb_open_anime(callback: CallbackQuery, bot: Bot, db: Database) -> None:
    try:
        sample_id = int((callback.data or "").rsplit("_", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    sample = await db.get_anime_by_id(sample_id)
    if sample is None:
        await callback.answer("Anime topilmadi.", show_alert=True)
        return

    first = await db.get_first_episode(sample.title, sample.hashtag)
    item = first or sample
    await callback.answer()
    try:
        if callback.message:
            await send_episode(bot, callback.message.chat.id, item, db)
    except TelegramAPIError as exc:
        logger.exception("Videoni yuborishda xatolik: %s", exc)
        await callback.answer("Videoni yuborib bo'lmadi.", show_alert=True)


@router.callback_query(F.data.startswith("prev_ep_"))
async def cb_prev_episode(callback: CallbackQuery, bot: Bot, db: Database) -> None:
    await _navigate_episode(callback, bot, db, step=-1)


@router.callback_query(F.data.startswith("next_ep_"))
async def cb_next_episode(callback: CallbackQuery, bot: Bot, db: Database) -> None:
    await _navigate_episode(callback, bot, db, step=1)


@router.callback_query(F.data == "episode_info")
async def cb_episode_info(callback: CallbackQuery) -> None:
    await callback.answer("Bu tugma joriy qism raqamini ko'rsatadi.", show_alert=False)


async def _navigate_episode(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    step: int,
) -> None:
    try:
        anime_id = int((callback.data or "").rsplit("_", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    current = await db.get_anime_by_id(anime_id)
    if current is None:
        await callback.answer("Qism topilmadi.", show_alert=True)
        return

    target_no = current.current_episode + step
    if target_no < 1:
        await callback.answer("Bu birinchi qism.", show_alert=True)
        return
    if target_no > current.total_episodes:
        await callback.answer("Bu oxirgi qism.", show_alert=True)
        return

    adjacent = await db.get_adjacent_episode(current.title, current.hashtag, target_no)
    if adjacent is None:
        if step < 0:
            await callback.answer("Oldingi qism hali yuklanmagan.", show_alert=True)
        else:
            await callback.answer("Keyingi qism hali yuklanmagan.", show_alert=True)
        return

    await callback.answer()
    try:
        await send_episode(
            bot,
            callback.message.chat.id if callback.message else callback.from_user.id,
            adjacent,
            db,
            edit_message=callback.message if isinstance(callback.message, Message) else None,
        )
    except TelegramAPIError as exc:
        logger.exception("Qismni almashtirishda xatolik: %s", exc)
        await callback.answer("Videoni yangilab bo'lmadi.", show_alert=True)
