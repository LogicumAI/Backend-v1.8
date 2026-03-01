import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core import database
from app.core.database import get_session
from app.models import Chat, Message
from app.schemas import ChatSendRequest, ChatSendResponse
from app.services.pipeline import execute_pipeline

# Import shared dependency (avoids circular import with main.py)
from app.core.deps import get_current_user_id

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("/", response_model=List[Chat])
async def list_chats(
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List all chats for the current user."""
    chats = session.exec(select(Chat).where(Chat.user_id == user_id)).all()
    return chats


@router.post("/send", response_model=ChatSendResponse)
async def send_message(
    body: ChatSendRequest,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Process a user message through the full AI pipeline.

    If chat_id is None, a new chat is created.
    Returns: summary (Part 1), answer (Part 2), model_used, latency_ms.
    """
    # ── Resolve or create chat ───────────────
    if body.chat_id is None:
        chat = Chat(user_id=user_id)
        session.add(chat)
        session.commit()
        session.refresh(chat)
        chat_id = chat.id
    else:
        chat_id = body.chat_id
        # Verify ownership
        chat = session.get(Chat, chat_id)
        if not chat or chat.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this chat")

    # ── Store user message ───────────────────
    user_msg = Message(chat_id=chat_id, role="user", content=body.message)
    session.add(user_msg)
    session.commit()

    # ── Execute pipeline ─────────────────────
    result = await execute_pipeline(
        user_message=body.message,
        chat_id=chat_id,
        session=session,
        user_id=user_id,
        study_mode=body.study_mode,
    )

    # ── Store assistant message ──────────────
    assistant_msg = Message(
        chat_id=chat_id,
        role="assistant",
        content=result["answer"],
        model_used=result["model_used"],
        latency_ms=result["latency_ms"],
    )
    session.add(assistant_msg)
    session.commit()

    return ChatSendResponse(
        chat_id=chat_id,
        summary=result["summary"],
        answer=result["answer"],
        model_used=result["model_used"],
        latency_ms=result["latency_ms"],
        backend_version=result["backend_version"],
    )
