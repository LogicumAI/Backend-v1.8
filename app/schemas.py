from typing import Optional

from pydantic import BaseModel, Field


class ChatSendRequest(BaseModel):
    chat_id: Optional[int] = None   # None = start new chat
    message: str
    study_mode: bool = False


class ChatSendResponse(BaseModel):
    chat_id: int
    summary: str            # Summary Engine output (Part 1)
    answer: str             # Model response (Part 2)
    model_used: str         # "FLASH" or "GPT52"
    latency_ms: int
    backend_version: str    # Backend version tracking


class AuthRequest(BaseModel):
    email: str
    password: str = Field(..., max_length=72)
