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
        "action": "professional",
        "prompt": "clean studio background, soft gradient, elegant",
    },
    "lifestyle": {
        "label": "لايف ستايل - استخدام واقعي",
        "action": "lifestyle",
        "prompt": "natural lifestyle setting, warm cozy room with sunlight, modern interior",
    },
    "3d_mockup": {
        "label": "موديل ثلاثي الأبعاد",
        "action": "3d_mockup",
        "prompt": "3D render studio background, isometric platform, modern, clean",
    },
    "minimalist": {
        "label": "بساطة - تصميم أنيق",
        "action": "minimalist",
        "prompt": "minimalist studio, beige background, soft natural light",
    },
    "social_media": {
        "label": "سوشيال ميديا - جذاب",
        "action": "social_media",
        "prompt": "vibrant social media background, colorful gradient, trendy",
    },
    "luxury": {
        "label": "فاخر - راقي",
        "action": "luxury",
        "prompt": "luxury showroom, dark elegant background, gold accents, dramatic lighting",
    },
}


def remove_background(image: Image.Image) -> Image.Image:
    img = image.convert("RGBA")
    w, h = img.size

    samples = []
    for x in range(0, w, max(1, w // 20)):
        samples.append(img.getpixel((x, 0))[:3])
        samples.append(img.getpixel((x, h - 1))[:3])
    for y in range(0, h, max(1, h // 20)):
        samples.append(img.getpixel((0, y))[:3])
        samples.append(img.getpixel((w - 1, y))[:3])

    bg_r = sum(c[0] for c in samples) // len(samples)
    bg_g = sum(c[1] for c in samples) // len(samples)
    bg_b = sum(c[2] for c in samples) // len(samples)
    bg_color = (bg_r, bg_g, bg_b)

    threshold = 70
    datas = list(img.getdata())
    new_data = []
    for item in datas:
        if all(abs(item[c] - bg_color[c]) < threshold for c in range(3)):
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    return img


def composite_on_background(product: Image.Image, bg: Image.Image) -> Image.Image:
    product_rgba = product.convert("RGBA")
    bg_rgb = bg.convert("RGBA")

    max_w = int(bg_rgb.width * 0.7)
    max_h = int(bg_rgb.height * 0.6)
    product_rgba.thumbnail((max_w, max_h), Image.LANCZOS)

    x = (bg_rgb.width - product_rgba.width) // 2
    y = int(bg_rgb.height * 0.35)

    shadow = Image.new("RGBA", product_rgba.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        [
            int(product_rgba.width * 0.1),
            product_rgba.height - int(product_rgba.height * 0.1),
            int(product_rgba.width * 0.9),
            product_rgba.height,
        ],
        fill=(0, 0, 0, 40),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
    bg_rgb.paste(shadow, (x, y), shadow)

    bg_rgb.paste(product_rgba, (x, y), product_rgba)
    return bg_rgb


def generate_scene_background(description: str, style_prompt: str) -> Optional[Image.Image]:
    return None


def create_professional_background(width: int, height: int) -> Image.Image:
    bg = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(bg)
    for i in range(height):
        color = int(255 - (i / height) * 30)
        draw.line([(0, i), (width, i)], fill=(color, color, color))
    return bg


def create_gradient_background(width: int, height: int, top_color, bottom_color) -> Image.Image:
    bg = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(bg)
    for i in range(height):
        ratio = i / height
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
    return bg


def create_pedestal_background(width: int, height: int, dark: bool = False) -> Image.Image:
    if dark:
        bg = Image.new("RGB", (width, height), (30, 30, 40))
    else:
        bg = Image.new("RGB", (width, height), (240, 240, 245))
    draw = ImageDraw.Draw(bg)
    pw, ph = width // 3, height // 6
    px = (width - pw) // 2
    py = height - ph - height // 6
    if dark:
        pedestal_color = (50, 50, 65)
        top_color = (70, 70, 90)
    else:
        pedestal_color = (220, 220, 225)
        top_color = (245, 245, 250)
    draw.rounded_rectangle([px, py, px + pw, py + ph], radius=10, fill=pedestal_color)
    draw.rounded_rectangle([px + 5, py - 5, px + pw - 5, py + 5], radius=5, fill=top_color)
    return bg


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


def text_to_image(prompt: str) -> Optional[bytes]:
    return generate_ai_image(prompt)


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
        logger.info(f"Opening image, size: {len(image_bytes)} bytes")
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        logger.info(f"Image size: {img.size}")
        img.thumbnail((800, 800), Image.LANCZOS)

        logger.info("Removing background...")
        product_rgba = remove_background(img)
        logger.info(f"Product RGBA mode: {product_rgba.mode}")
        W, H = 1024, 1024

        bg = None
        logger.info(f"Creating background for style: {style_config['action']}")
        if style_config["action"] == "professional":
            bg = create_professional_background(W, H)
        elif style_config["action"] == "lifestyle":
            bg = create_gradient_background(W, H, (255, 248, 240), (230, 210, 190))
        elif style_config["action"] == "3d_mockup":
            bg = create_pedestal_background(W, H, dark=True)
        elif style_config["action"] == "minimalist":
            bg = create_gradient_background(W, H, (248, 245, 240), (235, 230, 220))
        elif style_config["action"] == "social_media":
            bg = create_gradient_background(W, H, (255, 100, 100), (100, 100, 255))
        elif style_config["action"] == "luxury":
            bg = create_pedestal_background(W, H, dark=True)
        else:
            bg = create_professional_background(W, H)

        logger.info("Compositing...")
        result = composite_on_background(product_rgba, bg)

        buf = io.BytesIO()
        result.save(buf, format="PNG", optimize=True)
        logger.info(f"Image transformed: {style}, output: {len(buf.getvalue())} bytes")
        return buf.getvalue()
    except Exception as e:
        import traceback
        logger.error(f"Transform error: {e}")
        logger.error(traceback.format_exc())
        return None
