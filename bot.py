import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import asyncio

API_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 123456789   # Thay bằng Telegram ID admin

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# =====================
# 📂 Database
# =====================
conn = sqlite3.connect("database.sqlite")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    name TEXT,
    price INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    timestamp TEXT
)
""")
conn.commit()


# =====================
# ⚡ Helpers
# =====================
def add_user(user_id, username):
    cur.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()

def get_balance(user_id):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cur.fetchone()
    return result[0] if result else 0

def update_balance(user_id, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def get_products(category=None):
    if category:
        cur.execute("SELECT id, name, price FROM products WHERE category=?", (category,))
    else:
        cur.execute("SELECT DISTINCT category FROM products")
    return cur.fetchall()


# =====================
# 📌 Start command
# =====================
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    add_user(message.from_user.id, message.from_user.username)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🛒 Cửa hàng", callback_data="shop"))
    kb.add(InlineKeyboardButton("🏦 Nạp tiền", callback_data="deposit"))
    kb.add(InlineKeyboardButton("👤 Thông tin", callback_data="info"))

    if message.from_user.id == ADMIN_ID:
        kb.add(InlineKeyboardButton("🔧 Quản trị", callback_data="admin"))

    balance = get_balance(message.from_user.id)
    await message.answer(f"👋 Xin chào <b>@{message.from_user.username}</b>\n💰 Số dư: {balance} VNĐ", reply_markup=kb)


# =====================
# 🛒 Cửa hàng
# =====================
@dp.callback_query_handler(lambda c: c.data == "shop")
async def shop_menu(callback: types.CallbackQuery):
    categories = get_products()
    kb = InlineKeyboardMarkup()
    for c in categories:
        kb.add(InlineKeyboardButton(c[0], callback_data=f"cat_{c[0]}"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text("🛒 Chọn danh mục:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("cat_"))
async def product_list(callback: types.CallbackQuery):
    category = callback.data.split("_", 1)[1]
    products = get_products(category)

    kb = InlineKeyboardMarkup()
    for p in products:
        kb.add(InlineKeyboardButton(f"{p[1]} - {p[2]} VNĐ", callback_data=f"buy_{p[0]}"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="shop"))
    await callback.message.edit_text(f"📦 Sản phẩm trong {category}:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def buy_product(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    cur.execute("SELECT name, price FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()

    if not product:
        await callback.answer("❌ Sản phẩm không tồn tại", show_alert=True)
        return

    balance = get_balance(callback.from_user.id)
    if balance < product[1]:
        await callback.answer("❌ Số dư không đủ!", show_alert=True)
        return

    # Trừ tiền + lưu lịch sử
    update_balance(callback.from_user.id, -product[1])
    cur.execute("INSERT INTO orders (user_id, product_id, timestamp) VALUES (?, ?, ?)", 
                (callback.from_user.id, product_id, datetime.now().isoformat()))
    conn.commit()

    await callback.message.edit_text(
        f"✅ Bạn đã mua <b>{product[0]}</b>\n💰 Số dư còn lại: {get_balance(callback.from_user.id)} VNĐ"
    )


# =====================
# 🏦 Nạp tiền (chỉ demo QR)
# =====================
@dp.callback_query_handler(lambda c: c.data == "deposit")
async def deposit_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text("🏦 Vui lòng quét QR và gửi bill cho admin để cộng tiền.\n(Chưa tự động hoá)", reply_markup=kb)


# =====================
# 👤 Thông tin
# =====================
@dp.callback_query_handler(lambda c: c.data == "info")
async def user_info(callback: types.CallbackQuery):
    balance = get_balance(callback.from_user.id)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text(f"👤 ID: {callback.from_user.id}\n@{callback.from_user.username}\n💰 Số dư: {balance} VNĐ", reply_markup=kb)


# =====================
# 🔧 Admin menu
# =====================
@dp.callback_query_handler(lambda c: c.data == "admin")
async def admin_menu(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Bạn không có quyền!", show_alert=True)
        return

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👥 Quản lý user", callback_data="admin_users"))
    kb.add(InlineKeyboardButton("📦 Quản lý sản phẩm", callback_data="admin_products"))
    kb.add(InlineKeyboardButton("📜 Lịch sử giao dịch", callback_data="admin_orders"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text("🔧 Menu quản trị:", reply_markup=kb)


# =====================
# ⬅️ Quay lại Main menu
# =====================
@dp.callback_query_handler(lambda c: c.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🛒 Cửa hàng", callback_data="shop"))
    kb.add(InlineKeyboardButton("🏦 Nạp tiền", callback_data="deposit"))
    kb.add(InlineKeyboardButton("👤 Thông tin", callback_data="info"))

    if callback.from_user.id == ADMIN_ID:
        kb.add(InlineKeyboardButton("🔧 Quản trị", callback_data="admin"))

    balance = get_balance(callback.from_user.id)
    await callback.message.edit_text(f"👋 Xin chào <b>@{callback.from_user.username}</b>\n💰 Số dư: {balance} VNĐ", reply_markup=kb)


# =====================
# 🚀 Run bot with asyncio
# =====================
async def main():
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
