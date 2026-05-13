import logging

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes

from vision_analyzer import analyze_image, analyze_video

logger = logging.getLogger(__name__)

AWAITING_ANALYSIS = {}


async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    AWAITING_ANALYSIS[user_id] = True

    await update.message.reply_text(
        "🔍 أرسل لي صورة أو فيديو وسأحلله لك بالذكاء الاصطناعي!"
    )


async def handle_analyze_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_ANALYSIS:
        return

    photo = await update.message.photo[-1].get_file()
    image_bytes = bytes(await photo.download_as_bytearray())

    await update.message.reply_text("🔍 جاري تحليل الصورة...")

    result = await analyze_image(image_bytes)
    await update.message.reply_text(f"🔍 **التحليل:**\n\n{result}", parse_mode="Markdown")

    AWAITING_ANALYSIS.pop(user_id, None)


async def handle_analyze_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in AWAITING_ANALYSIS:
        return

    video = await update.message.video.get_file()
    video_bytes = bytes(await video.download_as_bytearray())

    await update.message.reply_text("🔍 جاري تحليل الفيديو...")

    result = await analyze_video(video_bytes)
    await update.message.reply_text(f"🔍 **تحليل الفيديو:**\n\n{result}", parse_mode="Markdown")

    AWAITING_ANALYSIS.pop(user_id, None)


def analyze_handlers(app):
    app.add_handler(CommandHandler("analyze", analyze_start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_analyze_photo))
    app.add_handler(MessageHandler(filters.VIDEO, handle_analyze_video))
