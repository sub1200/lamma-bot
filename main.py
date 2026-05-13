import logging
import threading
import os
from dotenv import load_dotenv

load_dotenv()

from telegram.ext import ApplicationBuilder

from config import config
from database import init_db
from handlers import register_handlers
from scheduler import start_scheduler
from web_server import start_web_server

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def run_web_server():
    port = int(os.getenv("PORT", "5000"))
    start_web_server(host="0.0.0.0", port=port)


async def post_init(app):
    init_db()
    start_scheduler()
    logger.info("Bot initialized successfully")


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        print("ERROR: Please set TELEGRAM_BOT_TOKEN environment variable")
        return

    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("Web server thread started")

    app = ApplicationBuilder() \
        .token(config.TELEGRAM_BOT_TOKEN) \
        .post_init(post_init) \
        .build()

    register_handlers(app)

    logger.info("Starting bot...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
