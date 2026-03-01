import uuid
import base64
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.deps import get_current_user_id
from app.models import OCRDocumentV3, OCRChunkV3
from app.services import pipeline_v3

router = APIRouter(prefix="/ocr/v3", tags=["ocr_v3"])

class OCRDocumentV3Response(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    created_at: Any

class OCRDocumentListV3Response(BaseModel):
    files: List[OCRDocumentV3Response]

class OCRChunkV3Response(BaseModel):
    id: int
    chunk_type: str
    content: str
    origin_position: Optional[str]

@router.post("/upload")
async def upload_document_v3(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Upload a document/image and start the 8-stage V3 pipeline."""
    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")
    
    # Trigger pipeline in background
    background_tasks.add_task(
        pipeline_v3.run_v3_pipeline,
        user_id=user_id,
        filename=file.filename,
        image_b64=image_b64
    )
    
    return {"message": "Upload successful. Pipeline V3 started in background.", "filename": file.filename}

@router.get("/documents", response_model=OCRDocumentListV3Response)
async def list_documents_v3(
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """List all V3 documents for the current user."""
    statement = select(OCRDocumentV3).where(OCRDocumentV3.user_id == user_id)
    results = session.exec(statement).all()
    return {"files": [{"id": d.id, "filename": d.filename, "status": d.status, "created_at": d.created_at} for d in results]}

@router.get("/documents/{doc_id}/chunks", response_model=List[Dict])
async def get_document_chunks_v3(
    doc_id: uuid.UUID,
    session: Session = Depends(get_session),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Retrieve all semantic chunks for a specific V3 document."""
    doc = session.get(OCRDocumentV3, doc_id)
    if not doc or doc.user_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    
    statement = select(OCRChunkV3).where(OCRChunkV3.document_id == doc_id)
    chunks = session.exec(statement).all()
    return [{
        "id": c.id, 
        "chunk_type": c.chunk_type, 
        "content": c.content, 
        "origin_position": c.origin_position
    } for c in chunks]

