
"""
Telegram бот для сбора отзывов о сотрудниках
==========================================
Установка:
    pip install python-telegram-bot==20.7

Запуск:
    python bot.py
"""

import os, json, logging, asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN    = "8697673336:AAFXrgVPvkrNR4SsRacgUwK-D2LlDg4NLe0"
MANAGER_ID   = 1338569085
HISTORY_FILE = "reviews.json"

# ─── ГРУППЫ И СОТРУДНИКИ ──────────────────────────────────────────────────────
GROUPS = {
    "Аскарова": [
        "Узакбаев Айбол",
        "Узакбаев Байбол",
        "Рахметулла Нурсултан",
        "Копбаев Елжан",
    ],
    "Сулиманова": [
        "Бикоров Габит",
        "Бакиров Шакен",
        "Махамбет Нуржас",
        "Рыстай Уласкан",
        "Райф Арсен",
    ],
    "Аса": [
        "Узакбаев Ербол",
        "Жандос Нурзат",
        "Дуанбай Медерхан",
    ],
}

SELECT_GROUP, SELECT_EMPLOYEE, SELECT_RATING, GET_COMMENT = range(4)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)


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


# ─── /start → выбор группы ────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(f"🏢 {group}", callback_data=f"grp_{group}")]
        for group in GROUPS
    ]
    keyboard.append([InlineKeyboardButton("📋 История отзывов", callback_data="history")])
    await update.message.reply_text(
        "👋 Добро пожаловать!\n\nВыберите отдел:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_GROUP


# ─── Выбор группы → показать сотрудников ──────────────────────────────────────
async def select_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "history":
        return await show_history(update, context)

    group = query.data.replace("grp_", "")
    context.user_data["group"] = group
    employees = GROUPS[group]

    keyboard = [
        [InlineKeyboardButton(f"👤 {emp}", callback_data=f"emp_{i}")]
        for i, emp in enumerate(employees)
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_groups")])

    await query.edit_message_text(
        f"🏢 Отдел: *{group}*\n\nВыберите сотрудника:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_EMPLOYEE


# ─── Выбор сотрудника → оценка ────────────────────────────────────────────────
async def select_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_groups":
        keyboard = [
            [InlineKeyboardButton(f"🏢 {group}", callback_data=f"grp_{group}")]
            for group in GROUPS
        ]
        keyboard.append([InlineKeyboardButton("📋 История отзывов", callback_data="history")])
        await query.edit_message_text(
            "Выберите отдел:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_GROUP

    group = context.user_data["group"]
    idx = int(query.data.replace("emp_", ""))
    employee = GROUPS[group][idx]
    context.user_data["employee"] = employee

    keyboard = [[InlineKeyboardButton(stars(i), callback_data=f"rate_{i}")] for i in range(1, 6)]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_employees")])

    await query.edit_message_text(
        f"👤 Сотрудник: *{employee}*\n\nПоставьте оценку:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_RATING


# ─── Выбор оценки → комментарий ───────────────────────────────────────────────
async def select_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_employees":
        group = context.user_data["group"]
        employees = GROUPS[group]
        keyboard = [
            [InlineKeyboardButton(f"👤 {emp}", callback_data=f"emp_{i}")]
            for i, emp in enumerate(employees)
        ]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_groups")])
        await query.edit_message_text(
            f"🏢 Отдел: *{group}*\n\nВыберите сотрудника:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECT_EMPLOYEE

    rating = int(query.data.replace("rate_", ""))
    context.user_data["rating"] = rating

    await query.edit_message_text(
        f"👤 {context.user_data['employee']}\n"
        f"⭐ Оценка: {stars(rating)} ({rating}/5)\n\n"
        f"Напишите комментарий или отправьте 🎤 голосовое.\n"
        f"_(Если не хотите — напишите «-»)_",
        parse_mode="Markdown"
    )
    return GET_COMMENT


# ─── Текстовый комментарий ────────────────────────────────────────────────────
async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = context.user_data.get("employee", "Неизвестно")
    rating   = context.user_data.get("rating", 0)
    group    = context.user_data.get("group", "")
    username = update.effective_user.username or "аноним"
    now      = datetime.now().strftime("%d.%m.%Y %H:%M")
    comment  = update.message.text or ""

    save_review({"date": now, "group": group, "employee": employee,
                 "rating": rating, "comment": comment, "type": "text", "from": username})

    await context.bot.send_message(
        chat_id=MANAGER_ID,
        text=f"📝 *Новый отзыв!*\n\n🏢 Отдел: *{group}*\n👤 Сотрудник: *{employee}*\n"
             f"⭐ Оценка: {stars(rating)} ({rating}/5)\n💬 {comment}\n🕐 {now}\n👥 @{username}",
        parse_mode="Markdown"
    )

    msg = await update.message.reply_text(
        f"✅ Спасибо! *{employee}* получил {stars(rating)}\n\n"
        f"_Бот перезапустится через 15 секунд..._",
        parse_mode="Markdown"
    )

    context.user_data.clear()
    asyncio.create_task(_auto_restart(update, context, msg.message_id))
    return ConversationHandler.END


# ─── Голосовой комментарий ────────────────────────────────────────────────────
async def get_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employee = context.user_data.get("employee", "Неизвестно")
    rating   = context.user_data.get("rating", 0)
    group    = context.user_data.get("group", "")
    username = update.effective_user.username or "аноним"
    now      = datetime.now().strftime("%d.%m.%Y %H:%M")

    save_review({"date": now, "group": group, "employee": employee,
                 "rating": rating, "comment": "[голосовое]", "type": "voice", "from": username})

    await context.bot.send_message(
        chat_id=MANAGER_ID,
        text=f"🎤 *Голосовой отзыв!*\n\n🏢 {group}\n👤 *{employee}*\n"
             f"⭐ {stars(rating)} ({rating}/5)\n🕐 {now}\n👥 @{username}",
        parse_mode="Markdown"
    )
    await context.bot.forward_message(
        chat_id=MANAGER_ID,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )

    msg = await update.message.reply_text(
        f"✅ Голосовой отзыв принят!\n*{employee}* — {stars(rating)}\n\n"
        f"_Бот перезапустится через 15 секунд..._",
        parse_mode="Markdown"
    )

    context.user_data.clear()
    asyncio.create_task(_auto_restart(update, context, msg.message_id))
    return ConversationHandler.END


# ─── Авто-рестарт через 15 секунд ────────────────────────────────────────────
async def _auto_restart(update: Update, context: ContextTypes.DEFAULT_TYPE, old_msg_id: int):
    await asyncio.sleep(15)
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=old_msg_id
        )
    except Exception:
        pass

    keyboard = [
        [InlineKeyboardButton(f"🏢 {group}", callback_data=f"grp_{group}")]
        for group in GROUPS
    ]
    keyboard.append([InlineKeyboardButton("📋 История отзывов", callback_data="history")])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔄 *Новый отзыв?*\n\nВыберите отдел:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )  # ← эта скобка была пропущена в оригинале


# ─── История ──────────────────────────────────────────────────────────────────
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
        text += (
            f"🏢 {r.get('group', '')} | 👤 {r['employee']} — {stars(r['rating'])}\n"
            f"💬 {r['comment']}\n🕐 {r['date']}\n{'─' * 20}\n"
        )

    await query.edit_message_text(text, parse_mode="Markdown")
    return ConversationHandler.END


# ─── Отмена ───────────────────────────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. /start — начать заново.")
    context.user_data.clear()
    return ConversationHandler.END


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_GROUP:    [CallbackQueryHandler(select_group)],
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
