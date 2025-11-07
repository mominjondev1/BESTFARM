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

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8268173697:AAHS82mSPPCPgM-3h-8ofzJIah2gkL9fooM"
ADMIN_ID = "5851585402"  # O'zingizning Telegram ID'ingiz
PAYEER_ACCOUNT = "P1062588236"
BOT_NAME = "BEST FARM 🌱"  # Chiroyli nom!

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
                purchased_at TEXT
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
async def get_or_create_user(user_id: int, username: str, ref_by: int = None):
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
    "joja": {"name": "Jo‘ja", "emoji": "🐤", "price": 500},
    "tovuq": {"name": "Tovuq", "emoji": "🐔", "price": 1000},
    "ordak": {"name": "O‘rdak", "emoji": "🦆", "price": 1500},
    "quyon": {"name": "Quyon", "emoji": "🐇", "price": 2500}
}
ANIMAL_LIFETIME_DAYS = 120  # Hayvon faol davri

# ==================== HOLATLAR ====================
class TopUp(StatesGroup):
    amount = State()

class Withdraw(StatesGroup):
    amount = State()
    address = State()

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

# ==================== START ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    ref_by = None
    if len(message.text.split()) > 1:
        ref_arg = message.text.split()[1]
        if ref_arg.startswith("referral_"):
            try:
                ref_by = int(ref_arg.replace("referral_", ""))
            except:
                ref_by = None
    user = await get_or_create_user(message.from_user.id, message.from_user.username, ref_by)
    await message.answer(
        f"✨ {BOT_NAME} ga xush kelibsiz, {user[1]}!\n\n"
        "Siz quyidagi bo'limlardan foydalanishingiz mumkin:",
        reply_markup=main_menu()
    )

# ==================== YORDAM ====================
@dp.message(lambda msg: msg.text == "❓ Yordam")
async def help_section(message: types.Message):
    await message.answer("📞 Yordam uchun admin: @your_admin_username")

# ==================== HAYVONLAR DO'KONI ====================
@dp.message(lambda msg: msg.text == "🐣 Hayvonlar")
async def show_animals(message: types.Message):
    await message.answer(
        f"✨ Hayvonlar doʻkoniga xush kelibsiz, {message.from_user.username or 'do‘st'}!\n\n"
        "Bizning hayvonot do‘konimizda turli hayvonlar va ularning narxlari bilan tanishishingiz mumkin."
    )
    for key, animal in animals_config.items():
        daily_income = int(animal['price'] * 0.01)  # 1%
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Xarid qilish", callback_data=f"buy_{key}"),
             InlineKeyboardButton(text="🔄 Boshqa hayvonlar", callback_data="back_animals")]
        ])
        await message.answer(
            f"{animal['emoji']} {animal['name'].upper()} taʼrifi:\n\n"
            f"💰 Narxi: {animal['price']} soʻm\n"
            f"📈 Kunlik foyda: {daily_income} soʻm (1%)\n"
            f"⏳ Faol davr: {ANIMAL_LIFETIME_DAYS} kun",
            reply_markup=kb
        )

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    animal_key = callback.data.split("_")[1]
    animal = animals_config[animal_key]
    user_id = callback.from_user.id

    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = (await cursor.fetchone())[0]

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
            await callback.message.answer(
                f"🌳 Muvaffaqiyatli tarzda {animal['name'].lower()} xarid qildingiz!\n\n"
                f"Foyda olishni boshlash uchun 👨‍🌾 Mening ferma boʻlimiga oʻting.",
                reply_markup=main_menu()
            )
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Balans to‘ldirish", callback_data="top_up_start")],
                [InlineKeyboardButton(text="🔄 Boshqa hayvonlar", callback_data="back_animals")]
            ])
            await callback.message.answer(
                f"💁‍♂ Hisobingizda mablag‘ yetarli emas!\n\n"
                f"💰 Balansingiz: {balance} soʻm\n"
                f"{animal['emoji']} {animal['name']} narxi: {animal['price']} soʻm.",
                reply_markup=kb
            )
    await callback.answer()

# ==================== MENING FERMA ====================
@dp.message(lambda msg: msg.text == "👨‍🌾 Mening ferma")
async def my_farm(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT animal_type, amount, purchased_at FROM animals WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()

    animal_counts = {k: 0 for k in animals_config}
    for row in rows:
        animal_counts[row[0]] = row[1]

    text = (
        f"👋 Fermangizga xush kelibsiz, {message.from_user.first_name}!\n\n"
        f"👨🏻‍🌾 Sizning hayvonlaringiz:\n\n"
        f"🐤 Jo‘ja: {animal_counts['joja']}\n"
        f"🐔 Tovuq: {animal_counts['tovuq']}\n"
        f"🦆 O‘rdak: {animal_counts['ordak']}\n"
        f"🐇 Quyon: {animal_counts['quyon']}\n\n"
        f"💰 Kunlik foydangizni olish uchun hayvoningiz ustiga bosing:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐤 Jo‘ja", callback_data="collect_joja"),
         InlineKeyboardButton(text="🐔 Tovuq", callback_data="collect_tovuq")],
        [InlineKeyboardButton(text="🦆 O‘rdak", callback_data="collect_ordak"),
         InlineKeyboardButton(text="🐇 Quyon", callback_data="collect_quyon")],
        [InlineKeyboardButton(text="🏘 Bosh sahifa", callback_data="back_home")]
    ])
    await message.answer(text, reply_markup=kb)

# ==================== FOYDA YIG'ISH ====================
@dp.callback_query(lambda c: c.data.startswith("collect_"))
async def collect_income(callback: types.CallbackQuery):
    animal_key = callback.data.split("_")[1]
    if animal_key not in animals_config:
        await callback.answer("❌ Noto‘g‘ri hayvon.")
        return

    user_id = callback.from_user.id
    animal = animals_config[animal_key]
    daily_income = int(animal['price'] * 0.01)
    today = datetime.now().date()

    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute(
            "SELECT amount, purchased_at FROM animals WHERE user_id = ? AND animal_type = ?",
            (user_id, animal_key)
        )
        row = await cursor.fetchone()

        if not row or row[0] <= 0:
            await callback.message.answer(
                f"💁‍♂ Sizda {animal['name'].lower()} mavjud emas!\n\n"
                f"💸 Hayvonlar boʻlimidan {animal['name'].lower()} xarid qiling!",
                reply_markup=main_menu()
            )
            return

        purchased_at = datetime.strptime(row[1], "%Y-%m-%d").date()
        expiry_date = purchased_at + timedelta(days=ANIMAL_LIFETIME_DAYS)

        if today > expiry_date:
            # Hayvon muddati tugagan
            await db.execute("DELETE FROM animals WHERE user_id = ? AND animal_type = ?", (user_id, animal_key))
            await db.commit()
            await callback.message.answer(
                f"🌳 Sizning {animal['name'].lower()}ingiz muddati tugadi va endi mavjud emas.",
                reply_markup=main_menu()
            )
            return

        # Foyda hisoblash
        total_income = daily_income * row[0]
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_income, user_id))
        await db.execute("INSERT INTO transactions (user_id, description, amount, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, f"{animal['name']}dan foyda", total_income, datetime.now().strftime("%d.%m.%Y %H:%M")))
        await db.commit()
        await callback.message.answer(
            f"🟢 Hisobingiz +{total_income} soʻmga oʻzgartirildi.\n\n"
            f"🎉 Siz {animal['name'].lower()}(lar)dan {total_income} soʻm foyda oldingiz!",
            reply_markup=main_menu()
        )
    await callback.answer()

# ==================== HISOBIM ====================
@dp.message(lambda msg: msg.text == "💰 Hisobim")
async def my_account(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT username, balance, referrals FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        cursor = await db.execute("SELECT description, amount, timestamp FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        txs = await cursor.fetchall()

    report = ""
    for desc, amount, ts in txs:
        report += f"🌳 {user[0]}, [{ts}]\n{desc}\nBalans: {user[1]} soʻm\n\n"

    report += f"🆔: {user_id}\n💵 Balans: {user[1]} soʻm\n🫂 Referallar: {user[2]} ta"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Hisobni to‘ldirish", callback_data="top_up_start")],
        [InlineKeyboardButton(text="📤 Hisobdan yechish", callback_data="withdraw_start")]
    ])
    await message.answer(report, reply_markup=kb)

# ==================== REFERAL ====================
@dp.message(lambda msg: msg.text == "🤝 Referal")
async def referral_info(message: types.Message):
    ref_link = f"https://t.me/your_bot_username?start=referral_{message.from_user.id}"
    await message.answer(
        "🔗 Sizning shaxsiy referal havolangiz:\n\n"
        f"`{ref_link}`\n\n"
        "Do‘stlaringiz ushbu havola orqali kirsa, ular sizning referalingiz bo‘ladi.",
        parse_mode="Markdown"
    )

# ==================== PUL TIZIMI (TOP-UP / WITHDRAW) ====================
# (Bu qism o'zgarmagan — oldingi kodni saqlab qolamiz)

@dp.callback_query(lambda c: c.data == "top_up_start")
async def top_up_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("💰 Hisobingizni qancha summa bilan to‘ldirmoqchisiz?\n\n"
                                  "📌 Namuna: 500\n"
                                  "❗ Minimal summa: 500 so‘m")
    await state.set_state(TopUp.amount)
    await callback.answer()

@dp.message(TopUp.amount)
async def process_top_up_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 500:
            await message.answer("❗ Minimal to‘lov summasi: 500 so‘m.\n\nIltimos, qaytadan kiriting:")
            return
        link = f"https://payeer.com/ru/account/send/?to={PAYEER_ACCOUNT}&sum={amount}&currency=UZS"
        await message.answer(
            f"✅ To‘lov uchun quyidagi havolaga o‘ting:\n\n{link}\n\n"
            f"🔹 To‘lovni amalga oshirgandan so‘ng, admin hisobingizni qo‘lda to‘ldiradi.\n"
            f"🧾 To‘lov ID yoki skrinshotni admin (@your_admin_username) ga yuboring."
        )
        await bot.send_message(ADMIN_ID, f"🆕 Yangi to‘lov so‘rovi:\nFoydalanuvchi: @{message.from_user.username} (ID: {message.from_user.id})\nSumma: {amount} so‘m")
        await state.clear()
    except ValueError:
        await message.answer("❌ Noto‘g‘ri summa. Faqat raqam kiriting (masalan: 500):")

@dp.callback_query(lambda c: c.data == "withdraw_start")
async def withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect("farm_bot.db") as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = (await cursor.fetchone())[0]
    await callback.message.answer(
        f"💁‍♂ Pul chiqarib olishning eng kam miqdori: 250 soʻm\n\n"
        f"Sizning balans: {balance} soʻm.\n\n"
        "❓ Qancha pul yechmoqchisiz?"
    )
    await state.set_state(Withdraw.amount)
    await callback.answer()

@dp.message(Withdraw.amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        user_id = message.from_user.id
        if amount < 250:
            await message.answer("❗ Minimal yechish summasi: 250 so‘m.\n\nIltimos, qaytadan kiriting:")
            return
        async with aiosqlite.connect("farm_bot.db") as db:
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = (await cursor.fetchone())[0]
        if amount > balance:
            await message.answer(f"🚫 Hisobingizda yetarli mablag‘ yo‘q!\nSizning balans: {balance} so‘m.")
            return
        await state.update_data(amount=amount)
        await message.answer("📬 Iltimos, Payeer manzilingizni kiriting:\n\nMasalan: P1234567890")
        await state.set_state(Withdraw.address)
    except ValueError:
        await message.answer("❌ Noto‘g‘ri summa. Faqat raqam kiriting:")

@dp.message(Withdraw.address)
async def process_withdraw_address(message: types.Message, state: FSMContext):
    address = message.text.strip()
    if not address.startswith("P") or len(address) < 10:
        await message.answer("❌ Noto‘g‘ri Payeer manzil. To‘g‘ri manzil: P1234567890\n\nQaytadan kiriting:")
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
        f"💸 Yangi pul yechish so‘rovi!\n\n"
        f"👤 Foydalanuvchi: @{username} (ID: {user_id})\n"
        f"💰 Summa: {amount} so‘m\n"
        f"📬 Payeer: {address}"
    )

    await message.answer(
        "✅ So‘rov qabul qilindi!\n\n"
        "Admin tez orada pulingizni yuboradi. Iltimos, kuting."
    )
    await state.clear()

@dp.callback_query(lambda c: c.data == "back_home")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.answer("🏘 Bosh menyu:", reply_markup=main_menu())
    await callback.answer()

# ==================== ASOSIY ====================
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())