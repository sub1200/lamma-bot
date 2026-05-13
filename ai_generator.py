from typing import Optional
from openai import OpenAI

from config import config


_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_API_URL,
        )
    return _client


def generate_post(topic: str, tone: str = "professional", language: str = "ar") -> str:
    client = get_client()
    lang_name = "Arabic" if language == "ar" else "English"

    prompt = (
        f"Write a social media post in {lang_name} about '{topic}'.\n"
        f"Tone: {tone}.\n"
        f"Make it engaging, suitable for Facebook and Instagram.\n"
        f"Include relevant hashtags.\n"
        f"Keep it between 100-300 words."
    )

    resp = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=800,
    )
    return resp.choices[0].message.content.strip()


def generate_comment_reply(comment: str, language: str = "ar") -> str:
    client = get_client()
    lang_name = "Arabic" if language == "ar" else "English"

    prompt = (
        f"Reply to this social media comment in {lang_name} in a friendly and helpful way:\n"
        f"Comment: {comment}\n"
        f"Keep it short (1-2 sentences)."
    )

    resp = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200,
    )
    return resp.choices[0].message.content.strip()
