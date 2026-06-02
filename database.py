import sqlite3
import threading
from datetime import datetime
from typing import Optional

from datetime import datetime, timedelta
from typing import Optional

from config import config


_LOCAL = threading.local()


def get_conn() -> sqlite3.Connection:
    if not hasattr(_LOCAL, "conn") or _LOCAL.conn is None:
        _LOCAL.conn = sqlite3.connect(config.DATABASE_PATH)
        _LOCAL.conn.row_factory = sqlite3.Row
    return _LOCAL.conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            token TEXT NOT NULL,
            page_id TEXT,
            user_id TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            platforms TEXT NOT NULL,
            scheduled_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            platform TEXT NOT NULL,
            post_id TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS auto_reply_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            keywords TEXT,
            reply_template TEXT,
            enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS oauth_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            token TEXT,
            page_id TEXT,
            page_name TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            email TEXT DEFAULT '',
            language TEXT DEFAULT 'ar',
            plan TEXT DEFAULT 'free',
            credits INTEGER DEFAULT 10,
            registration_date TEXT DEFAULT (datetime('now')),
            last_active TEXT
        );

        CREATE TABLE IF NOT EXISTS linked_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            provider_id TEXT,
            email TEXT,
            name TEXT,
            token TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_type TEXT,
            start_date TEXT,
            end_date TEXT,
            payment_status TEXT DEFAULT 'pending',
            transaction_id TEXT
        );

        CREATE TABLE IF NOT EXISTS credit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            action TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def register_user(user_id: int, username: str = "", full_name: str = ""):
    conn = get_conn()
    cur = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cur.fetchone():
        conn.execute(
            "INSERT INTO users (user_id, username, full_name, credits) VALUES (?, ?, ?, 10)",
            (user_id, username, full_name),
        )
        conn.commit()


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()


def update_user_plan(user_id: int, plan: str, credits: Optional[int] = None):
    conn = get_conn()
    if credits is not None:
        conn.execute("UPDATE users SET plan = ?, credits = ?, last_active = datetime('now') WHERE user_id = ?",
                     (plan, credits, user_id))
    else:
        conn.execute("UPDATE users SET plan = ?, last_active = datetime('now') WHERE user_id = ?",
                     (plan, user_id))
    conn.commit()


def deduct_credits(user_id: int, amount: int) -> bool:
    conn = get_conn()
    user = get_user(user_id)
    if user and user["credits"] >= amount:
        conn.execute("UPDATE users SET credits = credits - ?, last_active = datetime('now') WHERE user_id = ?",
                     (amount, user_id))
        conn.execute("INSERT INTO credit_logs (user_id, amount, action) VALUES (?, ?, 'usage')",
                     (user_id, amount))
        conn.commit()
        return True
    return False


def add_credits(user_id: int, amount: int, action: str = "purchase"):
    conn = get_conn()
    conn.execute("UPDATE users SET credits = credits + ?, last_active = datetime('now') WHERE user_id = ?",
                 (amount, user_id))
    conn.execute("INSERT INTO credit_logs (user_id, amount, action) VALUES (?, ?, ?)",
                 (user_id, amount, action))
    conn.commit()


def get_setting(key: str, default: str = "") -> str:
    cur = get_conn().execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    get_conn().execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )
    get_conn().commit()


def save_account(platform: str, token: str, page_id: str = "", user_id: str = ""):
    get_conn().execute(
        "INSERT INTO accounts (platform, token, page_id, user_id) VALUES (?, ?, ?, ?)",
        (platform, token, page_id, user_id),
    )
    get_conn().commit()


def get_account(platform: str) -> Optional[sqlite3.Row]:
    cur = get_conn().execute(
        "SELECT * FROM accounts WHERE platform = ? AND active = 1 ORDER BY id DESC LIMIT 1",
        (platform,),
    )
    return cur.fetchone()


def list_accounts():
    cur = get_conn().execute("SELECT * FROM accounts WHERE active = 1")
    return cur.fetchall()


def delete_account(account_id: int):
    get_conn().execute("UPDATE accounts SET active = 0 WHERE id = ?", (account_id,))
    get_conn().commit()


def save_post(content: str, platform: str, post_id: str = "", status: str = "draft") -> int:
    cur = get_conn().execute(
        "INSERT INTO posts (content, platform, post_id, status) VALUES (?, ?, ?, ?)",
        (content, platform, post_id, status),
    )
    get_conn().commit()
    return cur.lastrowid


def save_schedule(content: str, platforms: str, scheduled_at: str) -> int:
    cur = get_conn().execute(
        "INSERT INTO schedules (content, platforms, scheduled_at) VALUES (?, ?, ?)",
        (content, platforms, scheduled_at),
    )
    get_conn().commit()
    return cur.lastrowid


def get_pending_schedules():
    cur = get_conn().execute(
        "SELECT * FROM schedules WHERE status = 'pending' AND scheduled_at <= datetime('now')"
    )
    return cur.fetchall()


def mark_schedule_done(schedule_id: int):
    get_conn().execute("UPDATE schedules SET status = 'done' WHERE id = ?", (schedule_id,))
    get_conn().commit()


def get_reply_rules(platform: str):
    cur = get_conn().execute(
        "SELECT * FROM auto_reply_rules WHERE platform = ? ORDER BY id",
        (platform,),
    )
    return cur.fetchall()


def add_reply_rule(platform: str, keywords: str, reply_template: str):
    get_conn().execute(
        "INSERT INTO auto_reply_rules (platform, keywords, reply_template) VALUES (?, ?, ?)",
        (platform, keywords, reply_template),
    )
    get_conn().commit()


def delete_reply_rule(rule_id: int):
    get_conn().execute("DELETE FROM auto_reply_rules WHERE id = ?", (rule_id,))
    get_conn().commit()


def set_reply_rule_enabled(rule_id: int):
    cur = get_conn().execute("SELECT enabled FROM auto_reply_rules WHERE id = ?", (rule_id,))
    row = cur.fetchone()
    if row:
        new_val = 0 if row["enabled"] else 1
        get_conn().execute("UPDATE auto_reply_rules SET enabled = ? WHERE id = ?", (new_val, rule_id))
        get_conn().commit()


TRIAL_DAYS = 7
TRIAL_CREDITS = 50


def create_trial_subscription(user_id: int) -> bool:
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM subscriptions WHERE user_id = ? AND plan_type = 'trial'",
        (user_id,),
    ).fetchone()
    if existing:
        return False
    start = datetime.utcnow().isoformat()
    end = (datetime.utcnow() + timedelta(days=TRIAL_DAYS)).isoformat()
    conn.execute(
        "INSERT INTO subscriptions (user_id, plan_type, start_date, end_date, payment_status) VALUES (?, 'trial', ?, ?, 'active')",
        (user_id, start, end),
    )
    conn.execute(
        "UPDATE users SET plan = 'trial', credits = credits + ? WHERE user_id = ?",
        (TRIAL_CREDITS, user_id),
    )
    conn.execute(
        "INSERT INTO credit_logs (user_id, amount, action) VALUES (?, ?, 'trial_bonus')",
        (user_id, TRIAL_CREDITS),
    )
    conn.commit()
    return True


def get_active_subscription(user_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    cur = conn.execute(
        "SELECT * FROM subscriptions WHERE user_id = ? AND payment_status = 'active' ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    return cur.fetchone()


def is_trial_active(user_id: int) -> bool:
    sub = get_active_subscription(user_id)
    if not sub:
        return False
    if sub["plan_type"] != "trial":
        return True
    try:
        end = datetime.fromisoformat(sub["end_date"])
        return datetime.utcnow() < end
    except (ValueError, TypeError):
        return False


def get_trial_days_remaining(user_id: int) -> int:
    sub = get_active_subscription(user_id)
    if not sub:
        return 0
    try:
        end = datetime.fromisoformat(sub["end_date"])
        remaining = (end - datetime.utcnow()).days
        return max(0, remaining)
    except (ValueError, TypeError):
        return 0
