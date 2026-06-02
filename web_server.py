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
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
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
        .btn-google { background: #fff; color: #333; border: 1px solid #ddd; }
        .btn-facebook { background: #1877f2; color: white; }
        .divider {
            display: flex; align-items: center; gap: 10px; margin: 20px 0; color: #aaa;
        }
        .divider::before, .divider::after {
            content: ""; flex: 1; height: 1px; background: #eee;
        }
        .note { color: #aaa; font-size: 13px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🤖</div>
        <h1>Lamma</h1>
        <p class="sub">سجل دخولك لبدء استخدام البوت</p>
        <a href="{{ google_url }}" class="btn btn-google">
            <svg width="20" height="20" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            تسجيل الدخول بحساب Google
        </a>
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

    google_url = f"{BASE_URL}/google_login/{session_id}"
    facebook_url = f"{BASE_URL}/facebook_login/{session_id}"

    return render_template_string(
        LOGIN_PAGE,
        google_url=google_url,
        facebook_url=facebook_url,
        base_url=BASE_URL,
    )


@app.route("/google_login/<session_id>")
def google_login(session_id: str):
    session = get_session(session_id)
    if not session:
        return "الرابط غير صالح.", 404

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{BASE_URL}/callback/google",
        "state": session_id,
        "scope": "openid email profile",
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@app.route("/callback/google")
def google_callback():
    code = request.args.get("code")
    session_id = request.args.get("state")

    if not code or not session_id:
        return "<h1>خطأ: معلمات غير صالحة</h1>", 400

    session = get_session(session_id)
    if not session:
        return "الجلسة غير صالحة.", 404

    token_resp = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": f"{BASE_URL}/callback/google",
        "grant_type": "authorization_code",
    })
    token_data = token_resp.json()

    if "access_token" not in token_data:
        logger.error(f"Google token exchange failed: {token_data}")
        return "فشل تسجيل الدخول بحساب Google.", 400

    access_token = token_data["access_token"]

    user_resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={
        "Authorization": f"Bearer {access_token}",
    })
    user_data = user_resp.json()

    email = user_data.get("email", "")
    name = user_data.get("name", "")
    google_id = user_data.get("id", "")

    telegram_user_id = session["user_id"]
    register_user(telegram_user_id)
    create_trial_subscription(telegram_user_id)
    link_account(telegram_user_id, "google", google_id, email, name, access_token)

    update_session(session_id, status="linked", email=email, provider_name=name, token=access_token)

    return SUCCESS_PAGE


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
