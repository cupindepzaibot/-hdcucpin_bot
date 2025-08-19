import logging
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import Message, CallbackQuery
from aiogram.client import DefaultBotProperties
from datetime import datetime
import sqlite3

API_TOKEN = "8263184362:AAF53GdU6kyOyVJeLc_bYTHtivjRBHL0xWA"
ADMIN_ID = 7903231043   # Thay bằng Telegram ID admin của bạn

logging.basicConfig(level=logging.INFO)

# Khởi tạo Bot với các thuộc tính mặc định
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

# Khởi tạo Dispatcher
dp = Dispatcher()
dp.bot = bot

# =======================
# 📂 Database
# =======================
conn = sqlite3.connect("database.sqlite")
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0
)""")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    name TEXT,
    price INTEGER
)""")
conn.commit()

cur.execute("""CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    timestamp TEXT
)""")
conn.commit()

# =======================
# ⚡ Helpers
# =======================
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

# =======================
# 📌 Start command
# =======================
@dp.message_handler(commands=["start"])
async def start_cmd(message: Message):
    add_user(message.from_user.id, message.from_user.username)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🛒 Cửa hàng", callback_data="shop"))
    kb.add(InlineKeyboardButton("🏦 Nạp tiền", callback_data="deposit"))
    kb.add(InlineKeyboardButton("👤 Thông tin", callback_data="info"))

    if message.from_user.id == ADMIN_ID:
        kb.add(InlineKeyboardButton("🔧 Quản trị", callback_data="admin"))

    balance = get_balance(message.from_user.id)
    await message.answer(f"👋 Xin chào <b>@{message.from_user.username}</b>\n💰 Số dư: {balance} VNĐ", reply_markup=kb)

# =======================
# 🛒 Cửa hàng
# =======================
@dp.callback_query_handler(lambda c: c.data == "shop")
async def shop_menu(callback: CallbackQuery):
    categories = get_products()
    kb = InlineKeyboardMarkup()
    for c in categories:
        kb.add(InlineKeyboardButton(c[0], callback_data=f"cat_{c[0]}"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text("🛒 Chọn danh mục:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("cat_"))
async def product_list(callback: CallbackQuery):
    category = callback.data.split("_", 1)[1]
    products = get_products(category)

    kb = InlineKeyboardMarkup()
    for p in products:
        kb.add(InlineKeyboardButton(f"{p[1]} - {p[2]} VNĐ", callback_data=f"buy_{p[0]}"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="shop"))
    await callback.message.edit_text(f"📦 Sản phẩm trong {category}:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
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

# =======================
# 🏦 Nạp tiền (chỉ demo QR)
# =======================
@dp.callback_query_handler(lambda c: c.data == "deposit")
async def deposit_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text("🏦 Vui lòng quét QR và gửi bill cho admin để cộng tiền.\n(Chưa tự động hoá)", reply_markup=kb)

# =======================
# 👤 Thông tin
# =======================
@dp.callback_query_handler(lambda c: c.data == "info")
async def user_info(callback: CallbackQuery):
    balance = get_balance(callback.from_user.id)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text(f"👤 ID: {callback.from_user.id}\n@{callback.from_user.username}\n💰 Số dư: {balance} VNĐ", reply_markup=kb)

# =======================
# 🔧 Admin menu
# =======================
@dp.callback_query_handler(lambda c: c.data == "admin")
async def admin_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📊 Thống kê người dùng", callback_data="admin_stats"))
    kb.add(InlineKeyboardButton("🛠 Quản lý sản phẩm", callback_data="admin_products"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main"))
    await callback.message.edit_text("🔧 Menu quản trị:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    product_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders")
    order_count = cur.fetchone()[0]
    await callback.message.edit_text(
        f"📊 Thống kê:\n"
        f"👥 Người dùng: {user_count}\n"
        f"📦 Sản phẩm: {product_count}\n"
        f"🛒 Đơn hàng: {order_count}"
    )

@dp.callback_query_handler(lambda c: c.data == "admin_products")
async def admin_products(callback: CallbackQuery):
    categories = get_products()
    kb = InlineKeyboardMarkup()
    for c in categories:
        kb.add(InlineKeyboardButton(c[0], callback_data=f"admin_cat_{c[0]}"))
    kb.add(InlineKeyboardButton("➕ Thêm sản phẩm", callback_data="admin_add_product"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="admin"))
    await callback.message.edit_text("🛠 Quản lý sản phẩm:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("admin_cat_"))
async def admin_category(callback: CallbackQuery):
    category = callback.data.split("_", 2)[2]
    products = get_products(category)
    kb = InlineKeyboardMarkup()
    for p in products:
        kb.add(InlineKeyboardButton(f"{p[1]} - {p[2]} VNĐ", callback_data=f"admin_edit_{p[0]}"))
    kb.add(InlineKeyboardButton("➕ Thêm sản phẩm", callback_data="admin_add_product"))
    kb.add(InlineKeyboardButton("⬅️ Quay lại", callback_data="admin_products"))
    await callback.message.edit_text(f"🛠 Sản phẩm trong {category}:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery):
    await callback.message.edit_text("📝 Vui lòng gửi thông tin sản phẩm theo định dạng:\n\n"
                                      "<b>Tên sản phẩm</b>\n"
                                      "<b>Danh mục</b>\n"
                                      "<b>Giá (VNĐ)</b>")

@dp.message_handler(lambda message: message.text.count("\n") == 2, state="*")
async def process_new_product(message: Message):
    try:
        name, category, price = message.text.split("\n")
        price = int(price.strip().replace("VNĐ", "").replace(",", "").strip())
        cur.execute("INSERT INTO products (name, category, price) VALUES (?, ?, ?)", (name, category, price))
        conn.commit()
        await message.answer(f"✅ Đã thêm sản phẩm: {name} ({category}) - {price} VNĐ")
    except ValueError:
        await message.answer("❌ Định dạng không hợp lệ. Vui lòng gửi lại theo định dạng:\n\n"
                             "<b>Tên sản phẩm</b>\n"
                             "<b>Danh mục</b>\n"
                             "<b>Giá (VNĐ)</b>")

@dp.callback_query_handler(lambda c: c.data.startswith("admin_edit_"))
async def admin_edit_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    cur.execute("SELECT name, category, price FROM products WHERE id=?", (product_id,))
    product = cur.fetchone()
    if product:
        await callback.message.edit_text(f"🛠 Chỉnh sửa sản phẩm:\n\n"
                                         f"<b>Tên:</b> {product[0]}\n"
                                         f"<b>Danh mục:</b> {product[1]}\n"
                                         f"<b>Giá:</b> {product[2]} VNĐ")
    else:
        await callback.message.edit_text("❌ Sản phẩm không tồn tại.")

@dp.callback_query_handler(lambda c: c.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🛒 Cửa hàng", callback_data="shop"))
    kb.add(InlineKeyboardButton("🏦 Nạp tiền", callback_data="deposit"))
    kb.add(InlineKeyboardButton("👤 Thông tin", callback_data="info"))
    if callback.from_user.id == ADMIN_ID:
        kb.add(InlineKeyboardButton("🔧 Quản trị", callback_data="admin"))
    balance = get_balance(callback.from_user.id)
    await callback.message.edit_text(f"👋 Xin chào <b>@{callback.from_user.username}</b>\n💰 Số dư: {balance} VNĐ", reply_markup=kb)

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
