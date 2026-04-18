"""
PostgreSQL database layer using SQLAlchemy (async).
Manages: legal_documents, chat_sessions, chat_messages tables.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from .config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQLAlchemy Base & Models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class LegalDocument(Base):
    """Full-text legal document stored for citation lookup."""

    __tablename__ = "legal_documents"

    id = Column(String(50), primary_key=True)  # Matches HuggingFace/Qdrant document_id
    title = Column(Text, nullable=False, default="")
    content_html = Column(Text, default="")
    clean_text = Column(Text, default="")
    doc_type = Column(String(100), default="")
    document_number = Column(String(100), default="")
    validity_status = Column(String(50), default="Còn hiệu lực")
    metadata_json = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    """A conversation session (one sidebar item)."""

    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    title = Column(Text, default="Cuộc hội thoại mới")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id")


class ChatMessage(Base):
    """A single message in a conversation (human or AI)."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(UUID(as_uuid=False), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "human" or "ai"
    content = Column(Text, nullable=False)
    citations_json = Column(JSONB, default=list)  # [{article, law_name, document_id, ...}]
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------

_engine = None
_async_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.POSTGRES_URL,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def init_db() -> None:
    """Create all tables if they don't exist."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ PostgreSQL tables created/verified.")


async def close_db() -> None:
    """Dispose engine on shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
    logger.info("PostgreSQL engine disposed.")


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

async def upsert_legal_document(
    doc_id: str,
    title: str,
    content_html: str,
    clean_text: str,
    doc_type: str = "",
    document_number: str = "",
    validity_status: str = "Còn hiệu lực",
) -> None:
    """Insert or update a legal document."""
    factory = get_session_factory()
    async with factory() as session:
        existing = await session.get(LegalDocument, doc_id)
        if existing:
            existing.title = title
            existing.content_html = content_html
            existing.clean_text = clean_text
            existing.doc_type = doc_type
            existing.document_number = document_number
            existing.validity_status = validity_status
        else:
            session.add(LegalDocument(
                id=doc_id,
                title=title,
                content_html=content_html,
                clean_text=clean_text,
                doc_type=doc_type,
                document_number=document_number,
                validity_status=validity_status,
            ))
        await session.commit()


async def get_legal_document(doc_id: str) -> Optional[LegalDocument]:
    """Fetch a single legal document by ID."""
    factory = get_session_factory()
    async with factory() as session:
        return await session.get(LegalDocument, doc_id)


async def upsert_legal_documents_batch(documents: list[dict], batch_size: int = 100) -> int:
    """Batch upsert legal documents. Each dict must have 'id', 'title', etc."""
    factory = get_session_factory()
    total = 0
    async with factory() as session:
        for start in range(0, len(documents), batch_size):
            batch = documents[start:start + batch_size]
            for doc in batch:
                existing = await session.get(LegalDocument, doc["id"])
                if existing:
                    existing.title = doc.get("title", "")
                    existing.content_html = doc.get("content_html", "")
                    existing.clean_text = doc.get("clean_text", "")
                    existing.doc_type = doc.get("doc_type", "")
                    existing.document_number = doc.get("document_number", "")
                    existing.validity_status = doc.get("validity_status", "Còn hiệu lực")
                else:
                    session.add(LegalDocument(
                        id=doc["id"],
                        title=doc.get("title", ""),
                        content_html=doc.get("content_html", ""),
                        clean_text=doc.get("clean_text", ""),
                        doc_type=doc.get("doc_type", ""),
                        document_number=doc.get("document_number", ""),
                        validity_status=doc.get("validity_status", "Còn hiệu lực"),
                    ))
                total += 1
            await session.commit()
            logger.debug("Upserted SQL batch %d–%d", start, start + len(batch))
    logger.info("Upserted %d legal documents to PostgreSQL.", total)
    return total


# ---------------------------------------------------------------------------
# Chat Session CRUD
# ---------------------------------------------------------------------------

async def create_chat_session(title: str = "Cuộc hội thoại mới") -> ChatSession:
    factory = get_session_factory()
    async with factory() as session:
        chat_session = ChatSession(title=title)
        session.add(chat_session)
        await session.commit()
        await session.refresh(chat_session)
        return chat_session


async def list_chat_sessions(limit: int = 50) -> list[ChatSession]:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


async def get_chat_session(session_id: str) -> Optional[ChatSession]:
    factory = get_session_factory()
    async with factory() as session:
        return await session.get(ChatSession, session_id)


async def delete_chat_session(session_id: str) -> bool:
    factory = get_session_factory()
    async with factory() as session:
        chat_session = await session.get(ChatSession, session_id)
        if chat_session:
            await session.delete(chat_session)
            await session.commit()
            return True
        return False


async def update_chat_session_title(session_id: str, title: str) -> None:
    factory = get_session_factory()
    async with factory() as session:
        chat_session = await session.get(ChatSession, session_id)
        if chat_session:
            chat_session.title = title
            chat_session.updated_at = datetime.now(timezone.utc)
            await session.commit()


# ---------------------------------------------------------------------------
# Chat Message CRUD
# ---------------------------------------------------------------------------

async def add_chat_message(
    session_id: str,
    role: str,
    content: str,
    citations: list[dict] | None = None,
) -> ChatMessage:
    factory = get_session_factory()
    async with factory() as session:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            citations_json=citations or [],
        )
        session.add(msg)

        # Update session timestamp
        chat_session = await session.get(ChatSession, session_id)
        if chat_session:
            chat_session.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(msg)
        return msg


async def get_chat_messages(session_id: str, limit: int = 20) -> list[ChatMessage]:
    """Get the last N messages for a session."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # Oldest first
        return messages
