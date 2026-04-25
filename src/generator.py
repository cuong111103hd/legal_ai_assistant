"""
RAG Generation Engine.
Builds prompts with EvidencePack, calls LLM (Groq), and parses structured output.
Supports both Q&A and Contract Review modes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Optional
from langsmith import traceable


from .config import settings
from .models import (
    Citation,
    ContractClause,
    ContractReviewResponse,
    ContractRiskItem,
    EvidencePack,
    LegalAnswer,
    SearchResult,
    VerificationResult,
)
from .prompts.legal_rag import (
    CONTRACT_REVIEW_SYSTEM_PROMPT,
    CONTRACT_REVIEW_USER_TEMPLATE,
    LEGAL_QA_SYSTEM_PROMPT,
    LEGAL_QA_USER_TEMPLATE,
)
from .retriever import HybridRetriever
from .utils.text_processing import (
    chunk_contract_by_article,
    extract_article_id,
    extract_clause_id,
)
from .planner import LegalQueryPlanner
from .verifier import LegalVerifier

logger = logging.getLogger(__name__)


class LegalRAGGenerator:
    """
    Generates grounded legal answers using Groq or OpenAI.
    Enforces no-hallucination via EvidencePack prompting.
    """

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever
        self._planner = LegalQueryPlanner()

        if settings.LLM_PROVIDER.lower() == "openai":
            from openai import AsyncOpenAI

            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not configured.")
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("Initialized AsyncOpenAI generator with model: %s", settings.LLM_MODEL)
        else:
            from groq import AsyncGroq

            if not settings.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY is not configured. Check your .env file.")
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            logger.info("Initialized AsyncGroq generator with model: %s", settings.LLM_MODEL)

        self._verifier = LegalVerifier(self._client)

    # ------------------------------------------------------------------
    # Legal Q&A
    # ------------------------------------------------------------------

    @traceable(name="Legal Q&A Pipeline")
    async def answer_question(
        self,
        question: str,
        top_k: int = 10,
        validity_filter: Optional[str] = None,
    ) -> LegalAnswer:
        """
        Full RAG pipeline: Retrieve → Build EvidencePack → Generate answer.
        """
        # 1. Plan query
        query_plan = self._planner.plan(question)
        logger.info(f"Query Plan generated: Strategy={query_plan.strategy}, Expanded variants={len(query_plan.expansion_variants)}")

        # 2. Retrieve (Async in Phase 3)
        results = await self._retriever.search(
            query=question,
            query_plan=query_plan,
            top_k=top_k,
            validity_filter=validity_filter,
        )

        # 2. Build evidence pack
        evidence_pack = self._retriever.build_evidence_pack(results)

        # 3. Generate & Verify Loop (Phase 3)
        max_loops = 3
        current_loop = 0
        final_answer = None
        last_verification = None

        while current_loop < max_loops:
            current_loop += 1
            logger.info("Generation Loop %d/%d", current_loop, max_loops)

            user_prompt = LEGAL_QA_USER_TEMPLATE.format(
                question=question,
                evidence_pack=evidence_pack.format_for_prompt(),
            )

            # If it's a correction loop, append the previous mistakes
            if last_verification and last_verification.corrections:
                user_prompt += f"\n\nLƯU Ý: Lần trả lời trước có lỗi. Hãy sửa đổi dựa trên gợi ý sau: {last_verification.corrections}"

            response_text = await self._call_llm(
                system_prompt=LEGAL_QA_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )

            # Parse structured output
            answer = self._parse_legal_answer(response_text, evidence_pack)

            # 4. Verify (Phase 3)
            verification = await self._verifier.verify(
                answer=answer.answer,
                evidence_text=evidence_pack.format_for_prompt()
            )
            answer.verification_result = verification
            final_answer = answer
            last_verification = verification

            if verification.is_accurate:
                logger.info("✅ Answer verified as accurate on loop %d", current_loop)
                break
            else:
                logger.warning("⚠️ Hallucination or inaccuracy found on loop %d: %s", current_loop, verification.unsupported_claims)

        return final_answer

    @traceable(name="Legal Q&A Streaming")
    async def answer_question_stream(
        self,
        question: str,
        top_k: int = 10,
        validity_filter: Optional[str] = None,
        history_messages: list[dict] | None = None,
    ) -> tuple[list[SearchResult], AsyncGenerator[str, None]]:
        """
        Streaming version: returns search results + a generator that yields tokens.
        Supports conversation history for contextual follow-up.
        """
        # 1. Plan query
        query_plan = self._planner.plan(question)
        logger.info(f"Query Plan generated (stream): Strategy={query_plan.strategy}, Expanded variants={len(query_plan.expansion_variants)}")

        # 2. Retrieve (Async in Phase 3)
        results = await self._retriever.search(
            query=question,
            query_plan=query_plan,
            top_k=top_k,
            validity_filter=validity_filter,
        )

        # 2. Build evidence pack
        evidence_pack = self._retriever.build_evidence_pack(results)

        # 3. Create streaming generator
        user_prompt = LEGAL_QA_USER_TEMPLATE.format(
            question=question,
            evidence_pack=evidence_pack.format_for_prompt(),
        )

        # Build messages list with optional history
        messages = [{"role": "system", "content": LEGAL_QA_SYSTEM_PROMPT}]
        if history_messages:
            for msg in history_messages[-10:]:  # Last 10 messages max
                role = "user" if msg["role"] == "human" else "assistant"
                messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": user_prompt})

        async def token_generator():
            logger.info("Starting LLM stream (%s) with %d history messages …", settings.LLM_MODEL, len(history_messages or []))
            # Log to console in real-time for debugging
            print(f"\n[LLM STREAM START]", flush=True)

            stream = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                stream=True,
            )
            count = 0
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    count += 1
                    token = delta.content
                    print(token, end="", flush=True) # Live console output
                    yield token

            print(f"\n[LLM STREAM END] Total: {count} tokens\n", flush=True)
            logger.info("LLM stream finished. Sent %d tokens.", count)

        return results, token_generator()

    # ------------------------------------------------------------------
    # Contract review
    # ------------------------------------------------------------------

    @traceable(name="Contract Review Pipeline")
    async def review_contract(
        self,
        contract_text: str,
        contract_type: str = "Hợp đồng lao động",
        focus_areas: list[str] | None = None,
    ) -> ContractReviewResponse:
        """
        Analyse a contract for legal risks by chunking it into articles
        and reviewing them in parallel.
        """
        if focus_areas is None:
            focus_areas = [
                "Bảo hiểm xã hội",
                "Thời hạn hợp đồng",
                "Điều khoản chấm dứt",
                "Quyền lợi người lao động",
            ]

        # 1. Chunk contract
        clauses_data = chunk_contract_by_article(contract_text)
        logger.info("Contract split into %d clauses.", len(clauses_data))

        # 2. Process clauses in parallel (limit to first 15 clauses for performance/cost if huge)
        # In a real system we'd use a semaphore or queue
        tasks = []
        for c in clauses_data[:15]:  
            tasks.append(
                self._review_single_clause(
                    title=c["title"],
                    content=c["content"],
                    contract_type=contract_type
                )
            )

        # 3. Overall summary task
        summary_query = f"Quy định chung về {contract_type}"
        summary_results = await self._retriever.search(query=summary_query, top_k=5)
        summary_evidence = self._retriever.build_evidence_pack(summary_results)
        
        summary_task = self._call_llm(
            system_prompt=CONTRACT_REVIEW_SYSTEM_PROMPT,
            user_prompt=CONTRACT_REVIEW_USER_TEMPLATE.format(
                contract_type=contract_type,
                focus_areas="\n".join(f"- {a}" for a in focus_areas),
                contract_text=contract_text[:3000],
                evidence_pack=summary_evidence.format_for_prompt(),
            )
        )

        # Execute everything in parallel
        results = await asyncio.gather(*tasks, summary_task)
        
        reviewed_clauses = results[:-1]
        summary_text = results[-1]

        # 4. Parse summary
        overall_report = self._parse_contract_review(summary_text, summary_evidence)
        
        return ContractReviewResponse(
            summary=overall_report.summary,
            clauses=reviewed_clauses,
            overall_risks=overall_report.overall_risks,
            citations=self._filter_citations(summary_text, summary_evidence.citations),
        )

    async def _review_single_clause(
        self, 
        title: str, 
        content: str, 
        contract_type: str
    ) -> ContractClause:
        """Sub-agent task: review a single clause."""
        logger.info("Reviewing clause: %s", title)
        
        # Search for relevant laws for this specific clause
        search_query = f"{contract_type} {title} {content[:200]}"
        results = self._retriever.search(query=search_query, top_k=5)
        evidence_pack = self._retriever.build_evidence_pack(results)

        from .prompts.legal_rag import (
            CLAUSE_REVIEW_SYSTEM_PROMPT,
            CLAUSE_REVIEW_USER_TEMPLATE,
        )

        user_prompt = CLAUSE_REVIEW_USER_TEMPLATE.format(
            clause_title=title,
            clause_content=content,
            evidence_pack=evidence_pack.format_for_prompt(),
        )

        try:
            response_text = await self._call_llm(
                system_prompt=CLAUSE_REVIEW_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            # Find JSON in response
            json_match = re.search(r"(\{.*\})", response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
                return ContractClause(
                    title=title,
                    content=content,
                    analysis=data.get("analysis", ""),
                    risks=[ContractRiskItem(**r) for r in data.get("risks", [])],
                    citations=self._filter_citations(response_text, evidence_pack.citations)
                )
        except Exception as e:
            logger.error("Error reviewing clause %s: %s", title, e)
            
        return ContractClause(
            title=title, 
            content=content, 
            analysis="Không thể phân tích điều khoản này.",
            citations=[]
        )

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    @traceable(name="LLM Call")
    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call LLM via async client."""
        logger.info("Calling LLM (%s) …", settings.LLM_MODEL)

        response = await self._client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )

        text = response.choices[0].message.content or ""
        logger.info("LLM response: %d characters.", len(text))
        return text

    # ------------------------------------------------------------------
    # Citation / Evidence filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_citations(text: str, all_citations: list[Citation]) -> list[Citation]:
        """
        Extract cited indices (e.g., [1], [2]) from text and filter the citations list.
        Returns only the citations that were actually mentioned.
        """
        # Extract indices [X]
        cited_indices = set(re.findall(r"\[(\d+)\]", text))
        
        filtered = []
        # Sort to keep order consistent with numbering
        for idx_str in sorted(list(cited_indices), key=int):
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(all_citations):
                    filtered.append(all_citations[idx])
            except (ValueError, IndexError):
                continue
        
        return filtered

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_legal_answer(text: str, evidence_pack: EvidencePack) -> LegalAnswer:
        """
        Parse the LLM's structured response into a LegalAnswer.
        Extracts [TRẢ LỜI], [PHÂN TÍCH RỦI RO], [NGUỒN TRÍCH DẪN] sections.
        """
        answer_text = ""
        risk_text = ""
        citations_text = ""

        # Split by section headers
        sections = re.split(
            r"###?\s*\[?(TRẢ LỜI|PHÂN TÍCH RỦI RO|NGUỒN TRÍCH DẪN)\]?",
            text,
            flags=re.IGNORECASE,
        )

        current_section = None
        for part in sections:
            part_stripped = part.strip()
            upper = part_stripped.upper()

            if "TRẢ LỜI" in upper:
                current_section = "answer"
            elif "PHÂN TÍCH RỦI RO" in upper or "RỦI RO" in upper:
                current_section = "risk"
            elif "NGUỒN TRÍCH DẪN" in upper or "TRÍCH DẪN" in upper:
                current_section = "citations"
            elif current_section == "answer":
                answer_text += part
            elif current_section == "risk":
                risk_text += part
            elif current_section == "citations":
                citations_text += part

        # If parsing failed, use the entire text as the answer
        if not answer_text.strip():
            answer_text = text
        
        # Extract cited indices (e.g., [1], [2]) from the AI's response sections
        combined_text = f"{answer_text} {risk_text} {citations_text}"
        filtered_citations = LegalRAGGenerator._filter_citations(combined_text, evidence_pack.citations)

        return LegalAnswer(
            answer=answer_text.strip(),
            reasoning=risk_text.strip(),
            citations=filtered_citations,
            evidence_pack=evidence_pack,
        )

    @staticmethod
    def _parse_contract_review(
        text: str,
        evidence_pack: EvidencePack,
    ) -> ContractReviewResponse:
        """Parse contract review response into structured format."""
        summary = ""
        risks: list[ContractRiskItem] = []

        # Extract summary
        summary_match = re.search(
            r"###?\s*\[?TỔNG QUAN HỢP ĐỒNG\]?\s*\n(.*?)(?=###|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if summary_match:
            summary = summary_match.group(1).strip()

        # Extract individual risks
        risk_blocks = re.findall(
            r"####?\s*Rủi ro\s*\d+[:\.]?\s*(.*?)(?=####?\s*Rủi ro|\Z|###?\s*\[?NGUỒN)",
            text,
            re.DOTALL | re.IGNORECASE,
        )

        for block in risk_blocks:
            level_match = re.search(r"\*\*Mức độ\*\*[:\s]*(Cao|Trung bình|Thấp)", block, re.IGNORECASE)
            desc_match = re.search(r"\*\*Mô tả\*\*[:\s]*(.*?)(?=\*\*|$)", block, re.DOTALL)
            law_match = re.search(r"\*\*Căn cứ pháp lý\*\*[:\s]*(.*?)(?=\*\*|$)", block, re.DOTALL)
            rec_match = re.search(r"\*\*Khuyến nghị\*\*[:\s]*(.*?)(?=\*\*|$)", block, re.DOTALL)

            risks.append(
                ContractRiskItem(
                    risk_level=level_match.group(1) if level_match else "Trung bình",
                    description=desc_match.group(1).strip() if desc_match else block.strip()[:200],
                    relevant_law=law_match.group(1).strip() if law_match else "",
                    recommendation=rec_match.group(1).strip() if rec_match else "",
                )
            )

        return ContractReviewResponse(
            summary=summary,
            overall_risks=risks,
            citations=LegalRAGGenerator._filter_citations(text, evidence_pack.citations),
        )
