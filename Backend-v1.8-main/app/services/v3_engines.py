import json
import base64
import httpx
from typing import List, Dict, Any
from app.services import llm, prompts

async def information_gate(image_b64: str) -> Dict[str, Any]:
    """Stage 1: GPT-4o Mini binary informational gatekeeper."""
    response = await llm.call_openai(
        system_prompt=prompts.V3_INFORMATION_GATE,
        user_content="Determine informational suitability for the provided image.",
        model=llm.OPENAI_GPT4O_MINI_MODEL,
        image_b64=image_b64
    )
    # Extract JSON from potential markdown code blocks
    clean_resp = response.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_resp)

async def visual_structure_engine(image_b64: str) -> Dict[str, Any]:
    """Stage 2: GPT-4o layout analyzer."""
    response = await llm.call_openai(
        system_prompt=prompts.V3_VISUAL_STRUCTURE_CONTEXT_ENGINE,
        user_content="Decompose the layout of this image.",
        model=llm.OPENAI_GPT4O_MODEL,
        image_b64=image_b64
    )
    clean_resp = response.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_resp)

async def diagram_engine(image_b64: str) -> str:
    """Stage 3: GPT-4o diagram analyzer."""
    return await llm.call_openai(
        system_prompt=prompts.V3_DIAGRAM_MODE,
        user_content="Describe this diagram precisely.",
        model=llm.OPENAI_GPT4O_MODEL,
        image_b64=image_b64
    )

async def table_engine(image_b64: str) -> str:
    """Stage 4: GPT-4o table analyzer."""
    return await llm.call_openai(
        system_prompt=prompts.V3_TABLE_MODE,
        user_content="Convert this table into structured text.",
        model=llm.OPENAI_GPT4O_MODEL,
        image_b64=image_b64
    )

async def illustration_engine(image_b64: str) -> str:
    """Stage 5: GPT-4o illustration analyzer."""
    return await llm.call_openai(
        system_prompt=prompts.V3_ILLUSTRATION_MODE,
        user_content="Describe this illustration strictly visually.",
        model=llm.OPENAI_GPT4O_MODEL,
        image_b64=image_b64
    )

async def ocr_engine(image_b64: str) -> List[str]:
    """Stage 6: GPT-4o text extraction."""
    response = await llm.call_openai(
        system_prompt=prompts.V3_OCR_ENGINE,
        user_content="Extract clean paragraphs from this image.",
        model=llm.OPENAI_GPT4O_MODEL,
        image_b64=image_b64
    )
    # Split response into paragraphs, assuming newline separation
    return [p.strip() for p in response.split("\n\n") if p.strip()]

async def cohesion_engine(prev_paragraph: str, curr_paragraph: str) -> Dict[str, Any]:
    """Stage 7: GPT-4o Mini paragraph cohesion classifier."""
    user_content = f"PREVIOUS PARAGRAPH:\n{prev_paragraph}\n\nCURRENT PARAGRAPH:\n{curr_paragraph}\n\nDetermine cohesion."
    response = await llm.call_openai(
        system_prompt=prompts.V3_PARAGRAPH_LOGIC_ENGINE,
        user_content=user_content,
        model=llm.OPENAI_GPT4O_MINI_MODEL
    )
    clean_resp = response.replace("```json", "").replace("```", "").strip()
    return json.loads(clean_resp)

async def embedding_engine(text: str) -> List[float]:
    """Stage 8: OpenAI Embedding generator."""
    return await llm.call_embeddings(text)
