"""Gemini AI service: anime janrlari va O'zbek tilidagi ta'rifni qaytaradi."""

from __future__ import annotations

import asyncio
import logging
from typing import NamedTuple

from google import genai
from google.genai import types

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


class AnimeInfo(NamedTuple):
    genres: str
    description: str


_FALLBACK = AnimeInfo(
    genres="Sarguzasht, Fantastika",
    description=(
        "Bu animeda asosiy qahramon kuchli dushmanlar va to'siqlar bilan kurashib, "
        "o'zini isbotlashga harakat qiladi. Voqealar shiddatli va kutilmagan burilishlar bilan to'la. "
        "Do'stlik va sadoqat bu animening asosiy mavzularidir. "
        "Har bir qism tomoshabinni yangi kashfiyotlarga da'vat etadi."
    ),
)

# Alohida promptlar — har biri bitta javob qaytaradi
_GENRES_PROMPT = (
    '"{title}" animesining asosiy janrlarini yoz '
    "(vergul bilan ajratilgan 2-3 ta janr, faqat janr nomlarini yoz, boshqa hech narsa yozma):"
)
_DESC_PROMPT = (
    '"{title}" animesining syujeti haqida O\'zbek tilida '
    "4 ta qisqa gap yoz. Faqat animening haqiqiy mazmunini yoz, "
    "boshqa hech narsa yozma:"
)


async def fetch_anime_info(title: str) -> AnimeInfo:
    """Gemini orqali anime janrlari va O'zbek tilidagi ta'rifni qaytaradi."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY yo'q, fallback ishlatilmoqda.")
        return _FALLBACK

    try:
        client = _get_client()
        # Ikkala so'rovni parallel yuboramiz
        genres_prompt = _GENRES_PROMPT.format(title=title)
        desc_prompt = _DESC_PROMPT.format(title=title)

        genres_resp, desc_resp = await asyncio.wait_for(
            asyncio.gather(
                client.aio.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=genres_prompt,
                    config=types.GenerateContentConfig(max_output_tokens=40, temperature=0.3),
                ),
                client.aio.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=desc_prompt,
                    config=types.GenerateContentConfig(max_output_tokens=280, temperature=0.5),
                ),
            ),
            timeout=12.0,
        )

        genres = (genres_resp.text or "").strip().rstrip(".")
        description = (desc_resp.text or "").strip()

        # Bo'sh bo'lsa fallback
        genres = genres if genres else _FALLBACK.genres
        description = description if description else _FALLBACK.description

        logger.info("Gemini OK: %s | %s...", genres[:40], description[:40])
        return AnimeInfo(genres=genres, description=description)

    except asyncio.TimeoutError:
        logger.warning("Gemini timeout, fallback.")
        return _FALLBACK
    except Exception as exc:
        logger.warning("Gemini xatolik (%s), fallback.", exc)
        return _FALLBACK

