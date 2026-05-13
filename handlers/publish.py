from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from database import save_post
from facebook_publisher import publish_post as fb_publish
from instagram_publisher import publish_post as ig_publish

import logging

logger = logging.getLogger(__name__)

async def publish_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last_post = context.user_data.get("last_post", "")
    if not last_post:
        await update.message.reply_text(
            "لا يوجد منشور للنشر. أنشئ واحداً أولاً بـ /post"
        )
        return

    keyboard = [
        [InlineKeyboardButton("فيسبوك", callback_data="pub_facebook")],
        [InlineKeyboardButton("انستغرام", callback_data="pub_instagram")],
        [InlineKeyboardButton("الكل", callback_data="pub_both")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "اختر أين تريد النشر:",
        reply_markup=reply_markup,
    )


async def publish_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data
    last_post = context.user_data.get("last_post", "")

    if not last_post:
        await query.edit_message_text("لا يوجد منشور. استخدم /post أولاً.")
        return

    platforms = []
    if choice == "pub_facebook":
        platforms = ["facebook"]
    elif choice == "pub_instagram":
        platforms = ["instagram"]
    elif choice == "pub_both":
        platforms = ["facebook", "instagram"]

    await query.edit_message_text("جاري النشر... ⏳")

    results = []
    for platform in platforms:
        try:
            if platform == "facebook":
                post_id = fb_publish(last_post)
            else:
                post_id = ig_publish(last_post)

            save_post(last_post, platform, post_id, "published")
            results.append(f"✅ {platform}: تم النشر بنجاح")
        except Exception as e:
            logger.error(f"Publish error on {platform}: {e}")
            results.append(f"❌ {platform}: {e}")

    await query.edit_message_text("\n".join(results))


def publish_handlers(app):
    app.add_handler(CommandHandler("publish", publish_start))
    app.add_handler(CallbackQueryHandler(publish_callback, pattern="^pub_"))
