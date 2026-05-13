from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import CommandHandler, ContextTypes
from database import get_user, update_user_plan, register_user

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("✍️ إنشاء محتوى"), KeyboardButton("📸 تحسين صور")],
        [KeyboardButton("📤 نشر تلقائي"), KeyboardButton("📅 جدولة منشورات")],
        [KeyboardButton("👤 حسابي والاشتراك"), KeyboardButton("⚙️ إعدادات البوت")],
        [KeyboardButton("❓ المساعدة والدعم")]
    ],
    resize_keyboard=True,
)

ACCOUNT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("💳 شحن نقاط")],
        [KeyboardButton("💎 ترقية الباقة")],
        [KeyboardButton("📊 استهلاك النقاط")],
        [KeyboardButton("🔙 العودة للقائمة الرئيسية")]
    ],
    resize_keyboard=True,
)

PRICING_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🥉 الباقة الأساسية")],
        [KeyboardButton("🥈 الباقة الاحترافية")],
        [KeyboardButton("🥇 باقة الشركات")],
        [KeyboardButton("🔙 العودة للحساب")]
    ],
    resize_keyboard=True,
)


async def accounts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    user = get_user(user_id)

    plan = user["plan"].upper() if user else "غير معروف"
    credits = user["credits"] if user else 0

    text = (
        f"👤 *ملف الحساب الشخصي*\n\n"
        f"🔹 الخطة الحالية: `{plan}`\n"
        f"🔹 رصيد النقاط: `{credits} نقطة`\n"
        f"━━━━━━━━━━━━━━\n"
        f"يمكنك من هنا ترقية حسابك أو شحن نقاط إضافية لزيادة قدرات الذكاء الاصطناعي لديك."
    )
    await update.message.reply_text(text, reply_markup=ACCOUNT_KEYBOARD, parse_mode="Markdown")


async def pricing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💎 *اختر الباقة المناسبة لنمو أعمالك:*\n\n"
        "🥉 *الباقة الأساسية:*\n"
        "- 100 نقطة شهرياً\n"
        "- دعم AI أساسي\n"
        "- سعر: [X] دولار\n\n"
        "🥈 *الباقة الاحترافية:*\n"
        "- 1000 نقطة شهرياً\n"
        "- دعم AI متقدم\n"
        "- دعم فني سريع\n"
        "- سعر: [X] دولار\n\n"
        "🥇 *باقة الشركات:*\n"
        "- نقاط غير محدودة\n"
        "- تخصيص كامل للبوت\n"
        "- مدير حساب خاص\n"
        "- سعر: [X] دولار"
    )
    await update.message.reply_text(text, reply_markup=PRICING_KEYBOARD, parse_mode="Markdown")


async def credit_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    credits = user["credits"] if user else 0
    await update.message.reply_text(
        f"📊 رصيدك الحالي: `{credits} نقطة`\n\n"
        "يتم خصم نقطة واحدة لكل عملية إنشاء محتوى أو تحسين صورة.",
        parse_mode="Markdown",
        reply_markup=ACCOUNT_KEYBOARD,
    )


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.start import WELCOME_TEXT
    await update.message.reply_text(WELCOME_TEXT, reply_markup=MAIN_KEYBOARD)


def get_account_handler(text: str):
    mapping = {
        "👤 حسابي والاشتراك": accounts_menu,
        "💳 شحن نقاط": pricing_menu,
        "💎 ترقية الباقة": pricing_menu,
        "📊 استهلاك النقاط": credit_history,
        "🔙 العودة للقائمة الرئيسية": back_to_main,
        "🔙 العودة للحساب": accounts_menu,
    }
    return mapping.get(text)


def accounts_handlers(app):
    app.add_handler(CommandHandler("account", accounts_menu))
    app.add_handler(CommandHandler("accounts", accounts_menu))
