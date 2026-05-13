import base64
import io
import logging
import os
import subprocess
import tempfile
from typing import Optional

from openai import OpenAI

from config import config

logger = logging.getLogger(__name__)


def _client() -> Optional[OpenAI]:
    if not config.DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY not set")
        return None
    return OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_API_URL,
    )


def _img_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


async def analyze_image(image_bytes: bytes, prompt: str = "Describe this image in detail in Arabic") -> str:
    client = _client()
    if not client:
        return "❌ DEEPSEEK_API_KEY غير مضبوط."

    b64 = _img_to_base64(image_bytes)
    data_url = f"data:image/jpeg;base64,{b64}"

    try:
        resp = client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Vision analysis error: {e}")
        return f"❌ فشل التحليل: {e}"


async def suggest_product_style(image_bytes: bytes) -> str:
    prompt = (
        "You are a product photography expert. "
        "Look at this product image and suggest the best presentation style for it. "
        "The product is: (analyze what product this is)\n\n"
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
    return await analyze_image(image_bytes, prompt)


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
        return "❌ لا يمكن تحليل الفيديو. تأكد من تثبيت FFmpeg."

    client = _client()
    if not client:
        return "❌ DEEPSEEK_API_KEY غير مضبوط."

    contents = [{"type": "text", "text": "Analyze these frames from a video in Arabic. Describe what's happening and the main subject."}]

    for frame in frames[:3]:
        b64 = _img_to_base64(frame)
        contents.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    try:
        resp = client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": contents}],
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Video analysis error: {e}")
        return f"❌ فشل تحليل الفيديو: {e}"
