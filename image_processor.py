import logging
import io
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

STYLES = {
    "professional": {
        "label": "احترافي - خلفية بيضاء",
        "action": "professional",
    },
    "lifestyle": {
        "label": "لايف ستايل - استخدام واقعي",
        "action": "lifestyle",
    },
    "3d_mockup": {
        "label": "موديل ثلاثي الأبعاد",
        "action": "3d_mockup",
    },
    "minimalist": {
        "label": "بساطة - تصميم أنيق",
        "action": "minimalist",
    },
    "social_media": {
        "label": "سوشيال ميديا - جذاب",
        "action": "social_media",
    },
    "luxury": {
        "label": "فاخر - راقي",
        "action": "luxury",
    },
}


def apply_style(img: Image.Image, action: str) -> Image.Image:
    if action == "professional":
        bg = Image.new("RGB", (int(img.width * 1.2), int(img.height * 1.2)), (255, 255, 255))
        offset = ((bg.width - img.width) // 2, (bg.height - img.height) // 2)
        bg.paste(img, offset)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.15)
        return bg

    elif action == "lifestyle":
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.3)
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)
        img = img.filter(ImageFilter.SMOOTH_MORE)
        return img

    elif action == "3d_mockup":
        img = img.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.25)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.2)
        img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
        return img

    elif action == "minimalist":
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(0.7)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.05)
        bg = Image.new("RGB", (int(img.width * 1.4), int(img.height * 1.4)), (245, 245, 240))
        offset = ((bg.width - img.width) // 2, (bg.height - img.height) // 2)
        bg.paste(img, offset)
        return bg

    elif action == "social_media":
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.5)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.15)
        return img

    elif action == "luxury":
        img = img.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(1.1)
        img = ImageOps.expand(img, border=8, fill=(192, 168, 128))
        img = ImageOps.expand(img, border=2, fill=(128, 100, 64))
        return img

    return img


def transform_product_image(
    image_bytes: bytes,
    style: str,
) -> Optional[bytes]:
    style_config = STYLES.get(style)
    if not style_config:
        logger.error(f"Unknown style: {style}")
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((1024, 1024), Image.LANCZOS)
        img = apply_style(img, style_config["action"])

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    except Exception as e:
        logger.error(f"Image transform error: {e}")
        return None
