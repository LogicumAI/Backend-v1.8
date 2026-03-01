import json
import re
import math
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.models import OCRChunkV3, OCRDocumentV3
from app.core.database import engine
from app.services import llm

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(b * b for b in v2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
        
    return dot_product / (magnitude1 * magnitude2)

def split_query(text: str) -> List[str]:
    """Split text by . and ? to isolate individual questions/statements."""
    # Split by . or ? followed by whitespace or end of string
    parts = re.split(r'(?<=[.?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]

async def run_ocr_retrieval(user_id: uuid.UUID, user_message: str, threshold: float = 0.5) -> str:
    """
    Perform semantic retrieval from OCR V3 chunks.
    1. Split query into parts.
    2. Embed each part.
    3. Find best matching document (single area).
    4. Return concatenated context from that document.
    """
    query_parts = split_query(user_message)
    if not query_parts:
        return ""

    # 1. Embed all query parts in parallel
    embedding_tasks = [llm.call_embeddings(p) for p in query_parts]
    query_vectors = await asyncio.gather(*embedding_tasks)
    
    # Filter out empty embeddings
    query_vectors = [v for v in query_vectors if v]
    if not query_vectors:
        return ""

    # 2. Fetch all OCR chunks for this user (could be optimized with a vector DB in production)
    with Session(engine) as session:
        # First, find documents belonging to the user to filter chunks
        doc_stmt = select(OCRDocumentV3.id).where(OCRDocumentV3.user_id == user_id)
        user_doc_ids = session.exec(doc_stmt).all()
        
        if not user_doc_ids:
            return ""
            
        chunk_stmt = select(OCRChunkV3).where(OCRChunkV3.document_id.in_(user_doc_ids))
        all_chunks = session.exec(chunk_stmt).all()
    
    if not all_chunks:
        return ""

    # 3. Calculate similarities and group by document
    # doc_scores: {doc_id: max_similarity_score_found_in_this_doc}
    doc_best_scores: Dict[uuid.UUID, float] = {}
    # doc_chunks: {doc_id: [matching_chunks_with_scores]}
    doc_matches: Dict[uuid.UUID, List[Dict[str, Any]]] = {}

    for chunk in all_chunks:
        if not chunk.embedding:
            continue
            
        try:
            chunk_vector = json.loads(chunk.embedding)
        except:
            continue
            
        # Find best match for this chunk across all query parts
        best_part_sim = 0.0
        for q_vec in query_vectors:
            sim = cosine_similarity(q_vec, chunk_vector)
            if sim > best_part_sim:
                best_part_sim = sim
        
        if best_part_sim >= threshold:
            doc_id = chunk.document_id
            if doc_id not in doc_best_scores or best_part_sim > doc_best_scores[doc_id]:
                doc_best_scores[doc_id] = best_part_sim
            
            if doc_id not in doc_matches:
                doc_matches[doc_id] = []
            doc_matches[doc_id].append({"content": chunk.content, "score": best_part_sim})

    if not doc_best_scores:
        return ""

    # 4. Identify the "Best Area" (Document with the highest individual match)
    best_doc_id = max(doc_best_scores, key=doc_best_scores.get)
    
    # 5. Build context from THIS DOCUMENT ONLY
    # Sort matches by score (highest first) and take top 5 to avoid context overflow
    selected_matches = sorted(doc_matches[best_doc_id], key=lambda x: x["score"], reverse=True)[:5]
    
    context_items = [m["content"] for m in selected_matches]
    
    header = "GEFUNDENE INFORMATIONEN (OCR-AUSZUG):\n"
    return header + "\n---\n".join(context_items) + "\n\n"
