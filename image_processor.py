import io
import logging
from typing import Optional
from urllib.parse import quote
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import requests

logger = logging.getLogger(__name__)

POLLINATIONS_URL = "https://image.pollinations.ai/prompt"


def _auto_enhance(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Brightness(img).enhance(1.05)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(1.1)
    return img


def _apply_warm_tone(img: Image.Image) -> Image.Image:
    r, g, b = img.split()
    r = r.point(lambda i: min(255, i * 1.1))
    b = b.point(lambda i: i * 0.9)
    return Image.merge("RGB", (r, g, b))


def _apply_cool_tone(img: Image.Image) -> Image.Image:
    r, g, b = img.split()
    b = b.point(lambda i: min(255, i * 1.15))
    r = r.point(lambda i: i * 0.9)
    return Image.merge("RGB", (r, g, b))


def _apply_golden_tone(img: Image.Image) -> Image.Image:
    r, g, b = img.split()
    r = r.point(lambda i: min(255, i * 1.08))
    g = g.point(lambda i: min(255, i * 0.95))
    b = b.point(lambda i: i * 0.7)
    return Image.merge("RGB", (r, g, b))


def _apply_vignette(img: Image.Image) -> Image.Image:
    w, h = img.size
    cx, cy = w // 2, h // 2
    max_dist = ((cx) ** 2 + (cy) ** 2) ** 0.5
    overlay = Image.new("RGB", (w, h), (0, 0, 0))
    for y in range(h):
        for x in range(w):
            dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            alpha = min(255, int(80 * (dist / max_dist)))
            overlay.putpixel((x, y), (alpha, alpha, alpha))
    return Image.blend(img, Image.new("RGB", (w, h), (0, 0, 0)), 0.15)


def transform_product_image(
    image_bytes: bytes,
    style: str,
    description: str = "",
) -> Optional[bytes]:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((1200, 1200), Image.LANCZOS)

        if style == "professional":
            img = _auto_enhance(img)
            img = _apply_cool_tone(img)
            img = ImageOps.expand(img, border=15, fill=(255, 255, 255))
        elif style == "luxury":
            img = _auto_enhance(img)
            img = _apply_golden_tone(img)
            img = _apply_vignette(img)
            img = ImageOps.expand(img, border=10, fill=(180, 155, 100))
            img = ImageOps.expand(img, border=3, fill=(220, 200, 140))
        elif style == "lifestyle":
            img = _auto_enhance(img)
            img = _apply_warm_tone(img)
            img = img.filter(ImageFilter.SMOOTH_MORE)
        elif style == "social_media":
            img = _auto_enhance(img)
            img = ImageEnhance.Color(img).enhance(1.3)
            img = ImageEnhance.Contrast(img).enhance(1.2)
            img = ImageOps.expand(img, border=8, fill=(255, 100, 120))
            img = ImageOps.expand(img, border=3, fill=(100, 100, 255))
        else:
            img = _auto_enhance(img)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception as e:
        import traceback
        logger.error(f"Transform error: {e}")
        logger.error(traceback.format_exc())
        return None


def generate_ai_image(prompt: str) -> Optional[bytes]:
    from gemini_image import generate_image as gemini_gen
    result = gemini_gen(prompt)
    if result:
        return result
    try:
        resp = requests.get(
            f"{POLLINATIONS_URL}/{quote(prompt)}",
            params={"nofeed": "true", "width": 1024, "height": 1024},
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        logger.warning(f"Pollinations failed: {e}")
    return None


def text_to_image(prompt: str) -> Optional[bytes]:
    return generate_ai_image(prompt)
