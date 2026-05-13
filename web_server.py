import logging
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request, jsonify, render_template_string

from database import save_account, get_conn

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
    <title>ربط الحساب</title>
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
        .icon { font-size: 64px; margin-bottom: 20px; }
        h1 { color: #1a1a2e; margin-bottom: 10px; font-size: 24px; }
        p { color: #666; margin-bottom: 30px; line-height: 1.6; }
        .btn {
            display: block;
            width: 100%;
            padding: 16px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            margin-bottom: 12px;
            transition: transform 0.2s;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn-facebook {
            background: #1877f2;
            color: white;
        }
        .btn-email {
            background: #f0f0f0;
            color: #333;
        }
        .warning {
            background: #fff3cd;
            color: #856404;
            padding: 12px;
            border-radius: 10px;
            font-size: 13px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">🔐</div>
        <h1>ربط حساب {{ platform }}</h1>
        <p>اختر طريقة تسجيل الدخول لربط حسابك مع البوت</p>
        <a href="{{ facebook_url }}" class="btn btn-facebook">
            تسجيل الدخول عبر فيسبوك
        </a>
        <a href="{{ email_url }}" class="btn btn-email">
            تسجيل الدخول بالبريد الإلكتروني
        </a>
        <div class="warning">
            ⏰ الرابط صالح لمدة 24 ساعة فقط
        </div>
    </div>
</body>
</html>
"""


def init_oauth_table():
    conn = get_conn()
    conn.execute("""
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
        )
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


def update_session_token(session_id: str, token: str, page_id: str, page_name: str = ""):
    conn = get_conn()
    conn.execute(
        "UPDATE oauth_sessions SET status = 'linked', token = ?, page_id = ?, page_name = ? WHERE id = ?",
        (token, page_id, page_name, session_id),
    )
    conn.commit()


@app.route("/login/<session_id>")
def login_page(session_id: str):
    session = get_session(session_id)
    if not session:
        return "الرابط غير صالح أو منتهي الصلاحية.", 404

    facebook_url = f"{BASE_URL}/facebook_login/{session_id}"
    email_url = f"{BASE_URL}/email_login/{session_id}"

    return render_template_string(
        LOGIN_PAGE,
        platform=session["platform"],
        facebook_url=facebook_url,
        email_url=email_url,
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


@app.route("/callback/facebook")
def facebook_callback():
    code = request.args.get("code")
    session_id = request.args.get("state")

    if not code or not session_id:
        return "معلمات غير صالحة.", 400

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

    if not page_id:
        return "لم يتم العثور على صفحات. تأكد من أن لديك صفحة فيسبوك.", 400

    save_account(session["platform"], page_token, page_id=page_id)
    update_session_token(session_id, page_token, page_id, page_name)

    return render_template_string("""
    <!DOCTYPE html>
    <html dir="rtl">
    <head><meta charset="UTF-8"><title>تم الربط</title>
    <style>
        body { font-family: sans-serif; background: linear-gradient(135deg, #11998e, #38ef7d); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .card { background: white; border-radius: 20px; padding: 40px; text-align: center; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
        h1 { color: #11998e; } .icon { font-size: 64px; }
    </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h1>تم الربط بنجاح!</h1>
            <p>حساب {{ page_name }} مرتبط مع البوت الآن.<br>ارجع إلى Telegram واستخدم /start</p>
        </div>
    </body>
    </html>
    """, page_name=page_name)


@app.route("/status/<session_id>")
def session_status(session_id: str):
    session = get_session(session_id)
    if not session:
        return jsonify({"status": "invalid"})
    return jsonify({
        "status": session["status"],
        "platform": session["platform"],
        "page_name": session["page_name"],
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
        <p>هذا البوت يجمع فقط البيانات اللازمة لعمل الخدمة: معرف المستخدم في Telegram وتوكنات صفحات فيسبوك.
        لا يتم مشاركة هذه البيانات مع أطراف ثالثة. يمكنك طلب حذف بياناتك في أي وقت عبر البوت.</p>
        <p>آخر تحديث: 2026</p>
    </body>
    </html>
    """


def start_web_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    init_oauth_table()
    logger.info(f"Web server starting on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
