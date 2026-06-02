import base64
import io
import logging
from typing import Optional

import requests
from PIL import Image

from config import config

logger = logging.getLogger(__name__)


def generate_image(prompt: str) -> Optional[bytes]:
    """Generate image using Gemini API. Falls back to Pollinations on failure."""
    from image_processor import text_to_image as pollinations_fallback

    if not config.GEMINI_API_KEY:
        return pollinations_fallback(prompt)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={config.GEMINI_API_KEY}"
    body = {
        "contents": [{"parts": [{"text": f"Generate a high-quality photorealistic image: {prompt}. Professional lighting."}]}],
        "generationConfig": {"temperature": 1, "topP": 0.95, "maxOutputTokens": 8192},
    }

    try:
        resp = requests.post(url, json=body, timeout=90)
        data = resp.json()
        try:
            for part in data["candidates"][0]["content"]["parts"]:
                if "inline_data" in part:
                    return base64.b64decode(part["inline_data"]["data"])
        except (KeyError, IndexError, TypeError):
            pass
        logger.warning(f"Gemini no image, fallback to Pollinations")
    except Exception as e:
        logger.warning(f"Gemini failed ({e}), fallback to Pollinations")

    return pollinations_fallback(prompt)


def edit_image(image_bytes: bytes, prompt: str) -> Optional[bytes]:
    """Edit image using Gemini. Falls back to Pillow compositing on failure."""
    from image_processor import transform_product_image

    if not config.GEMINI_API_KEY:
        return transform_product_image(image_bytes, "professional", prompt)

    img = Image.open(io.BytesIO(image_bytes))
    img.thumbnail((1024, 1024), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={config.GEMINI_API_KEY}"
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": 1, "topP": 0.95, "maxOutputTokens": 8192},
    }

    try:
        resp = requests.post(url, json=body, timeout=90)
        data = resp.json()
        try:
            for part in data["candidates"][0]["content"]["parts"]:
                if "inline_data" in part:
                    return base64.b64decode(part["inline_data"]["data"])
        except (KeyError, IndexError, TypeError):
            pass
        logger.warning("Gemini edit failed, fallback to Pillow")
    except Exception as e:
        logger.warning(f"Gemini edit error ({e}), fallback to Pillow")

    return transform_product_image(image_bytes, "professional", prompt)
