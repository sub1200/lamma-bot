import logging
import requests
from typing import Optional

from database import get_setting

logger = logging.getLogger(__name__)

HF_API = "https://api-inference.huggingface.co/models"

STYLES = {
    "professional": {
        "label": "احترافي - خلفية بيضاء",
        "prompt": "Transform this product into a professional product photo, white background, studio lighting",
    },
    "lifestyle": {
        "label": "لايف ستايل - استخدام واقعي",
        "prompt": "Transform this product into a lifestyle photo, natural setting, realistic use, warm lighting",
    },
    "3d_mockup": {
        "label": "موديل ثلاثي الأبعاد",
        "prompt": "Transform this product into a 3D render mockup, isometric view, modern design",
    },
    "minimalist": {
        "label": "بساطة - تصميم أنيق",
        "prompt": "Transform this product into a minimalist style, clean background, elegant, soft lighting",
    },
    "social_media": {
        "label": "سوشيال ميديا - جذاب",
        "prompt": "Transform this product for social media, eye-catching, vibrant colors, instagram style",
    },
    "luxury": {
        "label": "فاخر - راقي",
        "prompt": "Transform this product into luxury style, gold accents, dramatic lighting, premium feel",
    },
}


def get_hf_token() -> Optional[str]:
    key = get_setting("hf_api_token", "")
    return key if key else None


def transform_product_image(
    image_bytes: bytes,
    style: str,
) -> Optional[bytes]:
    token = get_hf_token()
    if not token:
        logger.error("Hugging Face token not set")
        return None

    style_config = STYLES.get(style)
    if not style_config:
        logger.error(f"Unknown style: {style}")
        return None

    prompt = style_config["prompt"]

    headers = {"Authorization": f"Bearer {token}"}
    model = "stabilityai/stable-diffusion-2-1"

    try:
        resp = requests.post(
            f"{HF_API}/{model}",
            headers=headers,
            files={"image": ("image.png", image_bytes, "image/png")},
            data={"inputs": prompt},
            timeout=120,
        )

        if resp.status_code == 200:
            return resp.content

        if resp.status_code == 503:
            logger.info("Model is loading on HF, retrying...")
            import time
            time.sleep(20)
            resp = requests.post(
                f"{HF_API}/{model}",
                headers=headers,
                files={"image": ("image.png", image_bytes, "image/png")},
                data={"inputs": prompt},
                timeout=120,
            )
            if resp.status_code == 200:
                return resp.content

        logger.error(f"HF API error ({resp.status_code}): {resp.text[:200]}")
        return None

    except requests.RequestException as e:
        logger.error(f"HF request failed: {e}")
        return None
