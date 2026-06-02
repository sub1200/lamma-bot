from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from handlers.accounts import MAIN_KEYBOARD, ALL_ACCOUNT_TEXTS
from database import register_user, create_trial_subscription, is_trial_active, get_user

REGISTER_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("📝 إنشاء حساب جديد")]],
    resize_keyboard=True,
)

WELCOME_FIRST = (
    "🎉 *مرحباً بك في Lamma!*\n\n"
    "أنا مساعدك الذكي لإدارة أعمالك على السوشيال ميديا.\n"
    "أنشئ حسابك المجاني الآن وابدأ:\n\n"
    "✅ إنشاء منشورات بالذكاء الاصطناعي\n"
    "📸 تحويل صور المنتجات لصور احترافية\n"
    "📤 نشر تلقائي على فيسبوك\n"
    "🤖 ردود تلقائية ذكية\n\n"
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
        await update.message.reply_text(WELCOME_FIRST, reply_markup=REGISTER_KEYBOARD, parse_mode="Markdown")


async def register_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    existing = get_user(user_id)
    if existing:
        await update.message.reply_text("✅ حسابك مسجل بالفعل!", reply_markup=MAIN_KEYBOARD)
        return
    register_user(user_id, user.username or "", user.full_name or "")
    create_trial_subscription(user_id)
    await update.message.reply_text(
        "✅ *تم تسجيل حسابك بنجاح!*\n\n"
        "🎁 حصلت على:\n"
        "• 7 أيام تجربة مجانية\n"
        "• 50 نقطة مجانية\n\n"
        "استخدم القائمة للبدء 👇",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ *دليل المساعدة:*\n\n"
        "✍️ *إنشاء محتوى:* كتابة منشورات إبداعية بالـ AI\n"
        "📸 *تحسين صور:* تحويل صور منتجاتك لصور احترافية\n"
        "📤 *نشر تلقائي:* جدولة ونشر المحتوى على السوشيال ميديا\n"
        "👤 *حسابي:* إدارة اشتراكك ونقاطك\n"
        "⚙️ *إعدادات:* ضبط تفضيلات البوت\n\n"
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
    from handlers.settings import settings_menu

    account_handler = get_account_handler(text)
    if account_handler:
        await account_handler(update, context)
        return

    handler_map = {
        "✍️ إنشاء محتوى": post_start,
        "📸 تحسين صور": product_start,
        "📤 نشر تلقائي": publish_start,
        "📅 جدولة منشورات": schedule_start,
        "⚙️ إعدادات البوت": settings_menu,
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
    "✍️ إنشاء محتوى", "📸 تحسين صور",
    "📤 نشر تلقائي", "📅 جدولة منشورات",
    "👤 حسابي والاشتراك", "⚙️ إعدادات البوت",
    "❓ المساعدة والدعم",
] + ALL_ACCOUNT_TEXTS


def start_handler(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Regex("^📝 إنشاء حساب جديد$"), register_new))
    app.add_handler(MessageHandler(filters.Text(BUTTON_TEXTS), handle_menu_buttons))
