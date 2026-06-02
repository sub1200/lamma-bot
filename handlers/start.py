from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from handlers.accounts import MAIN_KEYBOARD, ALL_ACCOUNT_TEXTS
from database import register_user, create_trial_subscription, is_trial_active, get_user


LOGIN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("تسجيل الدخول بحساب فيسبوك 🔵", callback_data="login_facebook")],
])

WELCOME_FIRST = (
    "🎉 *مرحباً بك في Lamma!*\n\n"
    "أنا مساعدك الذكي لإدارة أعمالك على السوشيال ميديا.\n"
    "لتتمكن من استخدام البوت، يرجى تسجيل الدخول بحساب فيسبوك:\n\n"
    "• ربط صفحتك والنشر مباشرة\n"
    "• إدارة حسابات متعددة\n\n"
    "🚀 *اشتراك تجريبي مجاني لمدة 7 أيام + 50 نقطة هدية!*"
)

WELCOME_TEXT = (
    "مرحباً بك في بوت Lamma الذكي 🤖\n\n"
    "أنا مساعدك الشخصي لنمو أعمالك عبر الذكاء الاصطناعي. "
    "من خلالي يمكنك إدارة محتواك، جذب الزبائن، وزيادة مبيعاتك بكل سهولة.\n\n"
    "اختر من القائمة أدناه للبدء 👇"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    existing = get_user(user_id)
    if existing:
        await update.message.reply_text(WELCOME_TEXT, reply_markup=MAIN_KEYBOARD)
    else:
        await update.message.reply_text(WELCOME_FIRST, reply_markup=LOGIN_KEYBOARD, parse_mode="Markdown")


async def login_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    from web_server import create_session
    user_id = update.effective_user.id
    session_id = create_session(user_id, query.data.replace("login_", ""))
    base_url = "https://lamma-bot.onrender.com"
    link = f"{base_url}/login/{session_id}"
    await query.edit_message_text(
        "📤 *رابط تسجيل الدخول*\n\n"
        "اضغط الرابط أدناه لإتمام التسجيل:\n\n"
        f"🔗 {link}\n\n"
        "⏰ الرابط صالح لمدة 24 ساعة\n"
        "بعد التسجيل، عد واضغط /start للدخول.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 فتح رابط التسجيل", url=link)]
        ]),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ *دليل المساعدة:*\n\n"
        "✍️ *إنشاء محتوى:* كتابة منشورات إبداعية بالـ AI\n"
        "📦 *عرض منتج:* تصوير المنتج وعرضه بأنماط احترافية\n"
        "📤 *نشر تلقائي:* جدولة ونشر المحتوى على السوشيال ميديا\n"
        "👤 *حسابي:* إدارة اشتراكك ونقاطك\n\n"
        "يمكنك البدء بالضغط على الأزرار أدناه 👇"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD, parse_mode="Markdown")


async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    from handlers.post import post_start
    from handlers.product import product_start
    from handlers.publish import publish_start
    from handlers.schedule import schedule_start
    from handlers.accounts import accounts_menu, get_account_handler

    account_handler = get_account_handler(text)
    if account_handler:
        await account_handler(update, context)
        return

    handler_map = {
        "✍️ إنشاء محتوى": post_start,
        "📦 عرض منتج": product_start,
        "📤 نشر تلقائي": publish_start,
        "📅 جدولة منشورات": schedule_start,
        "❓ المساعدة والدعم": help_command,
    }

    handler = handler_map.get(text)
    if handler:
        await handler(update, context)
    else:
        await update.message.reply_text(
            "عذراً، هذا الخيار غير متاح حالياً.",
            reply_markup=MAIN_KEYBOARD,
        )


BUTTON_TEXTS = [
    "✍️ إنشاء محتوى", "📦 عرض منتج",
    "📤 نشر تلقائي", "📅 جدولة منشورات",
    "👤 حسابي والاشتراك",
    "❓ المساعدة والدعم",
] + ALL_ACCOUNT_TEXTS


def start_handler(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(login_choice, pattern="^login_"))
    app.add_handler(MessageHandler(filters.Text(BUTTON_TEXTS), handle_menu_buttons))
