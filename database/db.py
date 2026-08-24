"""Asynchronous SQLite manager for AnimeUz."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import aiosqlite

from config import DB_PATH, SUPER_ADMIN_ID

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UserRecord:
    id: int
    telegram_id: int
    full_name: str
    username: Optional[str]
    joined_date: str


@dataclass(slots=True)
class AnimeRecord:
    id: int
    title: str
    current_episode: int
    total_episodes: int
    file_id: str
    hashtag: str
    views: int


@dataclass(slots=True)
class ChannelRecord:
    id: int
    channel_username: str
    channel_title: str
    channel_url: str


@dataclass(slots=True)
class AdminRecord:
    id: int
    telegram_id: int
    full_name: str


@dataclass(slots=True)
class AnimeCatalogItem:
    """Grouped anime row used on the public catalog pages."""

    sample_id: int
    title: str
    hashtag: str
    total_episodes: int
    available_episodes: int
    views: int


class Database:
    """Thin async wrapper around aiosqlite with all CRUD operations."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = Path(path)

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with aiosqlite.connect(self.path) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                await db.execute("PRAGMA foreign_keys=ON;")
                await db.execute("PRAGMA busy_timeout=5000;")
                await self._create_tables(db)
                await db.commit()
            await self.ensure_super_admin()
            logger.info("Ma'lumotlar bazasi tayyor: %s", self.path)
        except Exception:
            logger.exception("Ma'lumotlar bazasini ishga tushirishda xatolik.")
            raise

    async def _create_tables(self, db: aiosqlite.Connection) -> None:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                username TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS anime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                current_episode INTEGER NOT NULL,
                total_episodes INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                hashtag TEXT NOT NULL,
                views INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS mandatory_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_username TEXT UNIQUE NOT NULL,
                channel_title TEXT NOT NULL,
                channel_url TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_anime_title ON anime(title);
            CREATE INDEX IF NOT EXISTS idx_anime_hashtag ON anime(hashtag);
            CREATE INDEX IF NOT EXISTS idx_anime_episode ON anime(title, current_episode);
            """
        )

    async def _execute(
        self,
        sql: str,
        params: Iterable[Any] = (),
        *,
        fetchone: bool = False,
        fetchall: bool = False,
        commit: bool = False,
    ) -> Any:
        try:
            async with aiosqlite.connect(self.path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(sql, tuple(params))
                result: Any = None
                if fetchone:
                    result = await cursor.fetchone()
                elif fetchall:
                    result = await cursor.fetchall()
                else:
                    result = cursor.lastrowid
                if commit:
                    await db.commit()
                await cursor.close()
                return result
        except aiosqlite.Error:
            logger.exception("SQL xatoligi: %s | params=%s", sql, params)
            raise

    # ── Users ───────────────────────────────────────────────────────────

    async def upsert_user(
        self,
        telegram_id: int,
        full_name: str,
        username: Optional[str],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        await self._execute(
            """
            INSERT INTO users (telegram_id, full_name, username, joined_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username
            """,
            (telegram_id, full_name, username, now),
            commit=True,
        )

    async def get_user(self, telegram_id: int) -> Optional[UserRecord]:
        row = await self._execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
            fetchone=True,
        )
        return self._user_from_row(row) if row else None

    async def count_users(self) -> int:
        row = await self._execute("SELECT COUNT(*) AS c FROM users", fetchone=True)
        return int(row["c"]) if row else 0

    # ── Anime ───────────────────────────────────────────────────────────

    async def add_anime(
        self,
        title: str,
        current_episode: int,
        total_episodes: int,
        file_id: str,
        hashtag: str,
    ) -> int:
        existing = await self.get_episode_by_title(title, current_episode)
        if existing:
            await self._execute(
                """
                UPDATE anime
                SET total_episodes = ?, file_id = ?, hashtag = ?
                WHERE id = ?
                """,
                (total_episodes, file_id, hashtag, existing.id),
                commit=True,
            )
            logger.info("Anime qismi yangilandi: %s #%s (id=%s)", title, current_episode, existing.id)
            return existing.id

        last_id = await self._execute(
            """
            INSERT INTO anime (title, current_episode, total_episodes, file_id, hashtag, views)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (title, current_episode, total_episodes, file_id, hashtag),
            commit=True,
        )
        new_id = int(last_id or 0)
        logger.info("Yangi anime qismi saqlandi: %s #%s (id=%s)", title, current_episode, new_id)
        return new_id

    async def get_anime_by_id(self, anime_id: int) -> Optional[AnimeRecord]:
        row = await self._execute(
            "SELECT * FROM anime WHERE id = ?",
            (anime_id,),
            fetchone=True,
        )
        return self._anime_from_row(row) if row else None

    async def get_episode_by_title(self, title: str, episode: int) -> Optional[AnimeRecord]:
        row = await self._execute(
            """
            SELECT * FROM anime
            WHERE LOWER(title) = LOWER(?) AND current_episode = ?
            LIMIT 1
            """,
            (title, episode),
            fetchone=True,
        )
        return self._anime_from_row(row) if row else None

    async def get_adjacent_episode(
        self,
        title: str,
        hashtag: str,
        episode: int,
    ) -> Optional[AnimeRecord]:
        row = await self._execute(
            """
            SELECT * FROM anime
            WHERE (LOWER(title) = LOWER(?) OR LOWER(hashtag) = LOWER(?))
              AND current_episode = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (title, hashtag, episode),
            fetchone=True,
        )
        return self._anime_from_row(row) if row else None

    async def increment_views(self, anime_id: int) -> None:
        await self._execute(
            "UPDATE anime SET views = views + 1 WHERE id = ?",
            (anime_id,),
            commit=True,
        )

    async def count_unique_anime(self, query: Optional[str] = None) -> int:
        if query:
            like = f"%{query.strip()}%"
            row = await self._execute(
                """
                SELECT COUNT(*) AS c FROM (
                    SELECT title, hashtag
                    FROM anime
                    WHERE title LIKE ? OR hashtag LIKE ?
                    GROUP BY LOWER(title), LOWER(hashtag)
                )
                """,
                (like, like),
                fetchone=True,
            )
        else:
            row = await self._execute(
                """
                SELECT COUNT(*) AS c FROM (
                    SELECT title, hashtag FROM anime GROUP BY LOWER(title), LOWER(hashtag)
                )
                """,
                fetchone=True,
            )
        return int(row["c"]) if row else 0

    async def get_catalog_page(
        self,
        page: int,
        page_size: int,
        query: Optional[str] = None,
    ) -> list[AnimeCatalogItem]:
        offset = max(page, 0) * page_size
        params: list[Any]
        where = ""
        if query:
            like = f"%{query.strip()}%"
            where = "WHERE title LIKE ? OR hashtag LIKE ?"
            params = [like, like, page_size, offset]
        else:
            params = [page_size, offset]

        rows = await self._execute(
            f"""
            SELECT
                MIN(id) AS sample_id,
                title,
                hashtag,
                MAX(total_episodes) AS total_episodes,
                COUNT(*) AS available_episodes,
                SUM(views) AS views
            FROM anime
            {where}
            GROUP BY LOWER(title), LOWER(hashtag)
            ORDER BY MAX(id) DESC
            LIMIT ? OFFSET ?
            """,
            params,
            fetchall=True,
        )
        items: list[AnimeCatalogItem] = []
        for row in rows or []:
            items.append(
                AnimeCatalogItem(
                    sample_id=int(row["sample_id"]),
                    title=row["title"],
                    hashtag=row["hashtag"],
                    total_episodes=int(row["total_episodes"] or 0),
                    available_episodes=int(row["available_episodes"] or 0),
                    views=int(row["views"] or 0),
                )
            )
        return items

    async def get_first_episode(self, title: str, hashtag: str) -> Optional[AnimeRecord]:
        row = await self._execute(
            """
            SELECT * FROM anime
            WHERE LOWER(title) = LOWER(?) OR LOWER(hashtag) = LOWER(?)
            ORDER BY current_episode ASC, id ASC
            LIMIT 1
            """,
            (title, hashtag),
            fetchone=True,
        )
        return self._anime_from_row(row) if row else None

    async def count_episodes(self) -> int:
        row = await self._execute("SELECT COUNT(*) AS c FROM anime", fetchone=True)
        return int(row["c"]) if row else 0

    async def total_views(self) -> int:
        row = await self._execute("SELECT COALESCE(SUM(views), 0) AS c FROM anime", fetchone=True)
        return int(row["c"]) if row else 0

    # ── Mandatory channels ──────────────────────────────────────────────

    async def add_channel(self, username: str, title: str, url: str) -> int:
        last_id = await self._execute(
            """
            INSERT INTO mandatory_channels (channel_username, channel_title, channel_url)
            VALUES (?, ?, ?)
            ON CONFLICT(channel_username) DO UPDATE SET
                channel_title = excluded.channel_title,
                channel_url = excluded.channel_url
            """,
            (username, title, url),
            commit=True,
        )
        logger.info("Majburiy kanal saqlandi: %s", username)
        return int(last_id)

    async def remove_channel(self, channel_id: int) -> bool:
        await self._execute(
            "DELETE FROM mandatory_channels WHERE id = ?",
            (channel_id,),
            commit=True,
        )
        logger.info("Majburiy kanal o'chirildi: id=%s", channel_id)
        return True

    async def get_all_channels(self) -> list[ChannelRecord]:
        rows = await self._execute(
            "SELECT * FROM mandatory_channels ORDER BY id ASC",
            fetchall=True,
        )
        return [self._channel_from_row(row) for row in (rows or [])]

    async def get_channel(self, channel_id: int) -> Optional[ChannelRecord]:
        row = await self._execute(
            "SELECT * FROM mandatory_channels WHERE id = ?",
            (channel_id,),
            fetchone=True,
        )
        return self._channel_from_row(row) if row else None

    async def count_channels(self) -> int:
        row = await self._execute("SELECT COUNT(*) AS c FROM mandatory_channels", fetchone=True)
        return int(row["c"]) if row else 0

    # ── Admins ──────────────────────────────────────────────────────────

    async def ensure_super_admin(self) -> None:
        try:
            await self._execute(
                """
                INSERT INTO admins (telegram_id, full_name)
                VALUES (?, ?)
                ON CONFLICT(telegram_id) DO NOTHING
                """,
                (SUPER_ADMIN_ID, "Super Admin"),
                commit=True,
            )
        except Exception:
            logger.exception("SUPER_ADMIN_ID ni admins jadvaliga yozib bo'lmadi.")

    async def add_admin(self, telegram_id: int, full_name: str) -> int:
        last_id = await self._execute(
            """
            INSERT INTO admins (telegram_id, full_name)
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET full_name = excluded.full_name
            """,
            (telegram_id, full_name),
            commit=True,
        )
        logger.info("Admin qo'shildi: %s (%s)", telegram_id, full_name)
        return int(last_id)

    async def remove_admin(self, telegram_id: int) -> bool:
        if telegram_id == SUPER_ADMIN_ID:
            return False
        await self._execute(
            "DELETE FROM admins WHERE telegram_id = ?",
            (telegram_id,),
            commit=True,
        )
        logger.info("Admin o'chirildi: %s", telegram_id)
        return True

    async def get_all_admins(self) -> list[AdminRecord]:
        rows = await self._execute(
            "SELECT * FROM admins ORDER BY id ASC",
            fetchall=True,
        )
        return [self._admin_from_row(row) for row in (rows or [])]

    async def is_admin(self, telegram_id: int) -> bool:
        if telegram_id == SUPER_ADMIN_ID:
            return True
        row = await self._execute(
            "SELECT 1 FROM admins WHERE telegram_id = ? LIMIT 1",
            (telegram_id,),
            fetchone=True,
        )
        return row is not None

    async def count_admins(self) -> int:
        row = await self._execute("SELECT COUNT(*) AS c FROM admins", fetchone=True)
        return int(row["c"]) if row else 0

    async def get_stats(self) -> dict[str, int]:
        return {
            "users": await self.count_users(),
            "anime": await self.count_unique_anime(),
            "episodes": await self.count_episodes(),
            "views": await self.total_views(),
            "channels": await self.count_channels(),
            "admins": await self.count_admins(),
        }

    # ── Row helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _user_from_row(row: aiosqlite.Row) -> UserRecord:
        return UserRecord(
            id=int(row["id"]),
            telegram_id=int(row["telegram_id"]),
            full_name=row["full_name"],
            username=row["username"],
            joined_date=str(row["joined_date"]),
        )

    @staticmethod
    def _anime_from_row(row: aiosqlite.Row) -> AnimeRecord:
        return AnimeRecord(
            id=int(row["id"]),
            title=row["title"],
            current_episode=int(row["current_episode"]),
            total_episodes=int(row["total_episodes"]),
            file_id=row["file_id"],
            hashtag=row["hashtag"],
            views=int(row["views"] or 0),
        )

    @staticmethod
    def _channel_from_row(row: aiosqlite.Row) -> ChannelRecord:
        return ChannelRecord(
            id=int(row["id"]),
            channel_username=row["channel_username"],
            channel_title=row["channel_title"],
            channel_url=row["channel_url"],
        )

    @staticmethod
    def _admin_from_row(row: aiosqlite.Row) -> AdminRecord:
        return AdminRecord(
            id=int(row["id"]),
            telegram_id=int(row["telegram_id"]),
            full_name=row["full_name"],
        )
