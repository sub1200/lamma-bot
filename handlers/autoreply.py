from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from database import set_setting, get_setting


async def autoreply_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enabled = get_setting("auto_reply_enabled", "0")
    status = "🟢 مفعل" if enabled == "1" else "🔴 معطل"

    await update.message.reply_text(
        f"حالة الردود التلقائية: {status}\n\n"
        "للتفعيل: /autoreply_on\n"
        "لإيقاف: /autoreply_off"
    )


async def autoreply_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("auto_reply_enabled", "1")
    await update.message.reply_text("✅ تم تفعيل الردود التلقائية!")


async def autoreply_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("auto_reply_enabled", "0")
    await update.message.reply_text("🔴 تم إيقاف الردود التلقائية.")


def autoreply_handlers(app):
    app.add_handler(CommandHandler("autoreply", autoreply_status))
    app.add_handler(CommandHandler("autoreply_on", autoreply_on))
    app.add_handler(CommandHandler("autoreply_off", autoreply_off))
