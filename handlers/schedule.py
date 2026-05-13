from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from database import save_schedule

AWAITING_SCHEDULE = {}
SCHEDULE_TIME_KEY = "schedule_time"


async def schedule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_post = context.user_data.get("last_post", "")
    if not last_post:
        await update.message.reply_text(
            "لا يوجد منشور للجدولة. أنشئ واحداً بـ /post أولاً."
        )
        return

    keyboard = [
        [InlineKeyboardButton("فيسبوك", callback_data="sch_facebook")],
        [InlineKeyboardButton("انستغرام", callback_data="sch_instagram")],
        [InlineKeyboardButton("الكل", callback_data="sch_both")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "اختر المنصة للجدولة:",
        reply_markup=reply_markup,
    )


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data
    platforms_map = {
        "sch_facebook": "facebook",
        "sch_instagram": "instagram",
        "sch_both": "facebook,instagram",
    }

    if choice in platforms_map:
        context.user_data["schedule_platforms"] = platforms_map[choice]
        user_id = update.effective_user.id
        AWAITING_SCHEDULE[user_id] = True

        await query.edit_message_text(
            "أرسل وقت النشر بصيغة:\n"
            "YYYY-MM-DD HH:MM\n\n"
            "مثال: 2026-05-10 15:30"
        )


async def handle_schedule_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_SCHEDULE:
        return

    time_str = update.message.text.strip()
    platforms = context.user_data.get("schedule_platforms", "facebook")
    content = context.user_data.get("last_post", "")

    if not content:
        await update.message.reply_text("لا يوجد منشور. استخدم /post أولاً.")
        AWAITING_SCHEDULE.pop(user_id, None)
        return

    try:
        save_schedule(content, platforms, time_str)
        await update.message.reply_text(
            f"تمت جدولة المنشور بنجاح ✅\n"
            f"المنصة: {platforms}\n"
            f"الوقت: {time_str}"
        )
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ في الجدولة: {e}")

    AWAITING_SCHEDULE.pop(user_id, None)


def schedule_handlers(app):
    app.add_handler(CommandHandler("schedule", schedule_start))
    app.add_handler(CallbackQueryHandler(schedule_callback, pattern="^sch_"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_schedule_time,
    ))
