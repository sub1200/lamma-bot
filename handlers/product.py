import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from image_processor import transform_product_image, text_to_image
from video_generator import image_to_video
from vision_analyzer import analyze_image, classify_product, PRODUCT_CATEGORIES
from ai_generator import generate_response
from database import save_post, add_reply_rule
from facebook_publisher import publish_post as fb_publish
from facebook_publisher import get_page_id
import requests

logger = logging.getLogger(__name__)

AWAITING_PHOTO = {}
AWAITING_DESC_EDIT = {}
AWAITING_PRICE = {}

PRESENTATION_STYLES = {
    "standard": {"label": "🖼️ عرض احترافي", "type": "pillow"},
    "with_person": {"label": "👤 مع شخص يرتديه", "type": "pollinations"},
    "environment": {"label": "🏠 في بيئة استخدام", "type": "pollinations"},
    "luxury": {"label": "💎 عرض فاخر", "type": "pillow"},
}


async def product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    AWAITING_PHOTO[user_id] = True
    await update.message.reply_text(
        "📦 *عرض المنتج*\n\n"
        "أرسل لي صورة المنتج وسأقوم بـ:\n"
        "1️⃣ تحليل المنتج بالذكاء الاصطناعي\n"
        "2️⃣ عرضه بأنماط احترافية\n"
        "3️⃣ إنشاء وصف تسويقي احترافي\n"
        "4️⃣ نشره مباشرة على فيسبوك\n\n"
        "🚀 ابدأ بإرسال الصورة:",
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

    await update.message.reply_text("🔍 جاري تحليل المنتج...")

    analysis = await analyze_image(
        image_bytes,
        "Analyze this product in Arabic. Identify what it is (name, type), color, material, shape. "
        "Reply with only: 'المنتج: [name] - [color] - [material]'. Max 20 words.",
    )

    context.user_data["product_analysis"] = analysis

    classification = await classify_product(image_bytes)
    context.user_data["product_class"] = classification

    product_name = analysis.replace("المنتج:", "").strip() if "المنتج:" in analysis else analysis
    cat = classification.get("category", "other")
    cat_info = PRODUCT_CATEGORIES.get(cat, PRODUCT_CATEGORIES["other"])

    context.user_data["allowed_styles"] = cat_info["styles"]

    keyboard = [
        [InlineKeyboardButton(PRESENTATION_STYLES[k]["label"], callback_data=f"pres_{k}")]
        for k in cat_info["styles"]
    ]

    await update.message.reply_text(
        f"✅ *تم التعرف على المنتج:*\n{product_name}\n"
        f"📂 الفئة: {cat_info['label']}\n\n"
        f"🎨 اختر نمط العرض:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_presentation_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    style_key = query.data.replace("pres_", "")
    allowed = context.user_data.get("allowed_styles", [])
    if style_key not in PRESENTATION_STYLES or (allowed and style_key not in allowed):
        await query.edit_message_text("❌ هذا النمط غير متاح لهذا المنتج.")
        return

    style = PRESENTATION_STYLES[style_key]
    original = context.user_data.get("product_original")
    analysis = context.user_data.get("product_analysis", "")
    classification = context.user_data.get("product_class", {})
    product_name = classification.get("arabic") or analysis.replace("المنتج:", "").strip()
    if not product_name or product_name == "المنتج":
        product_name = analysis.replace("المنتج:", "").strip() if "المنتج:" in analysis else "المنتج"

    await query.edit_message_text(f"⏳ جاري إنشاء الصورة... ({style['label']})")

    try:
        result = None
        if style_key == "standard":
            result = transform_product_image(original, "professional", analysis)
        elif style_key == "luxury":
            result = transform_product_image(original, "luxury", analysis)
        elif style_key == "with_person":
            prompt = f"A person wearing or holding {product_name}, professional product photography, white background, high quality, realistic"
            result = text_to_image(prompt)
            if not result:
                result = transform_product_image(original, "lifestyle", analysis)
        elif style_key == "environment":
            prompt = f"{product_name} being used in a real environment, professional lifestyle photography, natural lighting, high quality"
            result = text_to_image(prompt)
            if not result:
                result = transform_product_image(original, "social_media", analysis)

        if not result:
            await query.edit_message_text("❌ فشل إنشاء الصورة. حاول مرة أخرى.")
            return

        context.user_data["product_image"] = result
        context.user_data["product_style"] = style_key

        classification = context.user_data.get("product_class", {})
        sizes = classification.get("sizes", "N/A")
        price_guess = classification.get("price_guess", "")
        price_info = f"\n💰 السعر المقترح: {price_guess}\n📏 المقاسات: {sizes}" if price_guess else ""

        await query.message.reply_photo(
            photo=result,
            caption=f"✅ تم الإنشاء بنجاح - {style['label']}{price_info}",
        )

        if price_guess:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"💡 *اقتراح الذكاء الاصطناعي:*\n"
                     f"السعر التقريبي: {price_guess}\n"
                     f"المقاسات: {sizes}\n\n"
                     "يمكنك تأكيد هذه المعلومات أو تغييرها من القائمة أدناه.",
                parse_mode="Markdown",
            )

        await _show_action_menu(context, query.message.chat_id)

    except Exception as e:
        logger.error(f"Presentation error: {e}")
        await query.edit_message_text(f"❌ خطأ: {e}")


async def _show_action_menu(context, chat_id: int):
    keyboard = [
        [InlineKeyboardButton("✍️ وصف احترافي للمنتج", callback_data="act_desc")],
        [InlineKeyboardButton("🎬 تحويل إلى فيديو", callback_data="act_video")],
        [InlineKeyboardButton("📤 نشر على فيسبوك", callback_data="act_fb")],
        [InlineKeyboardButton("🔄 نمط عرض آخر", callback_data="act_restyle")],
        [InlineKeyboardButton("✅ تم - إضافة السعر والمقاسات", callback_data="act_price")],
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text="📋 *ماذا تريد أن تفعل الآن؟*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data.replace("act_", "")
    user_id = update.effective_user.id
    img = context.user_data.get("product_image")
    analysis = context.user_data.get("product_analysis", "")
    classification = context.user_data.get("product_class", {})
    product_name = classification.get("arabic") or analysis.replace("المنتج:", "").strip()
    if not product_name or product_name == "المنتج":
        product_name = analysis.replace("المنتج:", "").strip() if "المنتج:" in analysis else "المنتج"

    if action == "desc":
        if not img:
            await query.edit_message_text("❌ لا توجد صورة.")
            return
        await query.edit_message_text("✍️ جاري كتابة وصف احترافي...")
        desc = await generate_response(
            f"Write a professional product description in Arabic for '{product_name}'. "
            f"Make it persuasive and suitable for Facebook. Include features, benefits, "
            f"and a call to action. 3-4 sentences. Analysis: {analysis[:200]}"
        )
        if not desc:
            desc = f"🔥 {product_name} المثالي لعملائك! الجودة العالية والتصميم الأنيق - اطلبه الآن!"
        context.user_data["product_description"] = desc
        AWAITING_DESC_EDIT[user_id] = True
        await query.message.reply_text(
            f"✍️ *الوصف المقترح:*\n\n{desc}\n\n"
            "📝 هل تريد إضافة أو تعديل شيء؟\n"
            "أرسل التعديلات، أو أرسل /تم للاعتماد.",
            parse_mode="Markdown",
        )

    elif action == "video":
        if not img:
            await query.edit_message_text("❌ لا توجد صورة.")
            return
        await query.edit_message_text("🎬 جاري تحويل الصورة إلى فيديو...")
        video = image_to_video(img)
        if not video:
            await query.edit_message_text(
                "❌ تحويل الفيديو غير متاح حالياً (FFmpeg غير مثبت).\n"
                "يمكنك المتابعة بخيارات أخرى."
            )
            return
        context.user_data["product_video"] = video
        await query.message.reply_video(video=video, caption="🎬 فيديو عرض المنتج")
        await _show_action_menu(context, query.message.chat_id)

    elif action == "fb":
        if not img:
            await query.edit_message_text("❌ لا توجد صورة.")
            return
        desc = context.user_data.get("product_description", f"🔥 {product_name} - اطلبه الآن!")
        await query.edit_message_text("📤 جاري النشر على فيسبوك...")
        try:
            page_id = get_page_id()
            token = None
            from database import get_account
            account = get_account("facebook")
            if account:
                token = account["token"]
            if not page_id or not token:
                await query.edit_message_text("❌ لم يتم ربط حساب فيسبوك. استخدم /account أولاً.")
                return

            upload_url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
            resp = requests.post(upload_url, data={
                "caption": desc,
                "access_token": token,
            }, files={"source": ("product.jpg", img, "image/jpeg")})
            data = resp.json()
            if "id" in data:
                save_post(desc, "facebook", data["id"], "published")
                await query.edit_message_text("✅ تم النشر على فيسبوك بنجاح!")
            else:
                await query.edit_message_text(f"❌ فشل النشر: {data}")
        except Exception as e:
            await query.edit_message_text(f"❌ فشل النشر: {e}")

    elif action == "restyle":
        allowed = context.user_data.get("allowed_styles", list(PRESENTATION_STYLES.keys()))
        keyboard = [
            [InlineKeyboardButton(PRESENTATION_STYLES[k]["label"], callback_data=f"pres_{k}")]
            for k in allowed
        ]
        await query.edit_message_text(
            "🎨 اختر نمط عرض آخر:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif action == "price":
        await query.edit_message_text(
            "📏 *إضافة السعر والمقاسات*\n\n"
            "أرسل سعر المنتج والمقاسات المتوفرة (إن وجدت).\n"
            "مثال: `السعر: 50$ - المقاسات: M, L, XL`\n\n"
            "هذه المعلومات ستُستخدم للرد التلقائي على استفسارات الزبائن.",
            parse_mode="Markdown",
        )
        AWAITING_PRICE[user_id] = True


async def handle_desc_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_DESC_EDIT:
        return

    text = update.message.text.strip()
    if text == "/تم":
        AWAITING_DESC_EDIT.pop(user_id, None)
        desc = context.user_data.get("product_description", "")
        await update.message.reply_text(
            f"✅ *تم اعتماد الوصف!*\n\n{desc}\n\n"
            "يمكنك الآن نشر الصورة على فيسبوك من القائمة.",
            parse_mode="Markdown",
        )
        chat_id = update.effective_chat.id
        await _show_action_menu(context, chat_id)
        return

    new_desc = text
    context.user_data["product_description"] = new_desc
    AWAITING_DESC_EDIT.pop(user_id, None)
    await update.message.reply_text(
        f"✅ *تم تحديث الوصف!*\n\n{new_desc}\n\n"
        "📤 يمكنك الآن النشر على فيسبوك.",
        parse_mode="Markdown",
    )
    chat_id = update.effective_chat.id
    await _show_action_menu(context, chat_id)


async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_PRICE:
        return
    AWAITING_PRICE.pop(user_id, None)

    price_text = update.message.text.strip()
    analysis = context.user_data.get("product_analysis", "")
    product_name = analysis.replace("المنتج:", "").strip() if "المنتج:" in analysis else "المنتج"

    add_reply_rule("telegram", product_name, f"سعر {product_name}: {price_text}")

    context.user_data.pop("product_original", None)
    context.user_data.pop("product_image", None)
    context.user_data.pop("product_video", None)
    context.user_data.pop("product_description", None)
    context.user_data.pop("product_analysis", None)

    await update.message.reply_text(
        f"✅ *تم حفظ معلومات المنتج!*\n\n"
        f"📦 المنتج: {product_name}\n"
        f"💰 السعر: {price_text}\n\n"
        "🤖 سيتم استخدام هذه المعلومات للرد التلقائي على استفسارات الزبائن.\n\n"
        "للبدء بمنتج جديد، استخدم /product",
        parse_mode="Markdown",
    )


def product_handlers(app):
    app.add_handler(CommandHandler("product", product_start))
    app.add_handler(CommandHandler("imagine", product_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(handle_presentation_choice, pattern="^pres_"))
    app.add_handler(CallbackQueryHandler(handle_action, pattern="^act_"))


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in AWAITING_DESC_EDIT:
        await handle_desc_edit(update, context)
    elif user_id in AWAITING_PRICE:
        await handle_price(update, context)
