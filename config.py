"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
DB_PATH: Path = DATA_DIR / "animeuz.db"

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
MAIN_CHANNEL_USERNAME: str = os.getenv("MAIN_CHANNEL_USERNAME", "").strip().lstrip("@")


def _parse_int(name: str, required: bool = True) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        if required:
            raise RuntimeError(f"{name} muhit o'zgaruvchisi majburiy.")
        return 0
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} butun son bo'lishi kerak. Qiymat: {raw!r}") from exc


SUPER_ADMIN_ID: int = _parse_int("SUPER_ADMIN_ID")
MAIN_CHANNEL_ID: int = _parse_int("MAIN_CHANNEL_ID")

BOT_USERNAME: str = "animeuz_rasmiy_bot"
PAGE_SIZE: int = 6


def validate_config() -> None:
    """Fail fast if critical settings are missing."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan.")
    if SUPER_ADMIN_ID <= 0:
        raise RuntimeError("SUPER_ADMIN_ID musbat butun son bo'lishi kerak.")
    if MAIN_CHANNEL_ID == 0:
        raise RuntimeError("MAIN_CHANNEL_ID noto'g'ri. Kanal ID ni kiriting (masalan, -100...).")


def setup_logging() -> None:
    """Configure structured console logging for the whole process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
