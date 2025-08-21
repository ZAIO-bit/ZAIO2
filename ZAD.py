#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
بوت تليجرام المتطور - الإصدار 33.0 (إصلاح شامل لمشكلة الاتصال)
"""

import os
import logging
import sqlite3
import uuid
from pathlib import Path
import asyncio

# مكتبات تليجرام
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# مكتبات الخادم (FastAPI)
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

# مكتبة لحل مشكلة asyncio
import nest_asyncio

# ============================================================================
# 1. الإعدادات والتكوين
# ============================================================================

BOT_TOKEN = "7374830859:AAFJkTZe7Xm6TIh1D6lVdX6i2_iSq9WPmtg"
ADMIN_CHAT_ID = 6739658332
DEVELOPER_USERNAME = "c8s8sx"
BASE_URL = "https://zaio5.pythonanywhere.com/" # تأكد من أنه رابط PythonAnywhere الصحيح

# تحديد المسارات المطلقة لضمان عملها في كل مكان
HOME_DIRECTORY = os.path.expanduser('~') # /home/ZAIO5
DATABASE_PATH = os.path.join(HOME_DIRECTORY, "telegram_file_bot.db")
UPLOAD_FOLDER = os.path.join(HOME_DIRECTORY, "uploads")

MAX_FILE_SIZE_FREE = 200 * 1024 * 1024
MAX_FILE_SIZE_PREMIUM = 2 * 1024 * 1024 * 1024
MAX_FILES_FREE = 20
MAX_FILES_PREMIUM = 500
FILES_PER_PAGE = 5

# حالات المحادثة
BROADCAST_TYPING, ADMIN_SEARCH_USER = range(2)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(os.path.join(HOME_DIRECTORY, "telegram_bot.log")), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ============================================================================
# 2. إدارة قاعدة البيانات (مع مسارات مطلقة)
# ============================================================================
class DatabaseManager:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                    subscription_type TEXT DEFAULT 'free', is_admin INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0, storage_used INTEGER DEFAULT 0
                )
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL,
                    original_name TEXT NOT NULL, stored_name TEXT NOT NULL, file_size INTEGER NOT NULL,
                    upload_date TEXT DEFAULT CURRENT_TIMESTAMP, download_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """
            )
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, is_admin, subscription_type) VALUES (?, 1, 'premium')",
                (ADMIN_CHAT_ID,),
            )
            cursor.execute(
                "UPDATE users SET is_admin = 1, is_banned = 0 WHERE user_id = ?",
                (ADMIN_CHAT_ID,),
            )
            conn.commit()
        logger.info(f"Database initialized successfully at {self.db_path}")

    def add_user(self, user_id, username, first_name):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name),
            )
            conn.commit()

    def get_user(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None

    def find_user(self, query: str):
        with self.get_connection() as conn:
            if query.isdigit():
                cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (int(query),))
            else:
                cursor = conn.execute(
                    "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ?",
                    (f"%{query}%", f"%{query}%"),
                )
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None

    def set_user_ban_status(self, user_id: int, is_banned: bool):
        with self.get_connection() as conn:
            conn.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if is_banned else 0, user_id))
            conn.commit()

    def set_user_subscription(self, user_id: int, sub_type: str):
        with self.get_connection() as conn:
            conn.execute("UPDATE users SET subscription_type = ? WHERE user_id = ?", (sub_type, user_id))
            conn.commit()

    def check_user_limits(self, user_id):
        user = self.get_user(user_id)
        if not user: return {"error": "User not found"}
        if user["is_banned"]: return {"error": "أنت محظور 🚫"}
        is_premium = user["subscription_type"] == "premium" or user["is_admin"] == 1
        max_file_size = MAX_FILE_SIZE_PREMIUM if is_premium else MAX_FILE_SIZE_FREE
        max_files = MAX_FILES_PREMIUM if is_premium else MAX_FILES_FREE
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM files WHERE user_id = ?", (user_id,))
            current_files = cursor.fetchone()[0]
        return {
            "is_premium": is_premium, "max_file_size": max_file_size,
            "max_files": max_files, "current_files": current_files,
            "can_upload": current_files < max_files,
        }

    def add_file(self, user_id, file_data):
        file_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO files (file_id, user_id, original_name, stored_name, file_size) VALUES (?, ?, ?, ?, ?)",
                (file_id, user_id, file_data["original_name"], file_data["stored_name"], file_data["file_size"]),
            )
            conn.execute(
                "UPDATE users SET storage_used = storage_used + ? WHERE user_id = ?",
                (file_data["file_size"], user_id),
            )
            conn.commit()
        return file_id

    def get_file(self, file_id):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM files WHERE file_id = ?", (file_id,))
            file_data = cursor.fetchone()
            return dict(file_data) if file_data else None

    def get_user_files(self, user_id, page: int = 0):
        with self.get_connection() as conn:
            offset = page * FILES_PER_PAGE
            cursor = conn.execute(
                "SELECT * FROM files WHERE user_id = ? ORDER BY upload_date DESC LIMIT ? OFFSET ?",
                (user_id, FILES_PER_PAGE, offset),
            )
            files = [dict(row) for row in cursor.fetchall()]
            count_cursor = conn.execute("SELECT COUNT(*) FROM files WHERE user_id = ?", (user_id,))
            total_files = count_cursor.fetchone()[0]
            return files, total_files

    def delete_file(self, file_id, user_id):
        with self.get_connection() as conn:
            file_data = self.get_file(file_id)
            user = self.get_user(user_id)
            is_admin_user = user and user["is_admin"] == 1
            if not file_data or (file_data["user_id"] != user_id and not is_admin_user): return False
            
            file_path = Path(UPLOAD_FOLDER) / file_data["stored_name"]
            if file_path.exists(): file_path.unlink()
            
            conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
            conn.execute(
                "UPDATE users SET storage_used = storage_used - ? WHERE user_id = ?",
                (file_data["file_size"], file_data["user_id"]),
            )
            conn.commit()
            return True

    def get_admin_stats(self):
        with self.get_connection() as conn:
            stats = {}
            stats["total_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            stats["banned_users"] = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
            stats["premium_users"] = conn.execute("SELECT COUNT(*) FROM users WHERE subscription_type = 'premium'").fetchone()[0]
            stats["total_files"] = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            stats["total_storage"] = (conn.execute("SELECT SUM(file_size) FROM files").fetchone()[0] or 0)
            return stats

    def get_all_user_ids(self):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT user_id FROM users WHERE is_banned = 0")
            return [row["user_id"] for row in cursor.fetchall()]

# إنشاء نسخة واحدة من مدير قاعدة البيانات ليتم استخدامها في كل مكان
db = DatabaseManager()

# ============================================================================
# 3. دوال المساعدة والأزرار
# ============================================================================
def get_file_size_string(size_bytes):
    if not size_bytes: return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    size_in_bytes = float(size_bytes)
    while size_in_bytes >= 1024 and i < len(size_names) - 1:
        size_in_bytes /= 1024.0
        i += 1
    return f"{size_in_bytes:.1f} {size_names[i]}"

def is_admin(user_id: int) -> bool:
    user = db.get_user(user_id)
    return user and user["is_admin"] == 1

def create_main_menu_keyboard(user_id: int):
    keyboard = [
        [InlineKeyboardButton("🗂️ ملفاتي", callback_data="my_files_0"), InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("ℹ️ حول البوت", callback_data="about")],
    ]
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 لوحة تحكم الأدمن", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def create_admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 إحصائيات النظام", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users_start")],
        [InlineKeyboardButton("📣 إذاعة رسالة", callback_data="broadcast_start")],
        [InlineKeyboardButton("🏠 العودة للقائمة الرئيسية", callback_data="main_menu")],
    ])

# ============================================================================
# 4. معالجات البوت (Handlers)
# ============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    user_db_info = db.get_user(user.id)
    if user_db_info and user_db_info["is_banned"]:
        await update.message.reply_text("❌ أنت محظور من استخدام هذا البوت.")
        return
    welcome_text = f"🚀 **أهلاً بك يا {user.first_name}!**\n\nأنا بوت رفع الملفات الخاص بك. أرسل لي أي ملف، أو استخدم الأزرار أدناه للتحكم."
    keyboard = create_main_menu_keyboard(user.id)
    await update.message.reply_text(text=welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    limits = db.check_user_limits(user_id)
    if "error" in limits:
        await update.message.reply_text(f"❌ لا يمكنك الرفع: {limits['error']}")
        return
    if not limits["can_upload"]:
        await update.message.reply_text(f"❌ لقد وصلت إلى الحد الأقصى للملفات ({limits['max_files']} ملف).")
        return
    document = update.message.document
    if document.file_size > limits["max_file_size"]:
        await update.message.reply_text(f"❌ الملف كبير جداً! الحد الأقصى هو {get_file_size_string(limits['max_file_size'])}.")
        return
    progress_message = await update.message.reply_text(f"⏳ جارٍ التحضير لرفع: `{document.file_name}`...", parse_mode=ParseMode.MARKDOWN)
    try:
        file = await context.bot.get_file(document.file_id)
        secure_name = f"{uuid.uuid4()}_{os.path.basename(document.file_name)}"
        file_path = os.path.join(UPLOAD_FOLDER, secure_name)
        await progress_message.edit_text("📥 جاري تنزيل الملف إلى الخادم...", parse_mode=ParseMode.MARKDOWN)
        await file.download_to_drive(file_path)
        file_data = {"original_name": document.file_name, "stored_name": secure_name, "file_size": document.file_size}
        file_id = db.add_file(user_id, file_data)
        if file_id:
            link = f"{BASE_URL}/download/{file_id}"
            success_text = (f"✅ **تم الرفع بنجاح!**\n\n📄 **الملف:** `{document.file_name}`\n🗂️ **الحجم:** {get_file_size_string(document.file_size)}\n\n🔗 **رابط التحميل المباشر:**\n`{link}`")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ حذف الملف", callback_data=f"delete_confirm_{file_id}")], [InlineKeyboardButton("🏠 العودة للقائمة", callback_data="main_menu")]])
            await progress_message.edit_text(success_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        else:
            if os.path.exists(file_path): os.remove(file_path)
            await progress_message.edit_text("❌ حدث خطأ أثناء حفظ بيانات الملف في قاعدة البيانات.")
    except Exception as e:
        logger.error(f"Upload error for user {user_id}: {e}", exc_info=True)
        await progress_message.edit_text(f"❌ حدث خطأ فني أثناء الرفع. تم تسجيل الخطأ.")

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    welcome_text = f"🚀 **أهلاً بك يا {query.from_user.first_name}!**\n\nاستخدم الأزرار أدناه لإدارة ملفاتك."
    keyboard = create_main_menu_keyboard(user_id)
    await query.edit_message_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)

async def my_files_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    page = int(query.data.split("_")[2])
    files, total_files = db.get_user_files(user_id, page=page)
    if not files and page == 0:
        await query.edit_message_text("📂 لا توجد لديك أي ملفات مرفوعة بعد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 رجوع", callback_data="main_menu")]]))
        return
    text = f"🗂️ **ملفاتك (صفحة {page + 1}):**\n\n"
    keyboard_buttons = []
    for file in files:
        text += f"📄 `{file['original_name']}` ({get_file_size_string(file['file_size'])})\n"
        keyboard_buttons.append([InlineKeyboardButton(f"🗑️ حذف {file['original_name'][:20]}...", callback_data=f"delete_confirm_{file['file_id']}")])
    nav_buttons = []
    if page > 0: nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"my_files_{page - 1}"))
    if (page + 1) * FILES_PER_PAGE < total_files: nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"my_files_{page + 1}"))
    if nav_buttons: keyboard_buttons.append(nav_buttons)
    keyboard_buttons.append([InlineKeyboardButton("🏠 رجوع للقائمة الرئيسية", callback_data="main_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons), parse_mode=ParseMode.MARKDOWN)

async def delete_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_id = query.data.split("_")[2]
    file_data = db.get_file(file_id)
    if not file_data:
        await query.edit_message_text("❌ الملف لم يعد موجوداً.", reply_markup=create_main_menu_keyboard(query.from_user.id))
        return
    text = f"⚠️ **تأكيد الحذف** ⚠️\n\nهل أنت متأكد أنك تريد حذف الملف:\n`{file_data['original_name']}`؟\n\n**لا يمكن التراجع عن هذا الإجراء!**"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ نعم، احذف", callback_data=f"delete_do_{file_id}"), InlineKeyboardButton("❌ لا، تراجع", callback_data="my_files_0")]])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def delete_do_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    file_id = query.data.split("_")[2]
    user_id = query.from_user.id
    file_data = db.get_file(file_id)
    if not file_data:
        await query.edit_message_text("❌ لم يتم العثور على الملف.", reply_markup=create_main_menu_keyboard(user_id))
        return
    if db.delete_file(file_id, user_id):
        await query.edit_message_text(f"🗑️ تم حذف الملف `{file_data['original_name']}` بنجاح.", reply_markup=create_main_menu_keyboard(user_id), parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text("❌ حدث خطأ أثناء الحذف.", reply_markup=create_main_menu_keyboard(user_id))

async def my_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    limits = db.check_user_limits(user_id)
    _, total_files = db.get_user_files(user_id)
    text = (f"📊 **إحصائيات حسابك** 📊\n\n👤 **المستخدم:** {query.from_user.first_name}\n🆔 **ID:** `{user_id}`\n⭐️ **نوع الاشتراك:** {'مدفوع' if limits['is_premium'] else 'مجاني'}\n\n🗂️ **عدد الملفات:** {total_files} / {limits['max_files']}\n💾 **المساحة المستخدمة:** {get_file_size_string(user_data['storage_used'])}\n📏 **أقصى حجم للملف الواحد:** {get_file_size_string(limits['max_file_size'])}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 رجوع", callback_data="main_menu")]])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def about_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (f"ℹ️ **حول البوت** ℹ️\n\nهذا البوت تم تطويره لمساعدتك في رفع وتخزين ومشاركة ملفاتك بسهولة وأمان.\n\n👤 **المطور:** @{DEVELOPER_USERNAME}\n⚙️ **الإصدار:** 33.0 (مستقر)\n\nشكراً لاستخدامك البوت!")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 رجوع", callback_data="main_menu")]])
    await query.edit_message_text(text, reply_markup=keyboard)

# ============================================================================
# 5. معالجات الأدمن
# ============================================================================
async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.answer("❌ ليس لديك صلاحية الوصول.", show_alert=True)
        return
    text = "👑 **لوحة تحكم الأدمن** 👑\n\nأهلاً بك أيها المدير. اختر أحد الخيارات أدناه:"
    await query.edit_message_text(text, reply_markup=create_admin_panel_keyboard())

async def admin_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    stats = db.get_admin_stats()
    text = (f"📈 **إحصائيات النظام** 📈\n\n👥 **إجمالي المستخدمين:** {stats['total_users']}\n💎 **المستخدمون المدفوعون:** {stats['premium_users']}\n🚫 **المستخدمون المحظورون:** {stats['banned_users']}\n\n📂 **إجمالي الملفات:** {stats['total_files']}\n💾 **إجمالي المساحة المستخدمة:** {get_file_size_string(stats['total_storage'])}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("👑 رجوع للوحة التحكم", callback_data="admin_panel")]])
    await query.edit_message_text(text, reply_markup=keyboard)

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text("📣 **قسم الإذاعة**\n\nأرسل الآن الرسالة التي تريد إذاعتها. للإلغاء، اكتب /cancel.")
    return BROADCAST_TYPING

async def broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    message_to_broadcast = update.message.text
    user_ids = db.get_all_user_ids()
    await update.message.reply_text(f"⏳ جارٍ بدء الإذاعة إلى {len(user_ids)} مستخدم...")
    sent_count, failed_count = 0, 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_to_broadcast)
            sent_count += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            failed_count += 1
    await update.message.reply_text(f"✅ **اكتملت الإذاعة!**\n\n- تم الإرسال بنجاح إلى: {sent_count} مستخدم.\n- فشل الإرسال إلى: {failed_count} مستخدم.")
    await start(update, context)
    return ConversationHandler.END

async def admin_search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    await query.edit_message_text("👥 **إدارة المستخدمين**\n\nأرسل اسم المستخدم أو الـ ID للبحث. للإلغاء، اكتب /cancel.")
    return ADMIN_SEARCH_USER

async def admin_search_user_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    user_data = db.find_user(update.message.text)
    if not user_data:
        await update.message.reply_text("❌ لم يتم العثور على مستخدم. حاول مرة أخرى أو /cancel.")
        return ADMIN_SEARCH_USER
    target_user_id = user_data['user_id']
    _, total_files = db.get_user_files(target_user_id)
    text = (f"👤 **ملف المستخدم:** {user_data['first_name']}\n🆔 **ID:** `{user_data['user_id']}`\n🔖 **Username:** @{user_data['username']}\n⭐️ **الاشتراك:** {user_data['subscription_type']}\n🚫 **الحالة:** {'محظور' if user_data['is_banned'] else 'نشط'}\n📂 **عدد الملفات:** {total_files}")
    ban_text = "🚫 حظر" if not user_data['is_banned'] else "✅ رفع الحظر"
    sub_text = "💎 ترقية لمدفوع" if user_data['subscription_type'] == 'free' else "⬇️ تخفيض لمجاني"
    keyboard = [[InlineKeyboardButton(ban_text, callback_data=f"admin_ban_{target_user_id}")], [InlineKeyboardButton(sub_text, callback_data=f"admin_sub_{target_user_id}")], [InlineKeyboardButton("👑 رجوع للوحة التحكم", callback_data="admin_panel")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def admin_manage_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id): return
    parts = query.data.split("_")
    action, target_user_id = parts[1], int(parts[2])
    user_data = db.get_user(target_user_id)
    if not user_data:
        await query.edit_message_text("❌ المستخدم لم يعد موجوداً.")
        return
    if action == "ban":
        new_status = not user_data['is_banned']
        db.set_user_ban_status(target_user_id, new_status)
        await query.answer(f"✅ تم {'حظر' if new_status else 'رفع الحظر عن'} المستخدم.", show_alert=True)
    elif action == "sub":
        new_sub = "premium" if user_data['subscription_type'] == 'free' else 'free'
        db.set_user_subscription(target_user_id, new_sub)
        await query.answer(f"✅ تم {'ترقية' if new_sub == 'premium' else 'تخفيض'} اشتراك المستخدم.", show_alert=True)
    await query.edit_message_text("✅ تم تحديث بيانات المستخدم. ابحث عنه مجدداً لرؤية التغييرات.", reply_markup=create_admin_panel_keyboard())

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.", reply_markup=create_main_menu_keyboard(update.effective_user.id))
    return ConversationHandler.END

# ============================================================================
# 6. تعريف وتشغيل البوت وواجهة التحميل (API)
# ============================================================================

# --- الجزء الخاص بواجهة التحميل (API) ---
api = FastAPI()

@api.get("/download/{file_id}")
async def download_file_endpoint(file_id: str):
    file_data = db.get_file(file_id)
    if not file_data:
        raise HTTPException(status_code=404, detail="الملف غير موجود أو تم حذفه.")
    file_path = Path(UPLOAD_FOLDER) / file_data["stored_name"]
    if not file_path.is_file():
        logger.error(f"File not found on disk: {file_path}")
        raise HTTPException(status_code=404, detail="الملف غير موجود على الخادم.")
    return FileResponse(path=file_path, filename=file_data["original_name"], media_type="application/octet-stream")

# --- الجزء الخاص بالبوت (سيتم تشغيله يدوياً) ---
async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_start, pattern="^broadcast_start$"), CallbackQueryHandler(admin_search_user_start, pattern="^admin_users_start$")],
        states={
            BROADCAST_TYPING: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_receive)],
            ADMIN_SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_search_user_receive)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(main_menu_handler, pattern='^main_menu$'))
    application.add_handler(CallbackQueryHandler(my_files_handler, pattern=r'^my_files_'))
    application.add_handler(CallbackQueryHandler(delete_confirm_handler, pattern=r'^delete_confirm_'))
    application.add_handler(CallbackQueryHandler(delete_do_handler, pattern=r'^delete_do_'))
    application.add_handler(CallbackQueryHandler(my_stats_handler, pattern='^my_stats$'))
    application.add_handler(CallbackQueryHandler(about_handler, pattern='^about$'))
    application.add_handler(CallbackQueryHandler(admin_panel_handler, pattern='^admin_panel$'))
    application.add_handler(CallbackQueryHandler(admin_stats_handler, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(admin_manage_user_handler, pattern=r'^admin_(ban|sub)_'))
    logger.info
