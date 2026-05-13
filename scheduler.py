import threading
import time
import logging
from datetime import datetime

from database import get_pending_schedules, mark_schedule_done, save_post
from facebook_publisher import publish_post as fb_publish
from instagram_publisher import publish_post as ig_publish

logger = logging.getLogger(__name__)


_scheduler_thread: threading.Thread | None = None
_running = False


def start_scheduler():
    global _scheduler_thread, _running
    if _running:
        return
    _running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Scheduler started")


def stop_scheduler():
    global _running
    _running = False


def _scheduler_loop():
    while _running:
        try:
            schedules = get_pending_schedules()
            for s in schedules:
                platforms = s["platforms"].split(",")
                content = s["content"]
                for platform in platforms:
                    platform = platform.strip()
                    try:
                        if platform == "facebook":
                            post_id = fb_publish(content)
                        elif platform == "instagram":
                            post_id = ig_publish(content)
                        else:
                            continue
                        save_post(content, platform, post_id, "published")
                    except Exception as e:
                        logger.error(f"Schedule publish error on {platform}: {e}")
                        save_post(content, platform, status="failed")
                mark_schedule_done(s["id"])
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
        time.sleep(30)
