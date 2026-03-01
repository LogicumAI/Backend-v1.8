import uuid
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response

from app.services.tts import generate_speech
from app.core.deps import get_current_user_id

router = APIRouter(prefix="/api/tts", tags=["tts"])

@router.post("")
async def tts_endpoint(
    text: str = Body(..., embed=True),
    voice: str = Body("alloy", embed=True),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """
    Text-to-Speech endpoint that returns an MP3 audio file.
    """
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    try:
        audio_content = await generate_speech(text, voice)
        return Response(content=audio_content, media_type="audio/mpeg")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")
