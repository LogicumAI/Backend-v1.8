"""
AI Response Pipeline Orchestrator.

Flow:
  1. Parallel: Summary Engine | Prompt Optimizer | Router | Nano Relevance Selector
  2. Model Execution (Flash or GPT52)
  3. TURN_SUMMARY Generator (internal, not returned to user)
"""

import asyncio
import time
from sqlmodel import Session, select

from app.models import Chat, Message, TurnSummary
from app.services.llm import (
    call_openai,
    OPENAI_GPT4O_MODEL,
    OPENAI_GPT4O_MINI_MODEL,
)
from app.services.storage import storage_service
from app.services.prompts import (
    PROMPT_OPTIMIZER,
    ROUTER,
    NANO_RELEVANCE_SELECTOR,
    SUMMARY_ENGINE,
    TURN_SUMMARY_GENERATOR,
    build_flash_system_prompt,
    build_gpt52_system_prompt,
    build_codex_system_prompt,
)
from app.services.retrieval import run_ocr_retrieval


# Versioning
BACKEND_VERSION = "2.1"


# ── Step 1a: Summary Engine ─────────────────
async def run_summary_engine(user_message: str) -> str:
    """Produce a structured understanding confirmation (Part 1 of response)."""
    return await call_openai(
        system_prompt=SUMMARY_ENGINE,
        user_content=user_message,
        model=OPENAI_GPT4O_MINI_MODEL,
        max_tokens=512,
    )



# ── Step 1b: Prompt Optimizer ────────────────
async def run_prompt_optimizer(user_message: str) -> str:
    """Transform raw user input into an optimized, execution-ready prompt."""
    return await call_openai(
        system_prompt=PROMPT_OPTIMIZER,
        user_content=user_message,
        model=OPENAI_GPT4O_MINI_MODEL,
        max_tokens=1024,
    )


# ── Step 1c: Router ──────────────────────────
async def run_router(user_message: str) -> str:
    """Classify request → returns 'FLASH' or 'GPT52'."""
    try:
        raw = await call_openai(
            system_prompt=ROUTER,
            user_content=user_message,
            model=OPENAI_GPT4O_MINI_MODEL,
            max_tokens=10,
        )
        route = raw.strip().upper()
        # Ensure we only return spec-compliant tokens
        if "GPT52" in route or "GPT-5.2" in route:
            return "GPT52"
        elif "CODEX" in route:
            return "CODEX"
        return "FLASH"
    except Exception as e:
        print(f"Router failure: {e}")
        return "FLASH"


# ── Step 1d: Nano Relevance Selector ─────────
async def run_relevance_selector(
    user_message: str, session: Session, chat_id: int
) -> str:
    """Select relevant TURN_SUMMARYs from history for the current request."""
    # Fetch the last 10 turn summaries for this chat
    stmt = (
        select(TurnSummary)
        .where(TurnSummary.chat_id == chat_id)
        .order_by(TurnSummary.turn_index.desc())  # type: ignore[union-attr]
        .limit(10)
    )
    summaries = session.exec(stmt).all()

    if not summaries:
        return "RELEVANT_CONTEXT\n- none"

    # Build input for nano model
    summary_block = "\n".join(
        f"TURN_SUMMARY (turn {s.turn_index}):\n- {s.summary}"
        for s in reversed(summaries)
    )
    user_content = (
        f"Current user message:\n{user_message}\n\n"
        f"Stored TURN_SUMMARY blocks:\n{summary_block}"
    )

    return await call_openai(
        system_prompt=NANO_RELEVANCE_SELECTOR,
        user_content=user_content,
        model=OPENAI_GPT4O_MINI_MODEL,
        max_tokens=300,
    )


# ── Step 2: Model Execution ─────────────────
async def run_model_execution(
    optimized_prompt: str,
    relevant_context: str,
    route: str,
) -> str:
    """Execute the main model (Flash or GPT52) with optimized prompt + context."""
    user_content = (
        f"{relevant_context}\n\n"
        f"{optimized_prompt}"
    )

    if route == "GPT52":
        system_prompt = build_gpt52_system_prompt()
        return await call_openai(
            system_prompt=system_prompt,
            user_content=user_content,
            model="GPT52",
        )
    elif route == "CODEX":
        system_prompt = build_codex_system_prompt()
        return await call_openai(
            system_prompt=system_prompt,
            user_content=user_content,
            model="CODEX",
        )
    else:
        # Defaults to FLASH
        system_prompt = build_flash_system_prompt()
        return await call_openai(
            system_prompt=system_prompt,
            user_content=user_content,
            model="FLASH",
        )


# ── Step 3: TURN_SUMMARY Generator ──────────
async def run_turn_summary_generator(
    user_message: str, ai_response: str
) -> str:
    """Compress the turn into a TURN_SUMMARY for future retrieval (not shown to user)."""
    user_content = (
        f"User message:\n{user_message}\n\n"
        f"AI response:\n{ai_response}"
    )
    return await call_openai(
        system_prompt=TURN_SUMMARY_GENERATOR,
        user_content=user_content,
        model=OPENAI_GPT4O_MINI_MODEL,
        max_tokens=200,
    )


# ── Full Pipeline ────────────────────────────
async def execute_pipeline(
    user_message: str,
    chat_id: int,
    session: Session,
    user_id: int,
    study_mode: bool = False,
) -> dict:
    """
    Run the complete AI response pipeline with optional OCR retrieval.
    """
    start = time.perf_counter()

    # ── Phase 1: parallel pre-processing ─────
    start_initial = time.perf_counter()
    summary_task = asyncio.create_task(run_summary_engine(user_message))
    optimizer_task = asyncio.create_task(run_prompt_optimizer(user_message))
    router_task = asyncio.create_task(run_router(user_message))
    relevance_task = asyncio.create_task(
        run_relevance_selector(user_message, session, chat_id)
    )
    retrieval_task = asyncio.create_task(run_ocr_retrieval(user_id, user_message))

    # Run Phase 1 tasks
    results = await asyncio.gather(
        summary_task, optimizer_task, router_task, relevance_task, retrieval_task,
        return_exceptions=True
    )
    latency_initial_ms = int((time.perf_counter() - start_initial) * 1000)
    
    # Unpack safely
    summary = results[0] if not isinstance(results[0], Exception) else "Planung der Antwort..."
    if isinstance(summary, str) and summary.strip() == "SKIP":
        summary = ""

    optimized_prompt = results[1] if not isinstance(results[1], Exception) else user_message
    if isinstance(optimized_prompt, str) and optimized_prompt.strip() == "SKIP":
        optimized_prompt = user_message

    route = results[2] if not isinstance(results[2], Exception) else "FLASH"
    relevant_context = results[3] if not isinstance(results[3], Exception) else "RELEVANT_CONTEXT\n- none"
    ocr_context = results[4] if not isinstance(results[4], Exception) else ""

    # ── Study Mode Abort Logic ────────────────
    if study_mode and not ocr_context:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "summary": "Studien-Modus aktiv: Verifizierung wird durchgeführt...",
            "answer": "Zu dieser Anfrage wurde in den Unterlagen kein passender Kontext gefunden (Study Mode aktiv).",
            "initial_model": "GPT 5 Nano",
            "execution_model": "ABORTED",
            "latency_initial_ms": latency_initial_ms,
            "latency_execution_ms": 0,
            "latency_ms": latency_ms,
            "backend_version": BACKEND_VERSION,
        }

    # Combine all context
    full_context = f"{relevant_context}\n\n{ocr_context}".strip()

    # ── Phase 2: model execution ─────────────
    start_execution = time.perf_counter()
    try:
        answer = await run_model_execution(optimized_prompt, full_context, route)
        if not answer:
            answer = "Sorry, I couldn't generate a valid response right now."
    except Exception as e:
        print(f"Model execution critical failure: {e}")
        answer = "I apologize, but my core engine encountered an error. Please try again in a moment."
    
    latency_execution_ms = int((time.perf_counter() - start_execution) * 1000)
    latency_ms = int((time.perf_counter() - start) * 1000)

    # ── Phase 2.5: S3 Data Center Storage ──────
    # We save both user and assistant messages for persistence
    await asyncio.gather(
        storage_service.save_message(user_id, chat_id, "user", user_message, 0),
        storage_service.save_message(user_id, chat_id, "assistant", answer, 1),
    )

    # ── Phase 3: TURN_SUMMARY (fire-and-forget style, but we await to store) ──
    turn_summary_text = await run_turn_summary_generator(user_message, answer)

    # Determine next turn index
    stmt = (
        select(TurnSummary)
        .where(TurnSummary.chat_id == chat_id)
        .order_by(TurnSummary.turn_index.desc())  # type: ignore[union-attr]
        .limit(1)
    )
    last = session.exec(stmt).first()
    next_index = (last.turn_index + 1) if last else 1

    # Store the TURN_SUMMARY
    ts = TurnSummary(
        chat_id=chat_id,
        turn_index=next_index,
        summary=turn_summary_text,
    )
    session.add(ts)
    session.commit()

    return {
        "summary": summary,
        "answer": answer,
        "initial_model": "GPT 5 Nano",
        "execution_model": route,
        "latency_initial_ms": latency_initial_ms,
        "latency_execution_ms": latency_execution_ms,
        "latency_ms": latency_ms,
        "backend_version": BACKEND_VERSION,
    }
