import time
import logging

from database import get_reply_rules, get_setting
from ai_generator import generate_comment_reply
from facebook_publisher import get_page_comments, reply_to_comment as fb_reply
from instagram_publisher import get_media_comments, reply_to_comment as ig_reply

logger = logging.getLogger(__name__)


def run_auto_reply_cycle():
    enabled = get_setting("auto_reply_enabled", "0")
    if enabled != "1":
        return

    language = get_setting("language", "ar")

    fb_rules = get_reply_rules("facebook")
    ig_rules = get_reply_rules("instagram")

    processed = get_setting("last_processed_comment_id", "0")
    last_id = int(processed)

    if fb_rules:
        try:
            _process_facebook_comments(last_id, language)
        except Exception as e:
            logger.error(f"Facebook auto-reply error: {e}")

    if ig_rules:
        try:
            _process_instagram_comments(last_id, language)
        except Exception as e:
            logger.error(f"Instagram auto-reply error: {e}")


def _process_facebook_comments(last_id: int, language: str):
    from database import get_conn

    comments = get_page_comments("me")
    new_last = last_id
    for c in comments:
        cid = int(c.get("id", "0"))
        if cid > last_id:
            reply = generate_comment_reply(c.get("message", ""), language)
            fb_reply(c["id"], reply)
            if cid > new_last:
                new_last = cid
    if new_last > last_id:
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_processed_comment_id', ?)",
            (str(new_last),),
        )
        conn.commit()


def _process_instagram_comments(last_id: int, language: str):
    from database import get_conn

    comments = get_media_comments("me")
    new_last = last_id
    for c in comments:
        cid = int(c.get("id", "0"))
        if cid > last_id:
            reply = generate_comment_reply(c.get("text", ""), language)
            ig_reply(c["id"], reply)
            if cid > new_last:
                new_last = cid
    if new_last > last_id:
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_processed_comment_id', ?)",
            (str(new_last),),
        )
        conn.commit()
