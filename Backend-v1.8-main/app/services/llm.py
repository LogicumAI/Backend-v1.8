"""
Thin wrapper around LLM API calls.
Supports both Google Gemini (for FLASH / Nano) and OpenAI (for GPT-5.2).
"""

import os
import httpx
from typing import List
from app.core.config import OPENAI_API_KEY

# ── OpenAI (GPT-5.x) ──────────────────────────
OPENAI_API_KEY = (os.environ.get("OPENAI_API_KEY") or "").strip()
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")

# ── Global Model Mapping ──────────────────────
OPENAI_GPT4O_MODEL = os.environ.get("OPENAI_GPT4O_MODEL", "GPT 5.2")
OPENAI_GPT4O_MINI_MODEL = os.environ.get("OPENAI_GPT4O_MINI_MODEL", "GPT 5 Nano")
OPENAI_BASE_URL = "https://api.openai.com/v1/chat/completions"

# Fictional specification models from PDF 1.0
FLASH = "FLASH"
GPT52 = "GPT52"
GEMINI_3_FLASH = "GEMINI-3-FLASH"
GPT51 = "GPT-5.1"
    
def normalize_openai_model(model: str) -> str:
    """Ensure fictional specification models map to real OpenAI IDs."""
    mapping = {
        "GPT-5.2": "gpt-4o",
        "GPT 5.2": "gpt-4o",
        "GPT52": "gpt-4o",
        "GPT-5.1": "gpt-4o-mini",
        "GPT 5 Nano": "gpt-4o-mini",
        "GPT51": "gpt-4o-mini",
        "FLASH": "gpt-4o-mini",
        "GEMINI-3-FLASH": "gpt-4o-mini",
        "gemini-1.5-flash": "gpt-4o",
        "gemini-1.5-flash-latest": "gpt-4o",
        "gemini-3-flash": "gpt-4o-mini",
        "gpt-5-nano": "gpt-4o-mini",
        "CODEX": "gpt-4o",
        "GPT 5.3 Codex": "gpt-4o"
    }
    return mapping.get(model, model)


async def call_gemini(
    system_prompt: str,
    user_content: str,
    model: str | None = None,
    max_tokens: int = 4096,
    image_b64: str | None = None,
) -> str:
    """[MIGRATED] Wraps call_openai to replace Gemini functionality."""
    # Map Gemini-style model calls to GPT
    if not model or "gemini" in model.lower() or "nano" in model.lower():
        model = "GPT 5 Nano"
        
    return await call_openai(
        system_prompt=system_prompt,
        user_content=user_content,
        model=model,
        max_tokens=max_tokens,
        image_b64=image_b64
    )


async def call_openai(
    system_prompt: str,
    user_content: str,
    model: str | None = None,
    max_tokens: int = 4096,
    image_b64: str | None = None,
) -> str:
    """Call OpenAI API and return the text response. Supports multimodal vision ingestion."""
    model = normalize_openai_model(model or OPENAI_GPT4O_MODEL)
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    
    content_list = []
    if user_content:
        content_list.append({"type": "text", "text": user_content})
    
    if image_b64:
        # GPT-4o style multimodal input
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_b64}"
            }
        })

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
            {"role": "user", "content": content_list},
        ],
        "max_tokens": max_tokens,
    }

    # Debug Logging
    # print(f"DEBUG OPENAI PAYLOAD: {payload}")

    async with httpx.AsyncClient(timeout=90) as client:
        try:
            resp = await client.post(OPENAI_BASE_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                print(f"ERROR: OpenAI internal error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            # Headers might contain keys, print only status and message
            print(f"OpenAI API Error {e.response.status_code}: {e.response.text}")
            return ""
        except Exception as e:
            print(f"Error in call_openai (structural failure): {type(e).__name__}")
            return ""

    return data["choices"][0]["message"]["content"]


async def call_embeddings(text: str) -> List[float]:
    """Call OpenAI Embedding API (text-embedding-3-small) and return the vector."""
    if not text or not text.strip():
        return []

    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "text-embedding-3-small",
        "input": text.strip()
    }
    
    # Matching timeout and robustness of call_openai
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                print(f"ERROR: OpenAI Embedding Error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [{}])[0].get("embedding", [])
        except httpx.HTTPStatusError as e:
            print(f"OpenAI Embedding API Error {e.response.status_code}: {e.response.text}")
            return []
        except Exception as e:
            print(f"Critical failure in call_embeddings: {type(e).__name__}: {e}")
            return []
