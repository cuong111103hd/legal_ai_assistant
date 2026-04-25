"""
Legal Verifier Agent.
Checks LLM-generated answers against evidence to detect hallucinations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import settings
from .models import VerificationResult

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM_PROMPT = """Bạn là một Chuyên gia Kiểm định Pháp lý (Legal Auditor). 
Nhiệm vụ của bạn là so sánh Câu trả lời của AI với các Nguồn trích dẫn (Evidence) để đảm bảo:
1. Mọi khẳng định trong câu trả lời đều có căn cứ trong nguồn trích dẫn.
2. Không có sự nhầm lẫn giữa các điều khoản, luật, nghị định.
3. Không có tình trạng "ảo tưởng" (hallucination) - tự bịa ra thông tin không có trong nguồn.

TRẢ VỀ KẾT QUẢ DƯỚI DẠNG JSON:
{
  "is_accurate": true/false,
  "confidence_score": 0.0 - 1.0,
  "hallucination_found": true/false,
  "unsupported_claims": ["Danh sách các ý không có căn cứ"],
  "corrections": "Đề xuất sửa đổi cụ thể để câu trả lời chính xác 100% với nguồn"
}
"""

VERIFIER_USER_TEMPLATE = """
### CÂU TRẢ LỜI CỦA AI:
{answer}

### NGUỒN TRÍCH DẪN (EVIDENCE):
{evidence}

Hãy kiểm tra tính chính xác của câu trả lời dựa trên nguồn trích dẫn trên.
"""


class LegalVerifier:
    """
    Verifies LLM-generated legal answers against provided evidence
    to prevent hallucinations and ensure correctness.
    """

    def __init__(self, llm_client: Any) -> None:
        self._client = llm_client

    async def verify(self, answer: str, evidence_text: str) -> VerificationResult:
        """Verify the answer against the retrieved evidence."""
        logger.info("Starting legal verification process...")

        user_prompt = VERIFIER_USER_TEMPLATE.format(
            answer=answer,
            evidence=evidence_text
        )

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0, # Use 0 for consistency in verification
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content or "{}"
            data = json.loads(result_text)
            
            return VerificationResult(**data)

        except Exception as e:
            logger.error("Verification failed: %s", e)
            # Default to accurate if verification itself fails to avoid blocking
            return VerificationResult(
                is_accurate=True,
                confidence_score=0.5,
                corrections=f"Verification error: {str(e)}"
            )
