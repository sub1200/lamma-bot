from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from database import get_setting, set_setting

AWAITING_HF_TOKEN = {}


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_setting("language", "ar")
    lang_display = "العربية" if lang == "ar" else "English"

    hf_token = get_setting("hf_api_token", "")
    hf_status = "✅ مضبوط" if hf_token else "❌ غير مضبوط"

    keyboard = [
        [InlineKeyboardButton(
            f"اللغة: {lang_display}",
            callback_data="set_lang",
        )],
        [InlineKeyboardButton(
            f"Hugging Face Token: {hf_status}",
            callback_data="set_hf",
        )],
        [InlineKeyboardButton("🔙 رجوع", callback_data="set_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "الإعدادات:",
        reply_markup=reply_markup,
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "set_lang":
        lang = get_setting("language", "ar")
        new_lang = "en" if lang == "ar" else "ar"
        set_setting("language", new_lang)
        display = "English" if new_lang == "en" else "العربية"
        await query.edit_message_text(f"✅ تم تغيير اللغة إلى: {display}")

    elif query.data == "set_hf":
        user_id = update.effective_user.id
        AWAITING_HF_TOKEN[user_id] = True
        await query.edit_message_text(
            "أرسل Token من Hugging Face:\n\n"
            "1. اذهب إلى https://huggingface.co/settings/tokens\n"
            "2. سجل حساب (مجاني)\n"
            "3. اضغط New Token\n"
            "4. اختر الدور: read\n"
            "5. انسخ وأرسل التوكن هنا"
        )

    elif query.data == "set_back":
        await query.edit_message_text("تم الرجوع.")


async def handle_hf_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_HF_TOKEN:
        return

    token = update.message.text.strip()
    set_setting("hf_api_token", token)
    AWAITING_HF_TOKEN.pop(user_id, None)
    await update.message.reply_text("✅ تم حفظ Hugging Face Token بنجاح!")


def settings_handlers(app):
    app.add_handler(CommandHandler("settings", settings_menu))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^set_"))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_hf_token,
    ))
