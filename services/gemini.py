"""Gemini AI service: anime janrlari va O'zbek tilidagi ta'rifni qaytaradi."""

from __future__ import annotations

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
    genres: str        # masalan: "Sarguzasht, Fantastika, Drama"
    description: str   # O'zbek tilida 4 gaplik ta'rif


_FALLBACK = AnimeInfo(
    genres="Sarguzasht, Fantastika",
    description="Bu anime ajoyib voqealar va qahramonlik bilan to'la. Tomosha qilishga arziydi! Har bir qismida kutilmagan burilishlar bor. Barcha yoshdagi tomoshabinlar uchun qiziqarli.",
)

_PROMPT_TPL = (
    'Anime: "{title}"\n\n'
    "Menga faqat quyidagi formatda javob ber, boshqa hech narsa yozma:\n"
    "Janrlar: <2-3 ta janr, vergul bilan ajratilgan>\n"
    "Tavsif: <O'zbek tilida kamida 4 ta mazmunli va qiziqarli gapdan iborat bo'lgan, animening haqiqiy mazmuni va voqealar rivojini to'liq ochib beradigan batafsil ta'rif>"
)


async def fetch_anime_info(title: str) -> AnimeInfo:
    """Gemini orqali anime janrlari va O'zbek tilidagi qisqacha ta'rifni qaytaradi."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY yo'q, fallback ishlatilmoqda.")
        return _FALLBACK

    prompt = _PROMPT_TPL.format(title=title)
    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=500,
                temperature=0.7,
            ),
        )
        text = (response.text or "").strip()
        return _parse_response(text)
    except Exception as exc:
        logger.warning("Gemini javob bermadi (%s), fallback ishlatilmoqda.", exc)
        return _FALLBACK


def _parse_response(text: str) -> AnimeInfo:
    """Gemini'dan kelgan matnni janrlar va ta'rifga ajratadi."""
    genres = _FALLBACK.genres
    description = _FALLBACK.description

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("janrlar:"):
            val = stripped.split(":", 1)[1].strip()
            if val:
                genres = val
        elif stripped.lower().startswith("tavsif:"):
            val = stripped.split(":", 1)[1].strip()
            if val:
                description = val

    return AnimeInfo(genres=genres, description=description)
