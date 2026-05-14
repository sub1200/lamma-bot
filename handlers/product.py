import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from image_processor import STYLES, transform_product_image
from video_generator import image_to_video
from vision_analyzer import analyze_image, suggest_product_style
from database import save_post
from facebook_publisher import publish_post as fb_publish
from instagram_publisher import publish_post as ig_publish
logger = logging.getLogger(__name__)

AWAITING_PHOTO = {}
AWAITING_ACTION = {}


async def product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    AWAITING_PHOTO[user_id] = True

    await update.message.reply_text(
        "📸 **تصوير المنتج**\n\n"
        "أرسل لي صورة المنتج وسأحولها لك بأنماط احترافية!",
        parse_mode="Markdown",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_PHOTO:
        return

    photo_file = await update.message.photo[-1].get_file()
    image_bytes = bytes(await photo_file.download_as_bytearray())
    context.user_data["product_original"] = image_bytes

    AWAITING_PHOTO.pop(user_id, None)

    await update.message.reply_text("🔍 جاري تحليل المنتج... اقتراح النمط المناسب قادم!")

    analysis = await analyze_image(
        image_bytes,
        "Analyze this product in Arabic. Identify what it is, its color, material, and shape. "
        "Then suggest the best presentation style from these options: "
        "professional, lifestyle, 3d_mockup, minimalist, social_media, luxury. "
        "Keep your response to 3 short sentences.",
    )

    context.user_data["product_description"] = analysis
    AWAITING_ACTION[user_id] = True

    keyboard = []
    for key, style in STYLES.items():
        label = style["label"]
        keyboard.append([InlineKeyboardButton(label, callback_data=f"style_{key}")])

    await update.message.reply_text(
        f"🔍 **تحليل المنتج:**\n{analysis}\n\nاختر نمط العرض:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_style_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if user_id not in AWAITING_ACTION:
        return

    style_key = query.data.replace("style_", "")
    if style_key not in STYLES:
        return

    original = context.user_data.get("product_original")
    if not original:
        await query.edit_message_text("❌ الصورة غير موجودة. استخدم /product مرة أخرى.")
        AWAITING_ACTION.pop(user_id, None)
        return

    await query.edit_message_text(f"⏳ جاري إنشاء الصورة بـ AI... ({STYLES[style_key]['label']})")

    try:
        description = context.user_data.get("product_description", "")
        result = transform_product_image(original, style_key, description)
        if result is None:
            await query.edit_message_text(
                "❌ فشل التحويل.\n"
                "تأكد من اتصال الإنترنت."
            )
            AWAITING_ACTION.pop(user_id, None)
            return

        context.user_data["product_transformed"] = result
        context.user_data["product_style"] = style_key
        AWAITING_ACTION.pop(user_id, None)

        await query.message.reply_photo(
            photo=result,
            caption=f"✅ تم التحويل بنمط: {STYLES[style_key]['label']}",
        )

        await _show_action_menu(context, query.message.chat_id)

    except Exception as e:
        logger.error(f"Transform error: {e}")
        await query.edit_message_text(f"❌ خطأ: {e}")
        AWAITING_ACTION.pop(user_id, None)


async def _show_action_menu(context, chat_id: int):
    keyboard = [
        [InlineKeyboardButton("🔍 تحليل الصورة", callback_data="act_analyze")],
        [InlineKeyboardButton("🎬 تحويل إلى فيديو", callback_data="act_animate")],
        [InlineKeyboardButton("📤 نشر على فيسبوك", callback_data="act_fb")],
        [InlineKeyboardButton("📤 نشر على انستغرام", callback_data="act_ig")],
        [InlineKeyboardButton("🔄 نمط آخر", callback_data="act_restyle")],
        [InlineKeyboardButton("✅ تم", callback_data="act_done")],
    ]

    await context.bot.send_message(
        chat_id=chat_id,
        text="ماذا تريد أن تفعل بالصورة؟",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data.replace("act_", "")

    if action == "analyze":
        img = context.user_data.get("product_transformed")
        if not img:
            await query.edit_message_text("❌ لا توجد صورة.")
            return

        await query.edit_message_text("🔍 جاري تحليل الصورة...")
        result = await analyze_image(img, "Describe this image in detail in Arabic")
        await query.message.reply_text(f"🔍 **التحليل:**\n\n{result}", parse_mode="Markdown")
        await _show_action_menu(context, query.message.chat_id)

    elif action == "animate":
        img = context.user_data.get("product_transformed")
        if not img:
            await query.edit_message_text("❌ لا توجد صورة.")
            return

        await query.edit_message_text("🎬 جاري إنشاء الفيديو...")
        video = image_to_video(img)
        if not video:
            await query.edit_message_text(
                "❌ فشل إنشاء الفيديو. تأكد من تثبيت FFmpeg:\n"
                "sudo apt install ffmpeg"
            )
            return

        context.user_data["product_video"] = video
        await query.message.reply_video(video=video, caption="🎬 فيديو العرض")
        await _show_action_menu(context, query.message.chat_id)

    elif action == "fb":
        img = context.user_data.get("product_transformed")
        if not img:
            await query.edit_message_text("❌ لا توجد صورة.")
            return

        await query.edit_message_text("📤 جاري النشر على فيسبوك...")
        try:
            post_id = fb_publish("منتج جديد 🎉")
            save_post("منتج جديد 🎉", "facebook", post_id, "published")
            await query.edit_message_text("✅ تم النشر على فيسبوك!")
        except Exception as e:
            await query.edit_message_text(f"❌ فشل النشر: {e}")

    elif action == "ig":
        img = context.user_data.get("product_transformed")
        if not img:
            await query.edit_message_text("❌ لا توجد صورة.")
            return

        await query.edit_message_text("📤 جاري النشر على انستغرام...")
        try:
            post_id = ig_publish("منتج جديد 🎉")
            save_post("منتج جديد 🎉", "instagram", post_id, "published")
            await query.edit_message_text("✅ تم النشر على انستغرام!")
        except Exception as e:
            await query.edit_message_text(f"❌ فشل النشر: {e}")

    elif action == "restyle":
        user_id = update.effective_user.id
        AWAITING_ACTION[user_id] = True

        keyboard = []
        for key, style in STYLES.items():
            keyboard.append([InlineKeyboardButton(style["label"], callback_data=f"style_{key}")])

        await query.edit_message_text(
            "اختر نمطاً آخر:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif action == "done":
        for k in ["product_original", "product_transformed", "product_video", "product_style"]:
            context.user_data.pop(k, None)

        await query.edit_message_text(
            "✅ تم الانتهاء!\n"
            "استخدم /product لتصوير منتج جديد.",
        )


def product_handlers(app):
    app.add_handler(CommandHandler("product", product_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_style_choice, pattern="^style_"))
    app.add_handler(CallbackQueryHandler(handle_action, pattern="^act_"))
