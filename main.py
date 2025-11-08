import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import aiosqlite

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# ==================== SOZLAMALAR (O'ZINGIZNI MA'LUMOTLARINGIZNI SHU YERGA YOZING) ====================
BOT_TOKEN = "8268173697:AAHS82mSPPCPgM-3h-8ofzJIah2gkL9fooM"  # 👈 O'z bot tokeningiz
ADMIN_ID = "5851585402"  # 👈 O'zingizning Telegram ID'ingiz (faqat raqam)
PAYEER_ACCOUNT = "P1062588236"  # 👈 Sizning Payeer manzilingiz
BOT_USERNAME = "bestfarlm_bot"  # 👈 Sizning bot usernamingiz (BotFatherda belgilangan)
ADMIN_USERNAME = "mominjon_gofurov"  # 👈 Sizning Telegram usernamingiz
BOT_NAME = "BEST FARM 🌱"

# ==================== VAQT ZONASI ====================
TASHKENT_TZ = pytz.timezone("Asia/Tashkent")

# ==================== LOGGING ====================
logging.basicConfig(level=logging.INFO)

# ==================== BOT VA DISPATCHER ====================
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

# ==================== YORDAMCHI: FOYDALANUVCHI ====================
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

# ==================== HOLATLAR ====================
class TopUp(StatesGroup):
    amount = State()

class Withdraw(StatesGroup):
    amount = State()
    address = State()

class AdminTopUp(StatesGroup):
    user_id = State()
    amount = State()

class AdminWithdraw(StatesGroup):
    user_id = State()
    amount = State()

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

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Hisob to'ldirish", callback_data="admin_topup")],
        [InlineKeyboardButton(text="➖ Hisobdan yechish", callback_data="admin_withdraw")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar ro'yxati", callback_data="admin_users")],
        [InlineKeyboardButton(text="💳 Tranzaksiyalar", callback_data="admin_transactions")],
        [InlineKeyboardButton(text="🏘 Bosh sahifa", callback_data="back_home")]
    ])

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

@dp.message(lambda msg: msg.text == "❓ Yordam")
async def help_section(message: types.Message):
    await message.answer(f"📞 Yordam uchun admin: @{ADMIN_USERNAME}")

@dp.message(lambda msg: msg.text == "🤝 Referal")
async def referral_info(message: types.Message):
    ref_link = f"https://t.me/{BOT_USERNAME}?start=referral_{message.from_user.id}"
    await message.answer(
        "🔗 Sizning shaxsiy referal havolangiz:\n\n"
        f"`{ref_link}`\n\n"
        "Do'stlaringiz ushbu havola orqali kirsa, ular sizning referalingiz bo'ladi.",
        parse_mode="Markdown"
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

    report = f"🆔: {user_id}\n💵 Balans: {user[1]} ₽\n🫂 Referallar: {user[2]} ta"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Hisobni to'ldirish", callback_data="top_up_start")],
        [InlineKeyboardButton(text="📤 Hisobdan yechish", callback_data="withdraw_start")],
        [InlineKeyboardButton(text="🏘 Bosh sahifa", callback_data="back_home")]
    ])
    await message.answer(report, reply_markup=kb)

@dp.message(lambda msg: msg.text == "👨‍🌾 Mening ferma")
async def my_farm(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT animal_type, amount FROM animals WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()

    animal_counts = {k: 0 for k in animals_config}
    for row in rows:
        animal_counts[row[0]] = row[1]

    text = (
        f"👋 Fermangizga xush kelibsiz, {message.from_user.first_name}!\n\n"
        f"👨🏻‍🌾 Sizning hayvonlaringiz:\n\n"
        f"🐤 Jo'ja: {animal_counts['joja']}\n"
        f"🐔 Tovuq: {animal_counts['tovuq']}\n"
        f"🦆 O'rdak: {animal_counts['ordak']}\n"
        f"🐇 Quyon: {animal_counts['quyon']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏘 Bosh sahifa", callback_data="back_home")]
    ])
    await message.answer(text, reply_markup=kb)

@dp.message(lambda msg: msg.text == "🐣 Hayvonlar")
async def show_animals(message: types.Message):
    username = message.from_user.username or "do'st"
    await message.answer(
        f"✨ Hayvonlar doʻkoniga xush kelibsiz, {username}!\n\n"
        "Bizning hayvonot do'konimizda turli hayvonlar va ularning narxlari bilan tanishishingiz mumkin."
    )
    for key, animal in animals_config.items():
        daily_income = int(animal['price'] * 0.01)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Xarid qilish", callback_data=f"buy_{key}")],
            [InlineKeyboardButton(text="🏘 Bosh sahifa", callback_data="back_home")]
        ])
        await message.answer(
            f"{animal['emoji']} {animal['name'].upper()} taʼrifi:\n\n"
            f"💰 Narxi: {animal['price']} ₽\n"
            f"📈 Kunlik foyda: {daily_income} ₽ (1%)\n"
            f"⏳ Faol davr: {ANIMAL_LIFETIME_DAYS} kun",
            reply_markup=kb
        )

# ==================== XARID QILISH ====================
@dp.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
   if not callback.message:
        return
    animal_key = callback.data.split("_")[1]
    animal = animals_config[animal_key]
    user_id = callback.from_user.id

    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        if not result:
            return
        balance = result[0]

        if balance >= animal['price']:
            new_balance = balance - animal['price']
            await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
            await db.execute("""
                INSERT INTO animals (user_id, animal_type, amount, purchased_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_id, animal_type) DO UPDATE SET
                amount = amount + 1, purchased_at = excluded.purchased_at
            """, (user_id, animal_key, datetime.now().strftime("%Y-%m-%d")))
            await db.execute("INSERT INTO transactions (user_id, description, amount, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, f"{animal['name']} xarid qildingiz", -animal['price'], datetime.now().strftime("%d.%m.%Y %H:%M")))
            await db.commit()
            if callback.message:
                await callback.message.answer(
                    f"🌳 Muvaffaqiyatli tarzda {animal['name'].lower()} xarid qildingiz!\n\n"
                    f"Fermangizda ko'proq foyda olishni boshlang!",
                    reply_markup=main_menu()
                )
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Balans to'ldirish", callback_data="top_up_start")],
                [InlineKeyboardButton(text="🏘 Bosh sahifa", callback_data="back_home")]
            ])
            if callback.message:
                await callback.message.answer(
                    f"💁‍♂ Hisobingizda mablag' yetarli emas!\n\n"
                    f"💰 Balansingiz: {balance} ₽\n"
                    f"{animal['emoji']} {animal['name']} narxi: {animal['price']} ₽.",
                    reply_markup=kb
                )
    await callback.answer()

# ==================== TO'LOV / YECHISH (FOYDALANUVCHI) ====================
@dp.callback_query(lambda c: c.data == "top_up_start")
async def top_up_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.message:
        await callback.message.answer("💰 Hisobingizni qancha summa bilan to'ldirmoqchisiz?\n\n"
                                      "📌 Namuna: 500\n"
                                      "❗ Minimal summa: 500 ₽")
    await state.set_state(TopUp.amount)
    await callback.answer()

@dp.message(TopUp.amount)
async def process_top_up_amount(message: types.Message, state: FSMContext):
    if not message.text:
        return
    try:
        amount = int(message.text)
        if amount < 500:
            await message.answer("❗ Minimal to'lov summasi: 500 ₽.\n\nIltimos, qaytadan kiriting:")
            return
        # Foydalanuvchi ID asosida 1-3 orasida qo'shimcha
extra = (message.from_user.id % 3) + 1  # 1, 2 yoki 3
final_amount = amount + extra

link = f"https://payeer.com/ru/account/send/?to={PAYEER_ACCOUNT}&sum={amount}&currency=RUB"
await message.answer(
    f"✅ To'lov uchun quyidagi havolaga o'ting:\n\n{link}\n\n"
    f"🔹 Siz {amount} ₽ to'lashni rejalashtirdingiz, lekin aniqlik uchun {extra} ₽ qo'shildi.\n"
    f"🔹 Jami to'lov: {final_amount} ₽\n\n"
    f"🧾 To'lovni amalga oshirgandan so'ng, admin hisobingizni qo'lda to'ldiradi.\n"
    f"🆔 Foydalanuvchi ID: {message.from_user.id}"
)
        await message.answer(
            f"✅ To'lov uchun quyidagi havolaga o'ting:\n\n{link}\n\n"
            f"🔹 To'lovni amalga oshirgandan so'ng, admin hisobingizni qo'lda to'ldiradi.\n"
            f"🧾 To'lov ID yoki skrinshotni admin (@{ADMIN_USERNAME}) ga yuboring."
        )
        await bot.send_message(ADMIN_ID, f"🆕 Yangi to'lov so'rovi:\nFoydalanuvchi: @{message.from_user.username} (ID: {message.from_user.id})\nSumma: {amount} ₽")
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri summa. Faqat raqam kiriting (masalan: 500):")

@dp.callback_query(lambda c: c.data == "withdraw_start")
async def withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = await cursor.fetchone()
        if not result:
            return
        balance = result[0]
    if callback.message:
        await callback.message.answer(
            f"💁‍♂ Pul chiqarib olishning eng kam miqdori: 250 ₽\n\n"
            f"Sizning balans: {balance} ₽.\n\n"
            "❓ Qancha pul yechmoqchisiz?"
        )
    await state.set_state(Withdraw.amount)
    await callback.answer()

@dp.message(Withdraw.amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if not message.text:
        return
    try:
        amount = int(message.text)
        user_id = message.from_user.id
        if amount < 250:
            await message.answer("❗ Minimal yechish summasi: 250 ₽.\n\nIltimos, qaytadan kiriting:")
            return
        async with aiosqlite.connect("farm_bot.db") as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            if not result:
                return
            balance = result[0]
        if amount > balance:
            await message.answer(f"🚫 Hisobingizda yetarli mablag' yo'q!\nSizning balans: {balance} ₽.")
            return
        await state.update_data(amount=amount)
        await message.answer("📬 Iltimos, Payeer manzilingizni kiriting:\n\nMasalan: P1234567890")
        await state.set_state(Withdraw.address)
    except ValueError:
        await message.answer("❌ Noto'g'ri summa. Faqat raqam kiriting:")

@dp.message(Withdraw.address)
async def process_withdraw_address(message: types.Message, state: FSMContext):
    if not message.text:
        return
    address = message.text.strip()
    if not address.startswith("P") or len(address) < 10:
        await message.answer("❌ Noto'g'ri Payeer manzil. To'g'ri manzil: P1234567890\n\nQaytadan kiriting:")
        return
    data = await state.get_data()
    amount = data["amount"]
    user_id = message.from_user.id
    username = message.from_user.username or f"user{user_id}"

    async with aiosqlite.connect("farm_bot.db") as db:
        await db.execute("""
            INSERT INTO transactions (user_id, description, amount, timestamp)
            VALUES (?, ?, ?, ?)
        """, (user_id, f"Withdraw request to {address}", -amount, datetime.now().strftime("%d.%m.%Y %H:%M")))
        await db.commit()

    await bot.send_message(
        ADMIN_ID,
        f"💸 Yangi pul yechish so'rovi!\n\n"
        f"👤 Foydalanuvchi: @{username} (ID: {user_id})\n"
        f"💰 Summa: {amount} ₽\n"
        f"📬 Payeer: {address}"
    )

    await message.answer(
        "✅ So'rov qabul qilindi!\n\n"
        "Admin tez orada pulingizni yuboradi. Iltimos, kuting."
    )
    await state.clear()

# ==================== ADMIN PANEL ====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 Sizda bu bo'lim uchun ruxsat yo'q.")
        return
    await message.answer("🔐 Admin panel:", reply_markup=admin_menu())

# --- Admin to'ldirish / yechish / ro'yxat / tranzaksiyalar ---
# (Ular oldingi versiyada to'g'ri ishlaydi — qisqartirilmagan holda GitHubda qoldiring)

@dp.callback_query(lambda c: c.data == "admin_topup")
async def admin_topup_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("👤 Foydalanuvchi ID'sini kiriting:")
    await state.set_state(AdminTopUp.user_id)
    await callback.answer()

@dp.message(AdminTopUp.user_id)
async def admin_topup_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer("💰 Qancha mablag' qo'shmoqchisiz? (₽)")
        await state.set_state(AdminTopUp.amount)
    except ValueError:
        await message.answer("❌ Noto'g'ri ID.")

@dp.message(AdminTopUp.amount)
async def admin_topup_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        amount = int(message.text)
        data = await state.get_data()
        user_id = data["user_id"]
        async with aiosqlite.connect("farm_bot.db") as db:
            cursor = await db.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            if not await cursor.fetchone():
                await message.answer(f"❌ Foydalanuvchi topilmadi.")
                return
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            await db.execute("INSERT INTO transactions (user_id, description, amount, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, f"Admin tomonidan {amount} ₽ qo'shildi", amount, datetime.now().strftime("%d.%m.%Y %H:%M")))
            await db.commit()
        await message.answer(f"✅ {user_id} ga {amount} ₽ qo'shildi!")
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri summa.")

@dp.callback_query(lambda c: c.data == "admin_withdraw")
async def admin_withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("👤 Foydalanuvchi ID'sini kiriting:")
    await state.set_state(AdminWithdraw.user_id)
    await callback.answer()

@dp.message(AdminWithdraw.user_id)
async def admin_withdraw_user_id(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer("💰 Qancha yechmoqchisiz? (₽)")
        await state.set_state(AdminWithdraw.amount)
    except ValueError:
        await message.answer("❌ Noto'g'ri ID.")

@dp.message(AdminWithdraw.amount)
async def admin_withdraw_amount(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        amount = int(message.text)
        data = await state.get_data()
        user_id = data["user_id"]
        async with aiosqlite.connect("farm_bot.db") as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if not row or row[0] < amount:
                await message.answer("🚫 Yetarli mablag' yo'q.")
                return
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
            await db.execute("INSERT INTO transactions (user_id, description, amount, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, f"Admin tomonidan {amount} ₽ yechildi", -amount, datetime.now().strftime("%d.%m.%Y %H:%M")))
            await db.commit()
        await message.answer(f"✅ {user_id} dan {amount} ₽ yechildi!")
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto'g'ri summa.")

@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_list_users(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT user_id, username, balance, referrals FROM users ORDER BY user_id DESC LIMIT 50")
        users = await cursor.fetchall()
    text = "👥 Foydalanuvchilar (so'nggi 50):\n\n"
    for uid, uname, bal, refs in users:
        text += f"ID: `{uid}` | @{uname} | 💵 {bal} ₽ | 🫂 {refs}\n"
    await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "admin_transactions")
async def admin_list_transactions(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("""
            SELECT t.user_id, u.username, t.description, t.amount, t.timestamp
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.user_id
            ORDER BY t.id DESC LIMIT 30
        """)
        txs = await cursor.fetchall()
    if not txs:
        await callback.message.answer("❌ Tranzaksiyalar yo'q.")
        return
    text = "💳 So'nggi tranzaksiyalar:\n\n"
    for uid, uname, desc, amt, ts in txs:
        sign = "+" if amt >= 0 else ""
        text += f"ID: `{uid}` | @{uname or 'user'}\n{desc}\n{sign}{amt} ₽ | {ts}\n\n"
    await callback.message.answer(text, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "back_home")
async def back_to_main(callback: types.CallbackQuery):
    if callback.message:
        await callback.message.answer("🏘 Bosh menyu:", reply_markup=main_menu())
    await callback.answer()

# ==================== AVTOMATIK FOYDA ====================
async def auto_collect_income():
    today = datetime.now(TASHKENT_TZ).date()
    now_str = datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M")
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT user_id, animal_type, amount, purchased_at FROM animals")
        rows = await cursor.fetchall()

        user_total_income = {}

        for user_id, animal_type, amount, purchased_at in rows:
            if amount <= 0:
                continue
            animal = animals_config.get(animal_type)
            if not animal:
                continue

            purchased_date = datetime.strptime(purchased_at, "%Y-%m-%d").date()
            expiry_date = purchased_date + timedelta(days=ANIMAL_LIFETIME_DAYS)

            if today > expiry_date:
                await db.execute("DELETE FROM animals WHERE user_id = ? AND animal_type = ?", (user_id, animal_type))
                continue

            daily_income = int(animal['price'] * 0.01)
            total_income = daily_income * amount

            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_income, user_id))
            await db.execute("INSERT INTO transactions (user_id, description, amount, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, f"{animal['name']}dan foyda", total_income, now_str))

            if user_id not in user_total_income:
                user_total_income[user_id] = 0
            user_total_income[user_id] += total_income

        await db.commit()

        for user_id, total in user_total_income.items():
            try:
                await bot.send_message(user_id, f"🌞 Sizning bugungi foydangiz: {total} ₽\n\nFarmandagi hayvonlaringiz siz uchun pul ishladi! 🐔🐇")
            except:
                pass

# ==================== ASOSIY ====================
async def main():
    await init_db()
    os.environ["TZ"] = "Asia/Tashkent"
    scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)
    scheduler.add_job(auto_collect_income, CronTrigger(hour=0, minute=0, timezone=TASHKENT_TZ), id='daily_income')
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
