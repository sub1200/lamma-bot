import asyncio
import logging
import os
import subprocess
import threading
import time
from dotenv import load_dotenv

load_dotenv()

import requests as http_requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from telegram.request import HTTPXRequest

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


def start_tor():
    try:
        proc = subprocess.Popen(
            ["tor", "--SocksPort", "9050", "--Log", "notice", "--DataDirectory", "/tmp/tor-data"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for i in range(30):
            try:
                r = http_requests.get(
                    "https://check.torproject.org/",
                    proxies={"https": "socks5://127.0.0.1:9050"},
                    timeout=5,
                )
                logger.info(f"Tor ready (attempt {i+1})")
                return proc
            except Exception:
                time.sleep(1)
        logger.warning("Tor did not become ready in 30s")
        return proc
    except Exception as e:
        logger.warning(f"Failed to start Tor: {e}")
        return None


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_handler():
    if bot_app is None or bot_loop is None:
        return "Bot not ready", 503
    update = Update.de_json(request.get_json(), bot_app.bot)
    asyncio.run_coroutine_threadsafe(
        bot_app.update_queue.put(update), bot_loop
    )
    return "OK", 200


@flask_app.route("/health")
def health():
    if bot_app is not None and bot_app.running:
        return "Bot OK", 200
    return "Starting...", 503


@flask_app.route("/diag")
def diag():
    import socket
    results = {}
    for host in ["api.telegram.org", "149.154.166.110", "149.154.167.220"]:
        try:
            r = http_requests.get(
                f"https://{host}/bot{config.TELEGRAM_BOT_TOKEN[:10]}/getMe",
                timeout=10,
                headers={"Host": "api.telegram.org"},
            )
            results[host] = r.status_code
        except Exception as e:
            results[host] = str(e)[:60]
    try:
        r = http_requests.get(
            "https://api.telegram.org/bot" + config.TELEGRAM_BOT_TOKEN[:10] + "/getMe",
            proxies={"https": "socks5://127.0.0.1:9050"},
            timeout=10,
        )
        results["via_tor"] = r.status_code
    except Exception as e:
        results["via_tor"] = str(e)[:60]
    return results, 200


def run_flask():
    port = int(os.getenv("PORT", "7860"))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


async def try_init_bot():
    global bot_app, bot_loop
    bot_loop = asyncio.get_running_loop()

    tor_proc = start_tor()
    proxy_url = "socks5://127.0.0.1:9050" if tor_proc else None

    req = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
        proxy_url=proxy_url,
    )

    for i in range(30):
        try:
            bot_app = (
                Application.builder()
                .token(config.TELEGRAM_BOT_TOKEN)
                .updater(None)
                .request(req)
                .build()
            )
            register_handlers(bot_app)
            await bot_app.initialize()
            await bot_app.start()

            base_url = os.getenv("BASE_URL", "")
            if not base_url:
                port = os.getenv("PORT", "7860")
                base_url = f"http://localhost:{port}"
            webhook_url = f"{base_url}{WEBHOOK_PATH}"
            await bot_app.bot.set_webhook(url=webhook_url)
            logger.info(f"Bot ready! Webhook: {webhook_url}")
            return
        except Exception as e:
            logger.warning(f"Bot init attempt {i+1}/30 failed: {e}")
            await asyncio.sleep(10 * (i + 1))

    logger.error("Bot init failed after 30 attempts — Flask still running")


async def bot_main():
    init_db()
    init_oauth_table()
    start_scheduler()
    await try_init_bot()
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
