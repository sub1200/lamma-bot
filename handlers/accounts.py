from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import (
    get_user,
    update_user_plan,
    register_user,
    create_trial_subscription,
    get_active_subscription,
    is_trial_active,
    get_trial_days_remaining,
    list_accounts,
    delete_account,
)
from config import config

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
        [KeyboardButton("🔄 ربط حساب فيسبوك"), KeyboardButton("📊 حسابي")],
        [KeyboardButton("💳 شحن نقاط"), KeyboardButton("💎 الباقات والاشتراك")],
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

PLANS = {
    "basics": {"name": "🥉 الباقة الأساسية", "price": "9.99$", "credits": 100, "features": ["100 نقطة شهرياً", "دعم AI أساسي", "نشر على منصة واحدة"]},
    "pro": {"name": "🥈 الباقة الاحترافية", "price": "19.99$", "credits": 500, "features": ["500 نقطة شهرياً", "دعم AI متقدم", "نشر على جميع المنصات", "دعم فني سريع"]},
    "enterprise": {"name": "🥇 باقة الشركات", "price": "49.99$", "credits": 99999, "features": ["نقاط غير محدودة", "تخصيص كامل", "مدير حساب خاص", "أولوية في الدعم"]},
}


def format_account_text(user_id: int) -> str:
    user = get_user(user_id)
    if not user:
        return "❌ المستخدم غير موجود."
    sub = get_active_subscription(user_id)
    plan = user["plan"].upper() if user.get("plan") else "FREE"
    credits = user.get("credits", 0)
    trial_active = is_trial_active(user_id)
    trial_days = get_trial_days_remaining(user_id)
    lines = [
        "👤 *حسابي الشخصي*",
        "━━━━━━━━━━━━━━━━",
        f"🆔 المعرف: `{user_id}`",
        f"📋 الخطة: `{plan}`",
        f"💰 الرصيد: `{credits} نقطة`",
    ]
    if sub:
        lines.append(f"📅 الاشتراك: `{sub['plan_type']}`")
        if sub["plan_type"] == "trial" and trial_active:
            lines.append(f"⏳ متبقي من التقيّة: `{trial_days} أيام`")
    lines.extend([
        "━━━━━━━━━━━━━━━━",
        "🔹 *ربط فيسبوك:* اربط حساب فيسبوك للنشر المباشر",
        "🔹 *شحن:* اشحن نقاطاً إضافية لاستخدام أكثر",
        "🔹 *الباقات:* اختر الباقة المناسبة لك",
    ])
    return "\n".join(lines)


async def accounts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    text = format_account_text(user_id)
    await update.message.reply_text(text, reply_markup=ACCOUNT_KEYBOARD, parse_mode="Markdown")


async def account_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = format_account_text(user_id)
    await update.message.reply_text(text, parse_mode="Markdown")


async def pricing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💎 *اختر الباقة المناسبة:*\n\n"
        "🥉 *الأساسية* - `9.99$/شهر`\n"
        "100 نقطة شهرياً • دعم AI أساسي\n\n"
        "🥈 *الاحترافية* - `19.99$/شهر`\n"
        "500 نقطة شهرياً • دعم متقدم • جميع المنصات\n\n"
        "🥇 *الشركات* - `49.99$/شهر`\n"
        "نقاط غير محدودة • تخصيص كامل • مدير حساب\n\n"
        "اختر الباقة للتفاصيل 👇"
    )
    await update.message.reply_text(text, reply_markup=PRICING_KEYBOARD, parse_mode="Markdown")


async def show_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    plan_key = {"🥉 الباقة الأساسية": "basics", "🥈 الباقة الاحترافية": "pro", "🥇 باقة الشركات": "enterprise"}.get(text)
    if not plan_key:
        return
    plan = PLANS[plan_key]
    features = "\n".join(f"✅ {f}" for f in plan["features"])
    msg = (
        f"{plan['name']}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 السعر: `{plan['price']}`\n"
        f"🔹 النقاط: `{plan['credits']}`\n\n"
        f"*المزايا:*\n{features}\n\n"
        "📲 للاشتراك تواصل مع المطور: @sub1200"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=PRICING_KEYBOARD)


async def credit_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    credits = user["credits"] if user else 0
    await update.message.reply_text(
        f"📊 *رصيد النقاط*\n\n"
        f"💰 الرصيد الحالي: `{credits} نقطة`\n\n"
        "يتم خصم نقطة واحدة لكل:\n"
        "• إنشاء منشور ✍️\n"
        "• تحسين صورة 📸\n"
        "• تحليل صورة 🔍\n"
        "• رد تلقائي بالذكاء الاصطناعي 🤖",
        parse_mode="Markdown",
        reply_markup=ACCOUNT_KEYBOARD,
    )


async def link_facebook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from web_server import create_session
    user_id = update.effective_user.id
    session_id = create_session(user_id, "facebook")
    base_url = config.BASE_URL
    link = f"{base_url}/login/{session_id}"
    keyboard = [[InlineKeyboardButton("🔗 ربط حساب فيسبوك", url=link)]]
    await update.message.reply_text(
        "🔄 *ربط حساب فيسبوك*\n\n"
        "اضغط الزر أدناه لتسجيل الدخول عبر فيسبوك:\n"
        "• سيتم ربط صفحتك بالبوت\n"
        "• يمكنك النشر المباشر على فيسبوك\n"
        "• الرابط صالح لمدة 24 ساعة",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def list_linked_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = list_accounts()
    if not accounts:
        await update.message.reply_text(
            "📋 لا توجد حسابات مرتبطة.\n\n"
            "استخدم 🔄 ربط حساب فيسبوك لإضافة حساب.",
            reply_markup=ACCOUNT_KEYBOARD,
        )
        return
    text = "📋 *الحسابات المرتبطة:*\n\n"
    for acc in accounts:
        text += f"🔹 `{acc['platform']}` - {acc.get('page_id','')[:20]}\n"
    text += "\nلإضافة حساب جديد استخدم 🔄 ربط حساب فيسبوك"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=ACCOUNT_KEYBOARD)


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.start import WELCOME_TEXT
    await update.message.reply_text(WELCOME_TEXT, reply_markup=MAIN_KEYBOARD)


async def back_to_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = format_account_text(user_id)
    await update.message.reply_text(text, reply_markup=ACCOUNT_KEYBOARD, parse_mode="Markdown")


ACCOUNT_BUTTONS = {
    "👤 حسابي والاشتراك": accounts_menu,
    "📊 حسابي": account_detail,
    "🔄 ربط حساب فيسبوك": link_facebook,
    "📋 الحسابات المرتبطة": list_linked_accounts,
    "💳 شحن نقاط": pricing_menu,
    "💎 الباقات والاشتراك": pricing_menu,
    "🥉 الباقة الأساسية": show_plan,
    "🥈 الباقة الاحترافية": show_plan,
    "🥇 باقة الشركات": show_plan,
    "🔙 العودة للحساب": back_to_accounts,
    "🔙 العودة للقائمة الرئيسية": back_to_main,
}

ALL_ACCOUNT_TEXTS = list(ACCOUNT_BUTTONS.keys())


def get_account_handler(text: str):
    return ACCOUNT_BUTTONS.get(text)


def accounts_handlers(app):
    app.add_handler(CommandHandler("account", accounts_menu))
    app.add_handler(CommandHandler("accounts", accounts_menu))
