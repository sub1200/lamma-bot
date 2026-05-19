from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import add_reply_rule, delete_reply_rule, get_reply_rules, set_setting, get_setting, set_reply_rule_enabled
from ai_generator import generate_response

AWAITING_KEYWORD = {}
AWAITING_REPLY = {}

RULES_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ إضافة رد جديد"), KeyboardButton("📋 قائمة الردود")],
        [KeyboardButton("🤖 تفعيل ردود AI"), KeyboardButton("📊 الإحصائيات")],
        [KeyboardButton("🔙 العودة للقائمة الرئيسية")]
    ],
    resize_keyboard=True,
)


async def autoreply_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    enabled = get_setting("auto_reply_enabled", "0") == "1"
    ai_enabled = get_setting("ai_reply_enabled", "1") == "1"
    rules = get_reply_rules("telegram")

    text = (
        f"🤖 *نظام الردود التلقائية*\n\n"
        f"الحالة: {'🟢 مفعّل' if enabled else '🔴 معطّل'}\n"
        f"ردود AI: {'🟢 مفعّل' if ai_enabled else '🔴 معطّل'}\n"
        f"عدد الردود المحفوظة: `{len(rules)}`\n\n"
        f"أضف ردوداً مخصصة أو فعّل الردود بالذكاء الاصطناعي ليرد البوت تلقائياً على رسائل العملاء."
    )
    await update.message.reply_text(text, reply_markup=RULES_KEYBOARD, parse_mode="Markdown")


async def add_rule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    AWAITING_KEYWORD[user_id] = True
    await update.message.reply_text(
        "➕ *إضافة رد جديد*\n\n"
        "أرسل لي **الكلمة المفتاحية** التي تريد الرد عليها:\n"
        "مثال: `سعر` أو `كيف أطلب` أو `عنوان`\n\n"
        "أو أرسل /إلغاء للعودة.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 إلغاء")]], resize_keyboard=True),
    )


async def handle_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_KEYWORD:
        return

    keyword = update.message.text.strip()
    AWAITING_KEYWORD.pop(user_id, None)
    AWAITING_REPLY[user_id] = keyword

    await update.message.reply_text(
        f"✅ الكلمة المفتاحية: `{keyword}`\n\n"
        "الآن أرسل **الرد** الذي تريد إرساله عندما يكتب شخص هذه الكلمة:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 إلغاء")]], resize_keyboard=True),
    )


async def handle_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_REPLY:
        return

    keyword = AWAITING_REPLY.pop(user_id)
    reply_text = update.message.text

    add_reply_rule("telegram", keyword, reply_text)

    await update.message.reply_text(
        f"✅ تم حفظ الرد بنجاح!\n\n"
        f"🔑 الكلمة: `{keyword}`\n"
        f"💬 الرد: `{reply_text[:50]}...`\n\n"
        "أضف ردوداً أخرى أو عد للقائمة.",
        parse_mode="Markdown",
        reply_markup=RULES_KEYBOARD,
    )


async def list_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = get_reply_rules("telegram")
    if not rules:
        await update.message.reply_text("📋 لا توجد ردود محفوظة بعد.\n\nاستخدم ➕ إضافة رد جديد")
        return

    text = "📋 *قائمة الردود التلقائية:*\n\n"
    for i, rule in enumerate(rules[:10], 1):
        status = "🟢" if rule["enabled"] else "🔴"
        text += f"{i}. {status} `{rule['keywords']}`\n"

    if len(rules) > 10:
        text += f"\n... و{len(rules) - 10} ردود أخرى"

    keyboard = []
    for i, rule in enumerate(rules[:6], 1):
        keyboard.append([InlineKeyboardButton(
            f"{'🟢' if rule['enabled'] else '🔴'} {rule['keywords'][:30]}",
            callback_data=f"toggle_rule_{rule['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🗑️ حذف رد", callback_data="delete_rule")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def toggle_rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rule_id = int(query.data.replace("toggle_rule_", ""))
    set_reply_rule_enabled(rule_id)

    rules = get_reply_rules("telegram")
    text = "📋 *قائمة الردود التلقائية:*\n\n"
    for i, rule in enumerate(rules[:10], 1):
        status = "🟢" if rule["enabled"] else "🔴"
        text += f"{i}. {status} `{rule['keywords']}`\n"

    keyboard = []
    for rule in rules[:6]:
        keyboard.append([InlineKeyboardButton(
            f"{'🟢' if rule['enabled'] else '🔴'} {rule['keywords'][:30]}",
            callback_data=f"toggle_rule_{rule['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_autoreply")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def delete_rule_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rules = get_reply_rules("telegram")
    keyboard = []
    for rule in rules:
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {rule['keywords'][:30]}",
            callback_data=f"del_rule_{rule['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_autoreply")])

    await query.edit_message_text("🗑️ اختر الرد الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))


async def delete_rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    rule_id = int(query.data.replace("del_rule_", ""))
    delete_reply_rule(rule_id)

    await query.edit_message_text("✅ تم حذف الرد بنجاح!", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 قائمة الردود", callback_data="list_rules")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_to_autoreply")]
    ]))


async def toggle_ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = get_setting("ai_reply_enabled", "1")
    new_val = "0" if current == "1" else "1"
    set_setting("ai_reply_enabled", new_val)
    status = "🟢 مفعّل" if new_val == "1" else "🔴 معطّل"
    await update.message.reply_text(f"ردود AI: {status}")


async def auto_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if get_setting("auto_reply_enabled", "0") != "1":
        return

    text = update.message.text.strip().lower()
    rules = get_reply_rules("telegram")

    for rule in rules:
        if rule["enabled"] and rule["keywords"].lower() in text:
            await update.message.reply_text(rule["reply_template"])
            return

    if get_setting("ai_reply_enabled", "1") == "1":
        try:
            response = await generate_response(
                f"أنت مساعد دعم عملاء لمتجر إلكتروني. رد باختصار واحترافية بالعربية على: {text}"
            )
            if response:
                await update.message.reply_text(response)
        except Exception:
            pass


async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    AWAITING_KEYWORD.pop(user_id, None)
    AWAITING_REPLY.pop(user_id, None)
    from handlers.accounts import MAIN_KEYBOARD
    await update.message.reply_text("تم الإلغاء.", reply_markup=MAIN_KEYBOARD)


async def back_to_autoreply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await autoreply_menu(query, context)


def autoreply_handlers(app):
    app.add_handler(CommandHandler("autoreply", autoreply_menu))
    app.add_handler(CallbackQueryHandler(toggle_rule, pattern="^toggle_rule_"))
    app.add_handler(CallbackQueryHandler(delete_rule, pattern="^del_rule_"))
    app.add_handler(CallbackQueryHandler(delete_rule_start, pattern="^delete_rule$"))
    app.add_handler(CallbackQueryHandler(list_rules, pattern="^list_rules$"))
    app.add_handler(CallbackQueryHandler(back_to_autoreply, pattern="^back_to_autoreply$"))
    app.add_handler(MessageHandler(filters.Regex("^(➕ إضافة رد جديد|📋 قائمة الردود|🤖 تفعيل ردود AI|📊 الإحصائيات)$"), autoreply_menu))
    app.add_handler(MessageHandler(filters.Regex("🔙 العودة للقائمة الرئيسية"), cancel_operation))
    app.add_handler(MessageHandler(filters.Regex("🔙 إلغاء"), cancel_operation))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply_handler))
