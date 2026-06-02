import io
import logging
from typing import Optional
from urllib.parse import quote
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import requests

logger = logging.getLogger(__name__)

POLLINATIONS_URL = "https://image.pollinations.ai/prompt"

STYLES = {
    "professional": {
        "label": "احترافي - خلفية بيضاء",
        "bg_color": (255, 255, 255),
        "border": True,
        "border_color": (200, 200, 200),
    },
    "lifestyle": {
        "label": "لايف ستايل - استخدام واقعي",
        "bg_color": (255, 245, 230),
        "warm": True,
    },
    "3d_mockup": {
        "label": "موديل ثلاثي الأبعاد",
        "bg_color": (40, 40, 55),
        "shadow": True,
    },
    "minimalist": {
        "label": "بساطة - تصميم أنيق",
        "bg_color": (245, 243, 238),
        "thin_border": True,
    },
    "social_media": {
        "label": "سوشيال ميديا - جذاب",
        "gradient": True,
        "color1": (255, 100, 120),
        "color2": (100, 100, 255),
    },
    "luxury": {
        "label": "فاخر - راقي",
        "bg_color": (20, 18, 15),
        "gold_border": True,
    },
}


def transform_product_image(
    image_bytes: bytes,
    style: str,
    description: str = "",
) -> Optional[bytes]:
    style_config = STYLES.get(style)
    if not style_config:
        logger.error(f"Unknown style: {style}")
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((600, 600), Image.LANCZOS)

        W, H = 800, 800

        if style_config.get("gradient"):
            bg = Image.new("RGB", (W, H))
            draw = ImageDraw.Draw(bg)
            c1, c2 = style_config["color1"], style_config["color2"]
            for i in range(H):
                r = int(c1[0] * (1 - i/H) + c2[0] * (i/H))
                g = int(c1[1] * (1 - i/H) + c2[1] * (i/H))
                b = int(c1[2] * (1 - i/H) + c2[2] * (i/H))
                draw.line([(0, i), (W, i)], fill=(r, g, b))
        else:
            bg = Image.new("RGB", (W, H), style_config["bg_color"])

        pw = int(W * 0.65)
        ph = int(H * 0.65)
        img.thumbnail((pw, ph), Image.LANCZOS)

        px = (W - img.width) // 2
        py = int(H * 0.3)

        if style_config.get("shadow"):
            bg_rgba = bg.convert("RGBA")
            shadow = Image.new("RGBA", (img.width, img.height), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow)
            sd.ellipse(
                [img.width//5, img.height-img.height//8, img.width*4//5, img.height],
                fill=(0, 0, 0, 50),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(radius=6))
            bg_rgba.paste(shadow, (px, py), shadow)
            bg = bg_rgba

        bg_rgba = bg.convert("RGBA")
        img_rgba = img.convert("RGBA")
        bg_rgba.paste(img_rgba, (px, py), img_rgba)

        if style_config.get("border"):
            bg = ImageOps.expand(bg, border=12, fill=style_config["border_color"])
        elif style_config.get("thin_border"):
            bg = ImageOps.expand(bg, border=6, fill=(220, 218, 210))
        elif style_config.get("gold_border"):
            bg = ImageOps.expand(bg, border=8, fill=(180, 155, 100))
            bg = ImageOps.expand(bg, border=2, fill=(220, 200, 140))

        if style_config.get("warm"):
            bg = ImageEnhance.Color(bg).enhance(1.2)
            bg = ImageEnhance.Brightness(bg).enhance(1.05)

        buf = io.BytesIO()
        bg.save(buf, format="PNG", optimize=True)
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
