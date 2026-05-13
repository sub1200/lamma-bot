from typing import Optional
import requests

from database import get_account


GRAPH_API = "https://graph.facebook.com/v19.0"


def get_token() -> Optional[str]:
    account = get_account("instagram")
    if account:
        return account["token"]
    return None


def get_user_id() -> Optional[str]:
    account = get_account("instagram")
    if account:
        return account["user_id"]
    return None


def publish_post(content: str) -> Optional[str]:
    token = get_token()
    user_id = get_user_id()
    if not token or not user_id:
        return None

    url = f"{GRAPH_API}/{user_id}/media"
    resp = requests.post(url, data={
        "caption": content,
        "access_token": token,
    })
    data = resp.json()
    if "id" not in data:
        raise Exception(f"Instagram media creation failed: {data}")

    creation_id = data["id"]
    publish_url = f"{GRAPH_API}/{user_id}/media_publish"
    pub_resp = requests.post(publish_url, data={
        "creation_id": creation_id,
        "access_token": token,
    })
    pub_data = pub_resp.json()
    if "id" in pub_data:
        return pub_data["id"]
    raise Exception(f"Instagram publish failed: {pub_data}")


def publish_video(video_bytes: bytes, caption: str = "") -> Optional[str]:
    token = get_token()
    user_id = get_user_id()
    if not token or not user_id:
        return None

    url = f"{GRAPH_API}/{user_id}/media"
    resp = requests.post(url, data={
        "media_type": "VIDEO",
        "video_url": "https://...",  # needs hosted URL
        "caption": caption,
        "access_token": token,
    })
    data = resp.json()
    if "id" not in data:
        raise Exception(f"Instagram video creation failed: {data}")

    creation_id = data["id"]
    publish_url = f"{GRAPH_API}/{user_id}/media_publish"
    pub_resp = requests.post(publish_url, data={
        "creation_id": creation_id,
        "access_token": token,
    })
    pub_data = pub_resp.json()
    if "id" in pub_data:
        return pub_data["id"]
    raise Exception(f"Instagram video publish failed: {pub_data}")


def get_media_comments(media_id: str) -> list[dict]:
    token = get_token()
    if not token:
        return []

    url = f"{GRAPH_API}/{media_id}/comments"
    resp = requests.get(url, params={"access_token": token})
    data = resp.json()
    return data.get("data", [])


def reply_to_comment(comment_id: str, message: str) -> bool:
    token = get_token()
    if not token:
        return False

    url = f"{GRAPH_API}/{comment_id}/replies"
    resp = requests.post(url, data={
        "message": message,
        "access_token": token,
    })
    return resp.status_code == 200
