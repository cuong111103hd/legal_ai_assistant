"""
Pydantic v2 data models for the Legal RAG system.
Covers: document chunks, search results, evidence packs, API request/response.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SearchSource(str, Enum):
    """Origin of a search result."""
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


class IngestState(str, Enum):
    """Ingestion job state."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QueryStrategy(str, Enum):
    """Query routing strategies."""
    CITATION = "citation"       # Exact legal reference lookup
    NEGATION = "negation"       # Negation-aware retrieval
    SEMANTIC = "semantic"       # Standard hybrid retrieval


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------

class QueryPlan(BaseModel):
    """Structured query plan output from the Query Planner."""
    original_query: str
    normalized_query: str
    expansion_variants: list[str] = Field(default_factory=list, description="Synonym-expanded queries")

    has_negation: bool = False
    negation_scope: Optional[str] = None

    citations: list[str] = Field(default_factory=list, description="Extracted legal citation patterns")
    strategy: QueryStrategy = QueryStrategy.SEMANTIC

    search_filters: dict[str, Any] = Field(default_factory=dict, description="Metadata filters for retrieval")


class VerificationResult(BaseModel):
    """Result of the legal verification process."""
    is_accurate: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    corrections: Optional[str] = None
    hallucination_found: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)


class LegalChunk(BaseModel):
    """A single chunk of a legal document with metadata."""
    chunk_id: str = Field(..., description="Unique ID for this chunk")
    document_id: str = Field(..., description="Original document ID from dataset")
    law_name: str = Field(default="", description="Name of the law / decree / circular")
    article_id: str = Field(default="", description="Extracted Điều identifier, e.g. 'Điều 168'")
    content: str = Field(..., description="Chunk text content")
    validity_status: str = Field(default="Còn hiệu lực", description="Document validity")
    doc_type: str = Field(default="", description="Luật / Nghị định / Thông tư / …")
    document_number: str = Field(default="", description="Số hiệu văn bản, e.g. '45/2019/QH14'")
    chunk_index: int = Field(default=0, description="Positional index within the parent document")


class Citation(BaseModel):
    """A single legal citation."""
    article: str = Field(..., description="Điều reference, e.g. 'Điều 168'")
    clause: str = Field(default="", description="Khoản reference, e.g. 'Khoản 1'")
    law_name: str = Field(default="", description="Full law name")
    document_number: str = Field(default="", description="Số hiệu văn bản, e.g. '45/2019/QH14'")
    document_id: str = Field(default="", description="Document ID for deep linking to full text")
    excerpt: str = Field(default="", description="Relevant excerpt from the article")



class EvidencePack(BaseModel):
    """Structured evidence the LLM must reference before answering."""
    citations: list[Citation] = Field(default_factory=list)

    def format_for_prompt(self) -> str:
        """Render evidence as a numbered list for the LLM prompt."""
        lines: list[str] = []
        for i, c in enumerate(self.citations, 1):
            header = f"[{i}] {c.article}"
            if c.clause:
                header += f", {c.clause}"
            header += f" — {c.law_name}"
            if c.document_number:
                header += f" (Số hiệu: {c.document_number})"
            lines.append(header)
            if c.excerpt:
                lines.append(f'    "{c.excerpt}"')
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """A single search result with provenance."""
    chunk: LegalChunk
    score: float = Field(default=0.0)
    source: SearchSource = Field(default=SearchSource.HYBRID)


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for /chat endpoint."""
    question: str = Field(..., min_length=1, description="User's legal question")
    top_k: int = Field(default=10, ge=1, le=50)
    filter_validity: Optional[str] = Field(
        default=None,
        description="Filter by validity status, e.g. 'Còn hiệu lực'",
    )


class LegalAnswer(BaseModel):
    """Structured answer from the generation engine."""
    answer: str = Field(..., description="Main answer text")
    risk_analysis: str = Field(default="", description="Risk analysis (if applicable)")
    citations: list[Citation] = Field(default_factory=list)
    evidence_pack: EvidencePack = Field(default_factory=EvidencePack)
    verification_result: Optional[VerificationResult] = None


class ChatResponse(BaseModel):
    """Response body for /chat endpoint."""
    question: str
    answer: LegalAnswer
    retrieval_count: int = Field(default=0, description="Number of chunks retrieved")


class ContractReviewRequest(BaseModel):
    """Request body for /review-contract endpoint."""
    contract_text: str = Field(..., min_length=10, description="Full contract text")
    contract_type: str = Field(
        default="Hợp đồng lao động",
        description="Type of contract",
    )
    focus_areas: list[str] = Field(
        default_factory=lambda: [
            "Bảo hiểm xã hội",
            "Thời hạn hợp đồng",
            "Điều khoản chấm dứt",
            "Quyền lợi người lao động",
        ],
        description="Areas to focus risk analysis on",
    )


class ContractRiskItem(BaseModel):
    """A single risk identified in a contract."""
    risk_level: str = Field(..., description="Cao / Trung bình / Thấp")
    description: str = Field(..., description="Description of the risk")
    relevant_law: str = Field(default="", description="Applicable law / article")
    recommendation: str = Field(default="", description="Suggested action")


class ContractClause(BaseModel):
    """A single clause/article from a contract being reviewed."""
    title: str
    content: str
    analysis: str = Field(default="", description="Detailed LLM analysis of this specific clause")
    risks: list[ContractRiskItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class ContractReviewResponse(BaseModel):
    """Response body for /review-contract endpoint."""
    summary: str = Field(default="", description="Overall contract assessment")
    clauses: list[ContractClause] = Field(default_factory=list, description="Detail review per clause")
    overall_risks: list[ContractRiskItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class IngestRequest(BaseModel):
    """Request body for /ingest endpoint."""
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        description="Limit number of documents to ingest (for testing)",
    )


class IngestByNumbersRequest(BaseModel):
    """Request body for /ingest/by-numbers endpoint."""
    doc_numbers: list[str] = Field(..., description="List of so_ky_hieu (e.g. ['24/2018/QH14'])")


class IngestStatus(BaseModel):
    """Status response for ingestion job."""
    state: IngestState = Field(default=IngestState.IDLE)
    total_documents: int = Field(default=0)
    processed_documents: int = Field(default=0)
    total_chunks: int = Field(default=0)
    error_message: str = Field(default="")

    @property
    def progress_pct(self) -> float:
        if self.total_documents == 0:
            return 0.0
        return round(self.processed_documents / self.total_documents * 100, 1)


# ---------------------------------------------------------------------------
# Session & History models
# ---------------------------------------------------------------------------

class ChatSessionCreate(BaseModel):
    """Request body for creating a new chat session."""
    title: str = Field(default="Cuộc hội thoại mới")


class ChatSessionResponse(BaseModel):
    """Response for a chat session."""
    id: str
    title: str
    created_at: str
    updated_at: str


class ChatMessageResponse(BaseModel):
    """A single message in a session."""
    id: int
    role: str
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: str


class ChatWithMemoryRequest(BaseModel):
    """Request body for /chat with session memory."""
    question: str = Field(..., min_length=1, description="User's legal question")
    session_id: Optional[str] = Field(default=None, description="Session ID for memory continuity")
    top_k: int = Field(default=10, ge=1, le=50)
    filter_validity: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Document viewer
# ---------------------------------------------------------------------------

class LegalDocumentResponse(BaseModel):
    """Full legal document for the document viewer."""
    id: str
    title: str
    clean_text: str
    content_html: str = ""
    doc_type: str = ""
    document_number: str = ""
    validity_status: str = ""
    issuing_body: str = ""


class LegalDocumentListItem(BaseModel):
    """Metadata-only item for lists."""
    id: str
    title: str
    doc_type: str = ""
    document_number: str = ""
    validity_status: str = ""
    issuing_body: str = ""
    created_at: str


class LegalDocumentPaginationResponse(BaseModel):
    items: list[LegalDocumentListItem]
    total: int
    page: int
    page_size: int
