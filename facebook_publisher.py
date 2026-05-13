from typing import Optional
import requests

from database import get_account


GRAPH_API = "https://graph.facebook.com/v19.0"


def get_token() -> Optional[str]:
    account = get_account("facebook")
    if account:
        return account["token"]
    return None


def get_page_id() -> Optional[str]:
    account = get_account("facebook")
    if account:
        return account["page_id"]
    return None


def publish_post(content: str) -> Optional[str]:
    token = get_token()
    page_id = get_page_id()
    if not token or not page_id:
        return None

    url = f"{GRAPH_API}/{page_id}/feed"
    resp = requests.post(url, data={
        "message": content,
        "access_token": token,
    })
    data = resp.json()
    if "id" in data:
        return data["id"]
    raise Exception(f"Facebook publish failed: {data}")


def publish_video(video_bytes: bytes, description: str = "") -> Optional[str]:
    token = get_token()
    page_id = get_page_id()
    if not token or not page_id:
        return None

    url = f"{GRAPH_API}/{page_id}/videos"
    files = {"source": ("video.mp4", video_bytes, "video/mp4")}
    data = {"description": description, "access_token": token}

    resp = requests.post(url, files=files, data=data)
    result = resp.json()
    if "id" in result:
        return result["id"]
    raise Exception(f"Facebook video publish failed: {result}")


def get_page_comments(page_post_id: str) -> list[dict]:
    token = get_token()
    if not token:
        return []

    url = f"{GRAPH_API}/{page_post_id}/comments"
    resp = requests.get(url, params={"access_token": token})
    data = resp.json()
    return data.get("data", [])


def reply_to_comment(comment_id: str, message: str) -> bool:
    token = get_token()
    if not token:
        return False

    url = f"{GRAPH_API}/{comment_id}/comments"
    resp = requests.post(url, data={
        "message": message,
        "access_token": token,
    })
    return resp.status_code == 200
