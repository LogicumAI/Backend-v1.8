import json
import uuid
import asyncio
from typing import List, Dict, Any
from sqlmodel import Session
from app.core.database import engine
from app.models import OCRDocumentV3, OCRChunkV3
from app.services import v3_engines

async def run_v3_pipeline(user_id: uuid.UUID, filename: str, image_b64: str):
    """Orchestrate the 8-stage OCR V3 Pipeline."""
    
    # Create document entry in DB
    with Session(engine) as session:
        doc = OCRDocumentV3(
            user_id=user_id,
            filename=filename,
            s3_key=f"uploads/{user_id}/{filename}",
            status="processing"
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)
        doc_id = doc.id

    try:
        # Stage 1: Information Gate
        gate_resp = await v3_engines.information_gate(image_b64)
        if not gate_resp.get("contains_information"):
            _update_doc_status(doc_id, "failed")
            return {"error": "Non-informational image rejected", "reason": gate_resp.get("reason")}

        # Stage 2: Visual Structure & Context
        structure_resp = await v3_engines.visual_structure_engine(image_b64)
        
        # Stages 3, 4, 5 (Specialized Visual Engines) - Run in parallel
        visual_tasks = []
        for element in structure_resp.get("visual_elements", []):
            if element.get("relevant"):
                if element["type"] == "diagram":
                    visual_tasks.append(_process_visual(doc_id, image_b64, "diagram", v3_engines.diagram_engine))
                elif element["type"] == "table":
                    visual_tasks.append(_process_visual(doc_id, image_b64, "table", v3_engines.table_engine))
                elif element["type"] == "illustration":
                    visual_tasks.append(_process_visual(doc_id, image_b64, "illustration", v3_engines.illustration_engine))

        # Stage 6: OCR Engine
        ocr_task = v3_engines.ocr_engine(image_b64)
        
        # Wait for visual processing and OCR
        results = await asyncio.gather(*visual_tasks, ocr_task)
        visual_chunks = [r for r in results[:len(visual_tasks)]]
        ocr_paragraphs = results[-1]

        # Stage 7: Paragraph Logical Cohesion Engine
        final_text_chunks = await _run_cohesion_layer(ocr_paragraphs)

        # Stage 8: Embedding Engine
        all_chunks_to_embed = visual_chunks + final_text_chunks
        
        embedding_tasks = []
        for chunk_data in all_chunks_to_embed:
            embedding_tasks.append(_embed_and_save_chunk(doc_id, chunk_data))

        await asyncio.gather(*embedding_tasks)

        _update_doc_status(doc_id, "completed")
        return {"status": "success", "document_id": str(doc_id)}

    except Exception as e:
        print(f"Pipeline V3 Error: {e}")
        _update_doc_status(doc_id, "failed")
        raise e

async def _process_visual(doc_id: uuid.UUID, image_b64: str, chunk_type: str, engine_func):
    """Helper to process a visual element and return chunk metadata."""
    content = await engine_func(image_b64)
    return {
        "content": content,
        "chunk_type": chunk_type,
        "origin_position": "image_analysis" # Placeholder
    }

async def _run_cohesion_layer(paragraphs: List[str]) -> List[Dict[str, Any]]:
    """Helper to merge paragraphs based on cohesion logic (Stage 7)."""
    if not paragraphs:
        return []

    final_chunks = []
    current_content = paragraphs[0]

    for i in range(1, len(paragraphs)):
        prev_p = paragraphs[i-1]
        curr_p = paragraphs[i]
        
        cohesion = await v3_engines.cohesion_engine(prev_p, curr_p)
        
        if cohesion.get("merge"):
            current_content += "\n\n" + curr_p
        else:
            final_chunks.append({"content": current_content, "chunk_type": "text"})
            current_content = curr_p

    final_chunks.append({"content": current_content, "chunk_type": "text"})
    return final_chunks

async def _embed_and_save_chunk(doc_id: uuid.UUID, chunk_data: Dict[str, Any]):
    """Helper to generate embedding and save chunk to DB (Stage 8)."""
    vector = await v3_engines.embedding_engine(chunk_data["content"])
    
    with Session(engine) as session:
        chunk = OCRChunkV3(
            document_id=doc_id,
            content=chunk_data["content"],
            chunk_type=chunk_data["chunk_type"],
            origin_position=chunk_data.get("origin_position"),
            embedding=json.dumps(vector)
        )
        session.add(chunk)
        session.commit()

def _update_doc_status(doc_id: uuid.UUID, status: str):
    """Update OCRDocumentV3 status in DB."""
    with Session(engine) as session:
        doc = session.get(OCRDocumentV3, doc_id)
        if doc:
            doc.status = status
            session.add(doc)
            session.commit()
