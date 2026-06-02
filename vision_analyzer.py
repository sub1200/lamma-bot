import base64
import logging
import os
import subprocess
import tempfile
from typing import Optional

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)


def _img_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def _vision_call(image_bytes: bytes, prompt: str) -> str:
    b64 = _img_to_base64(image_bytes)
    data_url = f"data:image/jpeg;base64,{b64}"

    providers = []

    if config.GROQ_API_KEY:
        providers.append({
            "name": "Groq",
            "client": OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_API_URL),
            "model": "llama-3.2-90b-vision-preview",
        })
    if config.GEMINI_API_KEY:
        providers.append({
            "name": "Gemini",
            "client": OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_API_URL),
            "model": "gemini-2.0-flash",
        })
    if config.GITHUB_API_KEY:
        providers.append({
            "name": "GitHub",
            "client": OpenAI(api_key=config.GITHUB_API_KEY, base_url=config.GITHUB_API_URL),
            "model": "gpt-4o-mini",
        })

    if not providers:
        return "❌ No AI provider configured. Set GROQ_API_KEY, GEMINI_API_KEY, or GITHUB_API_KEY."

    last_error = None
    for p in providers:
        try:
            resp = p["client"].chat.completions.create(
                model=p["model"],
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
                max_tokens=1000,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            continue

    return f"❌ All vision providers failed: {last_error}"


async def analyze_image(image_bytes: bytes, prompt: str = None) -> str:
    # If no prompt is provided, we use the "Ultra Luxury Sales Agent" prompt
    if not prompt:
        prompt = (
            "You are a world-class Creative Director and Luxury Marketing Expert. "
            "Analyze the product in this image and generate a high-end marketing package in Arabic.\n\n"
            "Your response MUST follow this structure:\n\n"
            "1. 💎 **التحليل النفسي للمنتج**: (Identify the core value and how it makes the customer feel special. Focus on prestige and elegance).\n"
            "2. ✍️ **نماذج إعلانية فاخرة**:\n"
            "   - **النمط الملكي (Royal):** High-class, authoritative, and exclusive language.\n"
            "   - **النمط العصري (Modern Luxury):** Clean, minimal, and sophisticated.\n"
            "   - **النمط الإقناعي (Persuasive):** Focus on the 'must-have' feeling and urgent desire.\n"
            "3. 📸 **نصائح التصوير الاحترافي**: (Suggest the best background, lighting, and angle to make the product look like a million dollars).\n\n"
            "Make the language extremely seductive and professional (Arabic). Use emojis sparingly but effectively."
        )
    
    return _vision_call(image_bytes, prompt)


PRODUCT_CATEGORIES = {
    "clothing": {"label": "ملابس", "styles": ["standard", "with_person", "environment", "luxury"], "has_sizes": True},
    "shoes": {"label": "أحذية", "styles": ["standard", "with_person", "environment", "luxury"], "has_sizes": True},
    "accessories": {"label": "إكسسوارات", "styles": ["standard", "with_person", "environment", "luxury"], "has_sizes": False},
    "jewelry": {"label": "مجوهرات", "styles": ["standard", "luxury"], "has_sizes": False},
    "watches": {"label": "ساعات", "styles": ["standard", "with_person", "environment", "luxury"], "has_sizes": False},
    "food_beverage": {"label": "طعام وشراب", "styles": ["standard", "environment"], "has_sizes": True},
    "drink": {"label": "مشروبات", "styles": ["standard", "environment"], "has_sizes": True},
    "electronics": {"label": "إلكترونيات", "styles": ["standard", "environment", "luxury"], "has_sizes": False},
    "furniture": {"label": "أثاث", "styles": ["standard", "environment", "luxury"], "has_sizes": True},
    "home_decor": {"label": "ديكور منزلي", "styles": ["standard", "environment", "luxury"], "has_sizes": False},
    "cosmetics": {"label": "مستحضرات تجميل", "styles": ["standard", "luxury"], "has_sizes": True},
    "perfume": {"label": "عطور", "styles": ["standard", "luxury"], "has_sizes": True},
    "skincare": {"label": "عناية بالبشرة", "styles": ["standard", "luxury"], "has_sizes": True},
    "book": {"label": "كتاب", "styles": ["standard"], "has_sizes": False},
    "toy": {"label": "لعبة", "styles": ["standard", "environment"], "has_sizes": False},
    "sports": {"label": "معدات رياضية", "styles": ["standard", "environment", "luxury"], "has_sizes": True},
    "bag": {"label": "حقائب", "styles": ["standard", "with_person", "environment", "luxury"], "has_sizes": True},
    "other": {"label": "منتج", "styles": ["standard", "environment"], "has_sizes": False},
}


async def classify_product(image_bytes: bytes) -> dict:
    prompt = (
        "Analyze this product image. Determine its exact category.\n"
        f"Categories: {', '.join(PRODUCT_CATEGORIES.keys())}\n\n"
        "Reply in EXACTLY this format (use English words):\n"
        "NAME: <product name in English, max 5 words>\n"
        "CATEGORY: <one category from the list>\n"
        "ARABIC: <product name in Arabic, max 5 words>\n"
        "PRICE_GUESS: <estimated price range like 10-50 USD or 5-15 USD>\n"
        "SIZES: <available sizes like S,M,L or 250ml,500ml,1L or N/A>\n"
        "WEARABLE: <yes if humans wear/carry it on body, no otherwise>"
    )
    result = _vision_call(image_bytes, prompt)
    data = {"name": "", "category": "other", "arabic": "", "price_guess": "", "sizes": "N/A", "wearable": "no"}
    for line in result.split("\n"):
        line = line.strip()
        for key in ("NAME:", "CATEGORY:", "ARABIC:", "PRICE_GUESS:", "SIZES:", "WEARABLE:"):
            if line.startswith(key):
                data[key.lower().replace(":", "")] = line[len(key):].strip()
    if data["category"] not in PRODUCT_CATEGORIES:
        data["category"] = "other"
    return data


async def suggest_product_style(image_bytes: bytes) -> str:
    prompt = (
        "You are a product photography expert. "
        "Look at this product image and suggest the best presentation style for it.\n\n"
        "Available styles:\n"
        "- professional: white background, studio lighting\n"
        "- lifestyle: natural setting, realistic use\n"
        "- 3d_mockup: isometric 3D render\n"
        "- minimalist: clean and elegant\n"
        "- social_media: vibrant, eye-catching\n"
        "- luxury: premium, gold accents\n\n"
        "Reply with ONLY the style name (one word) that best fits this product, "
        "and a short explanation why."
    )
    return _vision_call(image_bytes, prompt)


def extract_frames_from_video(video_bytes: bytes, num_frames: int = 3) -> list[bytes]:
    frames = []
    tmp = tempfile.mkdtemp()
    input_path = os.path.join(tmp, "video.mp4")
    output_pattern = os.path.join(tmp, "frame_%03d.jpg")

    try:
        with open(input_path, "wb") as f:
            f.write(video_bytes)

        result = subprocess.run(
            ["ffmpeg", "-i", input_path, "-vf", f"fps=1/{num_frames}", "-frames:v", str(num_frames), output_pattern],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"FFmpeg frame extraction failed: {result.stderr}")
            return []

        for i in range(1, num_frames + 1):
            path = os.path.join(tmp, f"frame_{i:03d}.jpg")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    frames.append(f.read())

    except Exception as e:
        logger.error(f"Frame extraction error: {e}")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    return frames


async def analyze_video(video_bytes: bytes) -> str:
    frames = extract_frames_from_video(video_bytes)
    if not frames:
        return "❌ Cannot analyze video. Make make sure FFmpeg is installed."

    b64_frames = [_img_to_base64(f) for f in frames[:3]]
    content = [{"type": "text", "text": "Analyze these frames from a video in Arabic. Describe what's happening and the main subject."}]
    for b64 in b64_frames:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    providers = []
    if config.GROQ_API_KEY:
        providers.append({
            "name": "Groq",
            "client": OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_API_URL),
            "model": "llama-3.2-90b-vision-preview",
        })
    if config.GEMINI_API_KEY:
        providers.append({
            "name": "Gemini",
            "client": OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_API_URL),
            "model": "gemini-2.0-flash",
        })
    if config.GITHUB_API_KEY:
        providers.append({
            "name": "GitHub",
            "client": OpenAI(api_key=config.GITHUB_API_KEY, base_url=config.GITHUB_API_URL),
            "model": "gpt-4o-mini",
        })

    last_error = None
    for p in providers:
        try:
            resp = p["client"].chat.completions.create(
                model=p["model"],
                messages=[{"role": "user", "content": content}],
                max_tokens=500,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            continue

    return f"❌ All providers failed: {last_error}"
