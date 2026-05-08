"""
Telegram бот для сбора отзывов о сотрудниках
==========================================
Установка:
    pip install python-telegram-bot==20.7

Запуск:
    python bot.py
"""

import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
BOT_TOKEN  = "8697673336:AAFXrgVPvkrNR4SsRacgUwK-D2L1Dg4NLe0"
MANAGER_ID = 1338569085
HISTORY_FILE = "reviews.json"

# ─── СПИСОК СОТРУДНИКОВ — замените на своих! ──────────────────────────────────
EMPLOYEES = [
    "Узакбаев Айбол",
    "Узакбаев Байбол",
    "Рахметулла Нурсултан",
    "Бикров Шакен",
    "Джуманазаров Нурбек",
]

# ─── ШАГИ ДИАЛОГА ─────────────────────────────────────────────────────────────
SELECT_EMPLOYEE, SELECT_RATING, GET_COMMENT = range(3)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def save_review(data: dict):
    reviews = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            reviews = json.load(f)
    reviews.append(data)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)

def stars(n: int) -> str:
    return "⭐" * n + "☆" * (5 - n)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"👤 {emp}", callback_data=f"emp_{i}")]
        for i, emp in enumerate(EMPLOYEES)
    ]
    keyboard.append([InlineKeyboardButton("📋 История отзывов", callback_data="history")])
    await update.message.reply_text(
        "👋 Добро пожаловать!\n\nВыберите сотрудника:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_EMPLOYEE

async def select_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "history":
        return await show_history(update, context)
    idx = int(query.data.replace("emp_", ""))
    context.user_data["employee"] = EMPLOYEES[idx]
    keyboard = [[InlineKeyboardButton(stars(i), callback_data=f"rate_{i}")] for i in range(1, 6)]
    await query.edit_message_text(
        f"Вы выбрали: *{EMPLOYEES[idx]}*\n\nПоставьте оценку:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_RATING

async def select_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rating = int(query.data.replace("rate_", ""))
    context.user_data["rating"] = rating
    await query.edit_message_text(
        f"Сотрудник: *{context.user_data['employee']}*\n"
        f"Оценка: {stars(rating)} ({rating}/5)\n\n"
        f"Напишите комментарий или отправьте 🎤 голосовое.\n_(Если не хотите — напишите «-»)_",
        parse_mode="Markdown"
    )
    return GET_COMMENT

async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = context.user_data.get("employee", "Неизвестно")
    rating   = context.user_data.get("rating", 0)
    username = update.effective_user.username or "аноним"
    now      = datetime.now().strftime("%d.%m.%Y %H:%M")
    comment_text = update.message.text or ""
    save_review({"date": now, "employee": employee, "rating": rating, "comment": comment_text, "type": "text", "from": username})
    await context.bot.send_message(
        chat_id=MANAGER_ID,
        text=f"📝 *Новый отзыв!*\n\n👤 Сотрудник: *{employee}*\n⭐ Оценка: {stars(rating)} ({rating}/5)\n💬 Комментарий: {comment_text}\n🕐 Время: {now}\n👥 От: @{username}",
        parse_mode="Markdown"
    )
    await update.message.reply_text(f"✅ Спасибо за отзыв!\n\nВы оценили *{employee}* на {stars(rating)}\n\nЕщё один? Нажмите /start", parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def get_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = context.user_data.get("employee", "Неизвестно")
    rating   = context.user_data.get("rating", 0)
    username = update.effective_user.username or "аноним"
    now      = datetime.now().strftime("%d.%m.%Y %H:%M")
    save_review({"date": now, "employee": employee, "rating": rating, "comment": "[голосовое]", "type": "voice", "from": username})
    await context.bot.send_message(
        chat_id=MANAGER_ID,
        text=f"📝 *Новый голосовой отзыв!*\n\n👤 Сотрудник: *{employee}*\n⭐ Оценка: {stars(rating)} ({rating}/5)\n🕐 Время: {now}\n👥 От: @{username}",
        parse_mode="Markdown"
    )
    await context.bot.forward_message(chat_id=MANAGER_ID, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
    await update.message.reply_text(f"✅ Голосовой отзыв получен!\n\nВы оценили *{employee}* на {stars(rating)}\n\nЕщё один? /start", parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not os.path.exists(HISTORY_FILE):
        await query.edit_message_text("📋 История пуста.")
        return ConversationHandler.END
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        reviews = json.load(f)
    if not reviews:
        await query.edit_message_text("📋 История пуста.")
        return ConversationHandler.END
    text = "📋 *Последние отзывы:*\n\n"
    for r in reviews[-10:][::-1]:
        text += f"👤 {r['employee']} — {stars(r['rating'])}\n💬 {r['comment']}\n🕐 {r['date']}\n{'─'*20}\n"
    await query.edit_message_text(text, parse_mode="Markdown")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Нажмите /start чтобы начать снова.")
    context.user_data.clear()
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_EMPLOYEE: [CallbackQueryHandler(select_employee)],
            SELECT_RATING:   [CallbackQueryHandler(select_rating)],
            GET_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment),
                MessageHandler(filters.VOICE, get_voice),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
