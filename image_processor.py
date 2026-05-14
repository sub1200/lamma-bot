import io
import logging
from typing import Optional
from urllib.parse import quote
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import requests

logger = logging.getLogger(__name__)

POLLINATIONS_URL = "https://image.pollinations.ai/prompt"

STYLES = {
    "professional": {
        "label": "احترافي - خلفية بيضاء",
        "action": "professional",
        "prompt": "professional product photo, white background, studio lighting, high quality",
    },
    "lifestyle": {
        "label": "لايف ستايل - استخدام واقعي",
        "action": "lifestyle",
        "prompt": "lifestyle product photo, natural setting, realistic use, warm lighting",
    },
    "3d_mockup": {
        "label": "موديل ثلاثي الأبعاد",
        "action": "3d_mockup",
        "prompt": "3D render mockup of product, isometric view, modern design, high detail",
    },
    "minimalist": {
        "label": "بساطة - تصميم أنيق",
        "action": "minimalist",
        "prompt": "minimalist product photo, clean background, elegant, soft lighting",
    },
    "social_media": {
        "label": "سوشيال ميديا - جذاب",
        "action": "social_media",
        "prompt": "social media product photo, eye-catching, vibrant colors, instagram style",
    },
    "luxury": {
        "label": "فاخر - راقي",
        "action": "luxury",
        "prompt": "luxury product photo, gold accents, dramatic lighting, premium feel",
    },
}


def generate_ai_image(prompt: str) -> Optional[bytes]:
    try:
        resp = requests.get(
            f"{POLLINATIONS_URL}/{quote(prompt)}",
            params={"nofeed": "true", "width": 1024, "height": 1024},
            timeout=60,
        )
        if resp.status_code == 200:
            logger.info(f"Pollinations AI image generated ({len(resp.content)} bytes)")
            return resp.content
        logger.warning(f"Pollinations error: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Pollinations failed: {e}")
    return None


def apply_pillow_style(img: Image.Image, action: str) -> Image.Image:
    if action == "professional":
        bg = Image.new("RGB", (int(img.width * 1.2), int(img.height * 1.2)), (255, 255, 255))
        offset = ((bg.width - img.width) // 2, (bg.height - img.height) // 2)
        bg.paste(img, offset)
        return bg
    elif action == "lifestyle":
        img = ImageEnhance.Color(img).enhance(1.3)
        img = ImageEnhance.Brightness(img).enhance(1.1)
        return img.filter(ImageFilter.SMOOTH_MORE)
    elif action == "3d_mockup":
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(1.25)
        img = ImageEnhance.Color(img).enhance(1.2)
        return img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    elif action == "minimalist":
        img = ImageEnhance.Color(img).enhance(0.7)
        img = ImageEnhance.Contrast(img).enhance(1.05)
        bg = Image.new("RGB", (int(img.width * 1.4), int(img.height * 1.4)), (245, 245, 240))
        offset = ((bg.width - img.width) // 2, (bg.height - img.height) // 2)
        bg.paste(img, offset)
        return bg
    elif action == "social_media":
        img = ImageEnhance.Color(img).enhance(1.5)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        return ImageEnhance.Brightness(img).enhance(1.15)
    elif action == "luxury":
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Color(img).enhance(1.1)
        img = ImageOps.expand(img, border=8, fill=(192, 168, 128))
        img = ImageOps.expand(img, border=2, fill=(128, 100, 64))
        return img
    return img


def transform_product_image(
    image_bytes: bytes,
    style: str,
    description: str = "",
) -> Optional[bytes]:
    style_config = STYLES.get(style)
    if not style_config:
        logger.error(f"Unknown style: {style}")
        return None

    if description:
        prompt = f"{description}, {style_config['prompt']}"
        result = generate_ai_image(prompt)
        if result:
            return result

    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.thumbnail((1024, 1024), Image.LANCZOS)
        img = apply_pillow_style(img, style_config["action"])
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        logger.info(f"Pillow fallback used for style: {style}")
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Image transform error: {e}")
        return None


def text_to_image(prompt: str) -> Optional[bytes]:
    return generate_ai_image(prompt)
