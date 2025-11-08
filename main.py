import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import aiosqlite

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8268173697:AAHS82mSPPCPgM-3h-8ofzJIah2gkL9fooM"
ADMIN_ID = "5851585402"
PAYEER_ACCOUNT = "P1062588236"
BOT_USERNAME = "bestfarlm_bot"
ADMIN_USERNAME = "@mominjon_gofurov"
BOT_NAME = "BEST FARM 🌱"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== MA'LUMOTLAR BAZASI ====================
async def init_db():
    async with aiosqlite.connect("farm_bot.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                ref_by INTEGER DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS animals (
                user_id INTEGER,
                animal_type TEXT,
                amount INTEGER DEFAULT 0,
                purchased_at TEXT,
                PRIMARY KEY (user_id, animal_type)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                description TEXT,
                amount INTEGER,
                timestamp TEXT
            )
        """)
        await db.commit()

# ==================== FOYDALANUVCHI ====================
async def get_or_create_user(user_id: int, username: str | None, ref_by: int | None = None):
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT INTO users (user_id, username, ref_by) VALUES (?, ?, ?)",
                (user_id, username or f"user{user_id}", ref_by)
            )
            if ref_by:
                await db.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (ref_by,))
            await db.commit()
            user = (user_id, username or f"user{user_id}", 0, 0, ref_by)
        return user

# ==================== HAYVONLAR ====================
animals_config = {
    "joja": {"name": "Jo'ja", "emoji": "🐤", "price": 500},
    "tovuq": {"name": "Tovuq", "emoji": "🐔", "price": 1000},
    "ordak": {"name": "O'rdak", "emoji": "🦆", "price": 1500},
    "quyon": {"name": "Quyon", "emoji": "🐇", "price": 2500}
}
ANIMAL_LIFETIME_DAYS = 120

# ==================== AVTOMATIK FOYDA ====================
async def auto_collect_income():
    today = datetime.now().date()
    async with aiosqlite.connect("farm_bot.db") as db:
        # Barcha hayvonlarni olish
        cursor = await db.execute("SELECT user_id, animal_type, amount, purchased_at FROM animals")
        rows = await cursor.fetchall()

        for user_id, animal_type, amount, purchased_at in rows:
            if amount <= 0:
                continue

            animal = animals_config.get(animal_type)
            if not animal:
                continue

            purchased_date = datetime.strptime(purchased_at, "%Y-%m-%d").date()
            expiry_date = purchased_date + timedelta(days=ANIMAL_LIFETIME_DAYS)

            if today > expiry_date:
                # Hayvon muddati tugagan — o'chirish
                await db.execute("DELETE FROM animals WHERE user_id = ? AND animal_type = ?", (user_id, animal_type))
                continue

            # Kunlik foyda hisoblash (1%)
            daily_income = int(animal['price'] * 0.01)
            total_income = daily_income * amount

            # Balansga qo'shish
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_income, user_id))
            await db.execute("INSERT INTO transactions (user_id, description, amount, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, f"Avtomatik foyda: {animal['name']} x{amount}", total_income, datetime.now().strftime("%d.%m.%Y %H:%M")))

        await db.commit()

# ==================== KLAVIATURALAR ====================
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🐣 Hayvonlar"), KeyboardButton(text="👨‍🌾 Mening ferma")],
            [KeyboardButton(text="💰 Hisobim"), KeyboardButton(text="👛 Hamyon")],
            [KeyboardButton(text="🤝 Referal"), KeyboardButton(text="❓ Yordam")]
        ],
        resize_keyboard=True
    )

# ==================== BO'LIMLAR ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    ref_by = None
    if message.text and len(message.text.split()) > 1:
        ref_arg = message.text.split()[1]
        if ref_arg.startswith("referral_"):
            try:
                ref_by = int(ref_arg.replace("referral_", ""))
            except ValueError:
                ref_by = None
    user = await get_or_create_user(message.from_user.id, message.from_user.username, ref_by)
    await message.answer(
        f"✨ {BOT_NAME} ga xush kelibsiz, {user[1]}!\n\n"
        "Siz quyidagi bo'limlardan foydalanishingiz mumkin:",
        reply_markup=main_menu()
    )

@dp.message(lambda msg: msg.text == "💰 Hisobim")
async def my_account(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT username, balance, referrals FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await message.answer("❌ Siz ro'yxatdan o'tmagansiz. Iltimos, /start buyrug'ini yuboring.")
            return
        cursor = await db.execute("SELECT description, amount, timestamp FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        txs = await cursor.fetchall()

    report = ""
    for desc, amount, ts in txs:
        sign = "+" if amount >= 0 else ""
        report += f"🌳 [{ts}]\n{desc}\nBalans: {user[1]} ₽\n\n"

    report += f"🆔: {user_id}\n💵 Balans: {user[1]} ₽\n🫂 Referallar: {user[2]} ta"
    await message.answer(report)

# ==================== BOSHQA BO'LIMLAR (Referal, Yordam, Hayvonlar...) ====================
# (Bu qismlarni kamaytirib, asosiy qismlarni saqlab qoldim — GitHubda to'liq qoldiring)

# ... (boshqa funksiyalar o'zgarmasdan qoladi — hayvonlar, to'lov, admin panel, referal)

# ==================== ASOSIY ====================
async def main():
    await init_db()
    
    # ✅ AVTOMATIK ISHLOVCHI YOQILDI
    scheduler = AsyncIOScheduler()
    scheduler.add_job(auto_collect_income, IntervalTrigger(hours=24), id='daily_income')
    scheduler.start()
import os
os.environ['TZ'] = 'Asia/Tashkent'  # yoki o'zingizning mintaqangiz
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
