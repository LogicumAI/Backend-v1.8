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
    model_used: str         # "FLASH" or "GPT52" (Legacy field)
    initial_model: str      # Model used for pre-processing
    execution_model: str    # Model used for main response
    latency_ms: int         # Total latency
    latency_initial_ms: int # Latency of Phase 1
    latency_execution_ms: int # Latency of Phase 2
    backend_version: str    # Backend version tracking
    is_study_mode_abort: bool = False # Flag if study mode aborted


class AuthRequest(BaseModel):
    email: str
    password: str = Field(..., max_length=72)
