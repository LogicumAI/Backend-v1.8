import os
import httpx
from app.core.config import OPENAI_API_KEY

OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"

async def generate_speech(text: str, voice: str = "alloy") -> bytes:
    """
    Call OpenAI's TTS API to generate speech from text.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key is not configured")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": OPENAI_TTS_MODEL,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(OPENAI_TTS_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            # Fallback to tts-1 if gpt-4o-mini-tts is not available or errors out
            payload["model"] = "tts-1"
            resp = await client.post(OPENAI_TTS_URL, json=payload, headers=headers)
            resp.raise_for_status()
            
        return resp.content
