"""
FastAPI application with endpoints for:
  - /ingest       (POST)  — Background data ingestion
  - /ingest/status (GET)  — Ingestion progress
  - /chat         (POST)  — Streaming legal Q&A (SSE) with memory
  - /chat/sync    (POST)  — Non-streaming Q&A
  - /review-contract (POST) — Contract risk assessment
  - /sessions     (GET/POST/DELETE) — Chat session management
  - /sessions/{id}/messages (GET) — Chat history
  - /documents/{id} (GET) — Full legal document viewer
  - /health       (GET)   — Health check
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .database import QdrantManager
from .database_sql import (
    add_chat_message,
    close_db,
    create_chat_session,
    delete_chat_session,
    get_chat_messages,
    get_chat_session,
    get_legal_document,
    get_unique_doc_types,
    init_db,
    list_chat_sessions,
    list_legal_documents,
    update_chat_session_title,
)
from .generator import LegalRAGGenerator
from .ingestion import (
    get_ingest_status, 
    run_full_ingestion, 
    run_ingestion_by_numbers, 
    run_test_ingestion,
    stop_ingestion_task
)
from .models import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatWithMemoryRequest,
    ContractReviewRequest,
    ContractReviewResponse,
    IngestRequest,
    IngestByNumbersRequest,
    IngestState,
    IngestStatus,
    LegalAnswer,
    LegalDocumentListItem,
    LegalDocumentPaginationResponse,
    LegalDocumentResponse,
)
from .retriever import HybridRetriever

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Silence verbose HTTP logs if configured
if not settings.LOG_HTTPX:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Application lifespan — lazy initialisation of heavy components
# ---------------------------------------------------------------------------

_retriever: Optional[HybridRetriever] = None
_generator: Optional[LegalRAGGenerator] = None
_db: Optional[QdrantManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise resources on startup, cleanup on shutdown."""
    global _retriever, _generator, _db

    logger.info("🚀 Starting Vietnamese Legal Assistant API …")
    _db = QdrantManager()

    # Initialise PostgreSQL tables
    try:
        await init_db()
        logger.info("✅ PostgreSQL initialised.")
    except Exception as e:
        logger.warning("⚠️  PostgreSQL not available: %s", e)

    # Try to initialise retriever (will gracefully handle missing indices)
    try:
        _retriever = HybridRetriever()
        _generator = LegalRAGGenerator(retriever=_retriever)
        logger.info("✅ Retriever and generator initialised.")
    except Exception as e:
        logger.warning(
            "⚠️  Could not initialise retriever/generator (run /ingest first): %s", e
        )
        _retriever = None
        _generator = None

    yield

    await close_db()
    logger.info("👋 Shutting down …")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Vietnamese Legal Assistant API",
    description="RAG-powered legal Q&A and contract review for Vietnamese law.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_generator() -> LegalRAGGenerator:
    """Ensure the generator is available, or raise 503."""
    global _retriever, _generator
    if _generator is None:
        # Try to (re)initialise — indices may have appeared after ingestion
        try:
            _retriever = HybridRetriever()
            _generator = LegalRAGGenerator(retriever=_retriever)
        except Exception:
            raise HTTPException(
                status_code=503,
                detail="System chưa sẵn sàng. Vui lòng chạy /ingest trước.",
            )
    return _generator


# ---------------------------------------------------------------------------
# Endpoints — Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """Health check: Qdrant connection + collection stats."""
    db_info = _db.get_collection_info() if _db else {"error": "DB not initialised"}
    ingest = get_ingest_status()
    return {
        "status": "ok",
        "qdrant": db_info,
        "ingest": ingest.model_dump(),
    }


# ---------------------------------------------------------------------------
# Endpoints — Ingestion
# ---------------------------------------------------------------------------

@app.post("/ingest/download-data", tags=["Ingestion"])
async def download_legal_data():
    """
    Download all required dataset files (metadata, content, relationships) 
    from HuggingFace to local storage.
    """
    from .downloader import download_all_legal_data
    try:
        results = await download_all_legal_data()
        return {
            "status": "success",
            "files": results,
            "message": "Data download process completed."
        }
    except Exception as e:
        logger.error("Download failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/full", tags=["Ingestion"], response_model=IngestStatus)
async def ingest_full(background_tasks: BackgroundTasks, limit: Optional[int] = None):
    """
    Start full ingestion pipeline from local files.
    - limit: Optional number of documents to process.
    """
    status = get_ingest_status()
    if status.state == IngestState.RUNNING:
        raise HTTPException(status_code=409, detail="Ingestion đang chạy.")

    async def _run():
        await run_full_ingestion(limit=limit)
        # Reload retriever indices after ingestion
        global _retriever, _generator
        try:
            _retriever = HybridRetriever()
            _generator = LegalRAGGenerator(retriever=_retriever)
            logger.info("✅ Retriever reloaded after ingestion.")
        except Exception as e:
            logger.error("Failed to reload retriever: %s", e)

    background_tasks.add_task(_run)
    return IngestStatus(state=IngestState.RUNNING)


@app.post("/ingest/stop", tags=["Ingestion"])
async def stop_ingest():
    """
    Request to stop the current ingestion task.
    """
    stop_ingestion_task()
    return {"message": "Stop request sent. Ingestion will halt shortly."}


@app.post("/ingest/by-numbers", tags=["Ingestion"], response_model=IngestStatus)
async def ingest_by_numbers(request: IngestByNumbersRequest, background_tasks: BackgroundTasks):
    """
    Ingest specific documents by their so_ky_hieu.
    """
    status = get_ingest_status()
    if status.state == IngestState.RUNNING:
        raise HTTPException(status_code=409, detail="Bộ máy nạp dữ liệu đang bận.")

    async def _run():
        await run_ingestion_by_numbers(request.doc_numbers)
        # Reload indices
        global _retriever, _generator
        try:
            _retriever = HybridRetriever()
            _generator = LegalRAGGenerator(retriever=_retriever)
            logger.info("✅ Retriever reloaded after targeted ingestion.")
        except Exception as e:
            logger.error("Failed to reload retriever: %s", e)

    background_tasks.add_task(_run)
    return IngestStatus(state=IngestState.RUNNING)


@app.post("/ingest/test", tags=["Ingestion"], response_model=IngestStatus)
async def ingest_test(background_tasks: BackgroundTasks):
    """
    DEBUG ONLY: Ingest first 50 docs WITHOUT any filtering.
    """
    status = get_ingest_status()
    if status.state == IngestState.RUNNING:
        raise HTTPException(status_code=409, detail="Bộ máy nạp dữ liệu đang bận.")

    async def _run():
        await run_test_ingestion(limit=50)
        # Reload indices
        global _retriever, _generator
        try:
            _retriever = HybridRetriever()
            _generator = LegalRAGGenerator(retriever=_retriever)
            logger.info("✅ Retriever reloaded after test ingestion.")
        except Exception as e:
            logger.error("Failed to reload retriever: %s", e)

    background_tasks.add_task(_run)
    return IngestStatus(state=IngestState.RUNNING)


@app.get("/ingest/status", tags=["Ingestion"], response_model=IngestStatus)
async def ingest_status():
    """Get current ingestion progress."""
    return get_ingest_status()


# ---------------------------------------------------------------------------
# Endpoints — Chat (Streaming SSE) with Memory
# ---------------------------------------------------------------------------

@app.post("/chat", tags=["Chat"])
async def chat(request: ChatWithMemoryRequest):
    """
    Legal Q&A with streaming Server-Sent Events + Conversation Memory.

    If session_id is provided, loads previous messages as context.
    Streams the LLM's response token by token, then sends a final
    JSON event with the structured LegalAnswer.
    """
    generator = _require_generator()

    # Load conversation history if session_id provided
    history_messages = []
    session_id = request.session_id

    if session_id:
        try:
            db_messages = await get_chat_messages(session_id, limit=10)
            for msg in db_messages:
                history_messages.append({"role": msg.role, "content": msg.content})
        except Exception as e:
            logger.warning("Could not load session history: %s", e)

    try:
        results, token_stream = await generator.answer_question_stream(
            question=request.question,
            top_k=request.top_k,
            validity_filter=request.filter_validity,
            history_messages=history_messages,
        )
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    async def event_generator():
        full_text = ""
        try:
            async for token in token_stream:
                full_text += token
                yield {"event": "token", "data": token}

            # Build structured answer from full text
            evidence_pack = HybridRetriever.build_evidence_pack(results)
            answer = LegalRAGGenerator._parse_legal_answer(full_text, evidence_pack)
            response = ChatResponse(
                question=request.question,
                answer=answer,
                retrieval_count=len(results),
            )

            # Save to database if session_id
            if session_id:
                try:
                    await add_chat_message(session_id, "human", request.question)
                    citations_data = [c.model_dump() for c in answer.citations]
                    await add_chat_message(session_id, "ai", full_text, citations_data)

                    # Auto-title if first message
                    db_msgs = await get_chat_messages(session_id, limit=3)
                    if len(db_msgs) <= 2:
                        title = request.question[:60]
                        if len(request.question) > 60:
                            title += "…"
                        await update_chat_session_title(session_id, title)
                except Exception as e:
                    logger.warning("Failed to persist chat: %s", e)

            yield {
                "event": "done",
                "data": response.model_dump_json(),
            }
        except Exception as e:
            logger.error("Stream error: %s", e, exc_info=True)
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())


# ---- Chat (non-streaming, for simplicity) --------------------------------

@app.post("/chat/sync", tags=["Chat"], response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """
    Non-streaming legal Q&A. Returns full structured answer.
    """
    generator = _require_generator()

    try:
        answer = await generator.answer_question(
            question=request.question,
            top_k=request.top_k,
            validity_filter=request.filter_validity,
        )
    except Exception as e:
        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        question=request.question,
        answer=answer,
        retrieval_count=len(answer.citations),
    )


# ---------------------------------------------------------------------------
# Endpoints — Contract Review
# ---------------------------------------------------------------------------

@app.post(
    "/review-contract",
    tags=["Contract Review"],
    response_model=ContractReviewResponse,
)
async def review_contract(request: ContractReviewRequest):
    """
    Analyse a contract for legal risks.
    Returns structured risk assessment with citations.
    """
    generator = _require_generator()

    try:
        result = await generator.review_contract(
            contract_text=request.contract_text,
            contract_type=request.contract_type,
            focus_areas=request.focus_areas,
        )
    except Exception as e:
        logger.error("Contract review error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return result


# ---------------------------------------------------------------------------
# Endpoints — Chat Sessions (History Management)
# ---------------------------------------------------------------------------

@app.get("/sessions", tags=["Sessions"], response_model=list[ChatSessionResponse])
async def list_sessions():
    """List all chat sessions, most recent first."""
    sessions = await list_chat_sessions()
    return [
        ChatSessionResponse(
            id=str(s.id),
            title=s.title or "Cuộc hội thoại mới",
            created_at=s.created_at.isoformat() if s.created_at else "",
            updated_at=s.updated_at.isoformat() if s.updated_at else "",
        )
        for s in sessions
    ]


@app.post("/sessions", tags=["Sessions"], response_model=ChatSessionResponse)
async def create_session(request: ChatSessionCreate):
    """Create a new chat session."""
    session = await create_chat_session(title=request.title)
    return ChatSessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
    )


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str):
    """Delete a chat session and all its messages."""
    deleted = await delete_chat_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"status": "deleted"}


@app.get(
    "/sessions/{session_id}/messages",
    tags=["Sessions"],
    response_model=list[ChatMessageResponse],
)
async def get_session_messages(session_id: str, limit: int = 50):
    """Get messages for a specific chat session."""
    messages = await get_chat_messages(session_id, limit=limit)
    return [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            citations=msg.citations_json or [],
            created_at=msg.created_at.isoformat() if msg.created_at else "",
        )
        for msg in messages
    ]


# ---------------------------------------------------------------------------
# Endpoints — Legal Document Viewer
# ---------------------------------------------------------------------------

@app.get(
    "/documents/{doc_id}",
    tags=["Documents"],
    response_model=LegalDocumentResponse,
)
async def get_document(doc_id: str):
    """
    Get the full text of a legal document by ID.
    Used when user clicks on a citation to view the source.
    """
    doc = await get_legal_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Văn bản không tìm thấy.")
    return LegalDocumentResponse(
        id=doc.id,
        title=doc.title,
        clean_text=doc.clean_text or "",
        content_html=doc.content_html or "",
        doc_type=doc.doc_type,
        document_number=doc.document_number,
        validity_status=doc.validity_status,
        issuing_body=doc.metadata_json.get("issuing_body", "Đang cập nhật") if isinstance(doc.metadata_json, dict) else "Đang cập nhật",
    )


@app.get(
    "/legal-documents",
    tags=["Documents"],
    response_model=LegalDocumentPaginationResponse,
)
async def get_legal_documents(
    q: str | None = None, 
    doc_type: str | None = None,
    page: int = Query(1, ge=1), 
    limit: int = Query(20, ge=1, le=100)
):
    """List legal documents with pagination and filtering."""
    skip = (page - 1) * limit
    docs, total = await list_legal_documents(query=q, doc_type=doc_type, skip=skip, limit=limit)
    
    items = [
        LegalDocumentListItem(
            id=d.id,
            title=d.title or "",
            doc_type=d.doc_type or "",
            document_number=d.document_number or "",
            validity_status=d.validity_status or "",
            issuing_body=d.metadata_json.get("issuing_body", "Đang cập nhật") if isinstance(d.metadata_json, dict) else "Đang cập nhật",
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in docs
    ]
    
    return LegalDocumentPaginationResponse(
        items=items,
        total=total,
        page=page,
        page_size=limit
    )


@app.get("/legal-documents/types", tags=["Documents"])
async def get_legal_document_types():
    """Returns a list of unique document types present in the library."""
    types = await get_unique_doc_types()
    return types


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )
