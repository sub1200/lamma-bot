import logging
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request, jsonify, render_template_string

from database import save_account, get_conn, register_user, create_trial_subscription

logger = logging.getLogger(__name__)

app = Flask(__name__)

FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID", "")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

LOGIN_PAGE = """
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - Lamma</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 420px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        .logo { font-size: 64px; margin-bottom: 10px; }
        h1 { color: #1a1a2e; margin-bottom: 5px; font-size: 24px; }
        .sub { color: #888; margin-bottom: 30px; font-size: 14px; }
        .btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            margin-bottom: 12px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.15); }
        .btn-facebook { background: #1877f2; color: white; }
        .note { color: #aaa; font-size: 13px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🤖</div>
        <h1>Lamma</h1>
        <p class="sub">سجل دخولك بحساب فيسبوك لبدء استخدام البوت</p>
        <a href="{{ facebook_url }}" class="btn btn-facebook">
            تسجيل الدخول بحساب فيسبوك
        </a>
        <p class="note">بتسجيل الدخول، أنت توافق على <a href="{{ base_url }}/privacy" target="_blank">سياسة الخصوصية</a></p>
    </div>
</body>
</html>
"""

SUCCESS_PAGE = """
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><title>تم التسجيل</title>
<style>
    body { font-family: sans-serif; background: linear-gradient(135deg, #11998e, #38ef7d); min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }
    .card { background: white; border-radius: 20px; padding: 40px; text-align: center; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
    .icon { font-size: 64px; } h1 { color: #11998e; } p { color: #666; line-height: 1.8; }
</style>
</head>
<body>
    <div class="card">
        <div class="icon">✅</div>
        <h1>تم تسجيل الدخول بنجاح!</h1>
        <p>حسابك مرتبط مع البوت الآن.<br>ارجع إلى Telegram واضغط /start</p>
    </div>
</body>
</html>
"""


def init_oauth_tables():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS oauth_sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            token TEXT,
            page_id TEXT,
            page_name TEXT,
            email TEXT,
            provider_name TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT
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
    """)
    conn.commit()


def create_session(telegram_user_id: int, platform: str) -> str:
    session_id = uuid.uuid4().hex
    expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO oauth_sessions (id, user_id, platform, expires_at) VALUES (?, ?, ?, ?)",
        (session_id, telegram_user_id, platform, expires),
    )
    conn.commit()
    return session_id


def get_session(session_id: str):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM oauth_sessions WHERE id = ?", (session_id,))
    return cur.fetchone()


def update_session(session_id: str, **kwargs):
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [session_id]
    get_conn().execute(f"UPDATE oauth_sessions SET {fields} WHERE id = ?", values)
    get_conn().commit()


def link_account(user_id: int, provider: str, provider_id: str, email: str, name: str, token: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO linked_accounts (user_id, provider, provider_id, email, name, token) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, provider, provider_id, email, name, token),
    )
    conn.execute(
        "UPDATE users SET email = COALESCE(NULLIF(email, ''), ?) WHERE user_id = ?",
        (email, user_id),
    )
    conn.commit()


@app.route("/login/<session_id>")
def login_page(session_id: str):
    session = get_session(session_id)
    if not session:
        return "الرابط غير صالح أو منتهي الصلاحية.", 404

    facebook_url = f"{BASE_URL}/facebook_login/{session_id}"

    return render_template_string(
        LOGIN_PAGE,
        facebook_url=facebook_url,
        base_url=BASE_URL,
    )


@app.route("/facebook_login/<session_id>")
def facebook_login(session_id: str):
    session = get_session(session_id)
    if not session:
        return "الرابط غير صالح.", 404

    params = {
        "client_id": FACEBOOK_APP_ID,
        "redirect_uri": f"{BASE_URL}/callback/facebook",
        "state": session_id,
        "scope": "pages_manage_posts,pages_read_engagement,pages_show_list,instagram_basic,instagram_content_publish",
        "response_type": "code",
    }
    return redirect(f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}")


CALLBACK_LANDING = """
<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><title>Lamma - تسجيل الدخول</title>
<style>
    body { font-family: sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }
    .card { background: white; border-radius: 20px; padding: 40px; text-align: center; max-width: 420px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
    .icon { font-size: 64px; } h1 { color: #1a1a2e; } p { color: #666; line-height: 1.8; }
</style>
</head>
<body>
    <div class="card">
        <div class="icon">🔐</div>
        <h1>تسجيل الدخول عبر فيسبوك</h1>
        <p>هذه الصفحة تستقبل بيانات تسجيل الدخول من فيسبوك.<br>
        استخدم البوت على Telegram لبدء عملية الربط.</p>
        <p style="font-size:13px;color:#999;">&copy; Lamma Bot</p>
    </div>
</body>
</html>
"""


@app.route("/callback/facebook")
def facebook_callback():
    code = request.args.get("code")
    session_id = request.args.get("state")

    if not code or not session_id:
        return CALLBACK_LANDING, 200

    session = get_session(session_id)
    if not session:
        return "الجلسة غير صالحة.", 404

    token_url = "https://graph.facebook.com/v19.0/oauth/access_token"
    resp = requests.get(token_url, params={
        "client_id": FACEBOOK_APP_ID,
        "redirect_uri": f"{BASE_URL}/callback/facebook",
        "client_secret": FACEBOOK_APP_SECRET,
        "code": code,
    })
    data = resp.json()

    if "access_token" not in data:
        logger.error(f"Facebook token exchange failed: {data}")
        return "فشل تسجيل الدخول إلى فيسبوك.", 400

    short_token = data["access_token"]

    long_url = "https://graph.facebook.com/v19.0/oauth/access_token"
    long_resp = requests.get(long_url, params={
        "grant_type": "fb_exchange_token",
        "client_id": FACEBOOK_APP_ID,
        "client_secret": FACEBOOK_APP_SECRET,
        "fb_exchange_token": short_token,
    })
    long_data = long_resp.json()
    long_token = long_data.get("access_token", short_token)

    me_resp = requests.get("https://graph.facebook.com/v19.0/me", params={
        "access_token": long_token,
        "fields": "id,name,email",
    })
    me_data = me_resp.json()

    telegram_user_id = session["user_id"]
    register_user(telegram_user_id)
    create_trial_subscription(telegram_user_id)
    fb_id = me_data.get("id", "")
    fb_name = me_data.get("name", "")
    fb_email = me_data.get("email", "")
    link_account(telegram_user_id, "facebook", fb_id, fb_email, fb_name, long_token)

    pages_resp = requests.get("https://graph.facebook.com/v19.0/me/accounts", params={
        "access_token": long_token,
    })
    pages_data = pages_resp.json()

    page_id = ""
    page_token = ""
    page_name = ""

    for page in pages_data.get("data", []):
        page_id = page["id"]
        page_token = page["access_token"]
        page_name = page["name"]
        break

    if page_id:
        save_account(session["platform"], page_token, page_id=page_id)

    update_session(session_id, status="linked", email=fb_email, provider_name=fb_name, token=long_token)

    return SUCCESS_PAGE


@app.route("/status/<session_id>")
def session_status(session_id: str):
    session = get_session(session_id)
    if not session:
        return jsonify({"status": "invalid"})
    return jsonify({
        "status": session["status"],
        "platform": session["platform"],
        "email": session["email"],
        "provider_name": session["provider_name"],
    })


@app.route("/privacy")
def privacy_policy():
    return """
    <!DOCTYPE html>
    <html dir="rtl">
    <head><meta charset="UTF-8"><title>سياسة الخصوصية</title>
    <style>body{font-family:sans-serif;padding:40px;max-width:700px;margin:auto;line-height:1.8}
    h1{color:#333}</style>
    </head>
    <body>
        <h1>سياسة الخصوصية</h1>
        <p>هذا البوت يجمع فقط البيانات اللازمة لعمل الخدمة: معرف المستخدم في Telegram والبريد الإلكتروني.
        لا يتم مشاركة هذه البيانات مع أطراف ثالثة. يمكنك طلب حذف بياناتك في أي وقت عبر البوت.</p>
        <p>آخر تحديث: 2026</p>
    </body>
    </html>
    """


def start_web_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    init_oauth_tables()
    logger.info(f"Web server starting on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
