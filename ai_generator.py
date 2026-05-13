from typing import Optional
from openai import OpenAI

from config import config


_PROVIDERS = []


def _build_providers():
    global _PROVIDERS
    if _PROVIDERS:
        return
    providers = []
    if config.GROQ_API_KEY:
        providers.append({
            "name": "Groq",
            "client": OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_API_URL),
            "model": config.GROQ_MODEL,
        })
    if config.GEMINI_API_KEY:
        providers.append({
            "name": "Gemini",
            "client": OpenAI(api_key=config.GEMINI_API_KEY, base_url=config.GEMINI_API_URL),
            "model": config.GEMINI_MODEL,
        })
    if config.GITHUB_API_KEY:
        providers.append({
            "name": "GitHub",
            "client": OpenAI(api_key=config.GITHUB_API_KEY, base_url=config.GITHUB_API_URL),
            "model": config.GITHUB_MODEL,
        })
    _PROVIDERS = providers


def _call(prompt: str, temperature: float = 0.7, max_tokens: int = 800) -> str:
    _build_providers()
    if not _PROVIDERS:
        raise Exception("No AI provider configured. Set at least GROQ_API_KEY, GEMINI_API_KEY, or GITHUB_API_KEY")

    last_error = None
    for p in _PROVIDERS:
        try:
            resp = p["client"].chat.completions.create(
                model=p["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"All AI providers failed. Last error: {last_error}")


def generate_post(topic: str, tone: str = "professional", language: str = "ar") -> str:
    lang_name = "Arabic" if language == "ar" else "English"
    prompt = (
        f"Write a social media post in {lang_name} about '{topic}'.\n"
        f"Tone: {tone}.\n"
        f"Make it engaging, suitable for Facebook and Instagram.\n"
        f"Include relevant hashtags.\n"
        f"Keep it between 100-300 words."
    )
    return _call(prompt, temperature=0.8, max_tokens=800)


def generate_comment_reply(comment: str, language: str = "ar") -> str:
    lang_name = "Arabic" if language == "ar" else "English"
    prompt = (
        f"Reply to this social media comment in {lang_name} in a friendly and helpful way:\n"
        f"Comment: {comment}\n"
        f"Keep it short (1-2 sentences)."
    )
    return _call(prompt, temperature=0.7, max_tokens=200)
