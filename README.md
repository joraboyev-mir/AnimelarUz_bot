# AnimeUz Telegram Bot

O'zbek tilidagi animelarni qidirish, ko'rish, yuklab olish va kanallarga obunani tekshirish imkoniyatiga ega Telegram bot.

## Xususiyatlar

- **Anime qidiruv va ko'rish:** Kod yoki nom bo'yicha animelarni qidirish, qismlarni tomosha qilish.
- **Majburiy obuna (Sponsor kanallar):** Foydalanuvchilarni belgilangan kanallarga a'zoligini tekshirish tizimi.
- **Admin panel:**
  - Yangi anime va qismlarni qo'shish / tahrirlash / o'chirish.
  - Majburiy obuna kanallarini boshqarish.
  - Statistika ko'rish.
  - Foydalanuvchilarga xabar tarqatish (Broadcast).
- **Asinxron va tezkor:** iogram 3 va iosqlite asosida qurilgan.

## O'rnatish va Ishga tushirish

1. **Repozitoriyani klonlash:**
   `ash
   git clone <REPO_URL>
   cd AnimelarUz_bot
   `

2. **Virtual muhitni yaratish va faollashtirish:**
   `ash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   `

3. **Kutubxonalarni o'rnatish:**
   `ash
   pip install -r requirements.txt
   `

4. **Muhit o'zgaruvchilarini sozlash:**
   .env.example faylidan nusxa olib, .env faylini yarating va kerakli ma'lumotlarni to'ldiring:
   `ash
   cp .env.example .env
   `
   .env tarkibi:
   `env
   BOT_TOKEN=your_bot_token_here
   SUPER_ADMIN_ID=your_telegram_id
   MAIN_CHANNEL_ID=-100xxxxxxxxxx
   MAIN_CHANNEL_USERNAME=your_channel_username
   `

5. **Botni ishga tushirish:**
   `ash
   python main.py
   `

## Texnologiyalar

- Python 3.10+
- aiogram 3.x
- aiosqlite
- python-dotenv
