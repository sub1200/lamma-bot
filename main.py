import asyncio
import logging
import os
import threading
from dotenv import load_dotenv

load_dotenv()

from flask import request
from telegram import Update
from telegram.ext import Application

from config import config
from database import init_db
from handlers import register_handlers
from scheduler import start_scheduler
from web_server import app as flask_app, init_oauth_table

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"
bot_app: Application = None
bot_loop: asyncio.AbstractEventLoop = None


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_handler():
    if bot_app is None or bot_loop is None:
        return "Bot not initialized", 503
    update = Update.de_json(request.get_json(), bot_app.bot)
    asyncio.run_coroutine_threadsafe(
        bot_app.update_queue.put(update), bot_loop
    )
    return "OK", 200


@flask_app.route("/health")
def health():
    return "OK", 200


def run_flask():
    port = int(os.getenv("PORT", "7860"))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def bot_main():
    global bot_app, bot_loop

    init_db()
    init_oauth_table()
    start_scheduler()

    bot_app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .updater(None)
        .build()
    )
    register_handlers(bot_app)

    await bot_app.initialize()
    await bot_app.start()
    logger.info("Bot started")

    bot_loop = asyncio.get_running_loop()

    base_url = os.getenv("BASE_URL", "")
    if not base_url:
        port = os.getenv("PORT", "7860")
        base_url = f"http://localhost:{port}"

    webhook_url = f"{base_url}{WEBHOOK_PATH}"
    await bot_app.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set: {webhook_url}")

    while True:
        await asyncio.sleep(3600)


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        return

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask started in thread")

    asyncio.run(bot_main())


if __name__ == "__main__":
    main()
