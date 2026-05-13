from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from ai_generator import generate_post
from database import get_setting, save_post

AWAITING_TOPIC = {}

TOPICS_KEY = "post_topic"
TONES_KEY = "post_tone"


async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    AWAITING_TOPIC[user_id] = True
    context.user_data[TOPICS_KEY] = None
    context.user_data[TONES_KEY] = "professional"

    await update.message.reply_text(
        "ممتاز! لننشئ منشوراً جديداً ✍️\n\n"
        "اختر نغمة المنشور:\n"
        "1️⃣ احترافي (professional)\n"
        "2️⃣ عفوي (casual)\n"
        "3️⃣ تحفيزي (motivational)\n"
        "4️⃣ فكاهي (humorous)\n\n"
        "أرسل الرقم (1-4):"
    )


async def handle_post_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_TOPIC:
        return

    text = update.message.text.strip()
    tone_map = {
        "1": "professional",
        "2": "casual",
        "3": "motivational",
        "4": "humorous",
    }

    tone_selected = context.user_data.get(TONES_KEY)
    if tone_selected is None:
        if text in tone_map:
            context.user_data[TONES_KEY] = tone_map[text]
            await update.message.reply_text(
                f"تم اختيار النغمة: {tone_map[text]}\n\n"
                "الآن، أرسل الموضوع الذي تريد كتابة المنشور عنه:"
            )
        else:
            await update.message.reply_text("رجاءً أرسل رقم من 1 إلى 4:")
        return

    topic = text
    tone = context.user_data.get(TONES_KEY, "professional")
    language = get_setting("language", "ar")

    await update.message.reply_text("جاري إنشاء المنشور... ⏳")

    try:
        post_content = generate_post(topic, tone, language)
        save_post(post_content, "draft", status="draft")
        context.user_data["last_post"] = post_content

        await update.message.reply_text(
            f"تم إنشاء المنشور بنجاح ✅\n\n{post_content}\n\n"
            "للنشر استخدم /publish"
        )
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

    AWAITING_TOPIC.pop(user_id, None)
    context.user_data.pop(TOPICS_KEY, None)
    context.user_data.pop(TONES_KEY, None)


def post_handlers(app):
    app.add_handler(CommandHandler("post", post_start))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_post_message,
    ))
