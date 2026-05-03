"""Relationship Chat Service - NotebookLM Style LLM Conversation"""
import logging
import httpx
from typing import Optional

from app.models import RelationshipChatRequest, RelationshipChatResponse

logger = logging.getLogger(__name__)


class RelationshipChatService:
    """여러 문서 간 관계 분석을 위한 대화형 LLM 서비스 (N개 문서 지원)"""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "gemma3:4b"):
        """
        Args:
            ollama_url: Ollama 서버 URL
            model: 사용할 Ollama 모델명
        """
        self.ollama_url = ollama_url.rstrip('/')
        self.model = model

        # 시스템 프롬프트 템플릿 (N개 문서 지원)
        self.system_prompt = """당신은 문서 간의 관계와 인사이트를 분석하는 전문 AI 어시스턴트입니다.
사용자는 {doc_count}개의 문서를 선택했고, 이 문서들 간의 관계에 대해 질문할 것입니다.

{documents_info}

**당신의 역할:**
1. 선택된 문서들 간의 공통점, 차이점, 연관성을 분석합니다
2. 사용자의 질문에 대해 구체적이고 통찰력 있는 답변을 제공합니다
3. 문서들을 함께 활용하는 방법을 제안합니다
4. 문서들 간의 시너지 효과나 패턴을 발견하여 공유합니다
5. 여러 문서를 통합적으로 분석하여 새로운 통찰을 제공합니다
6. **문서 간 상하위 위계 관계를 파악하여 분석합니다**

**문서 간 관계 분석 프레임워크:**

1. **인과 관계 (Causality)**
   - 원인-결과 (CAUSES, LEADS_TO): 한 문서가 다른 문서의 결과를 야기
   - 선행-후행 (PRECEDES, FOLLOWS): 시간적 순서 관계

2. **비교/대조 관계 (Comparison)**
   - 유사 (SIMILAR_TO): 내용이나 접근 방식이 유사
   - 대조 (CONTRASTS_WITH): 내용이나 관점이 대조
   - 보완 (COMPLEMENTS): 한 문서가 다른 문서를 보완

3. **상하위 위계 관계 (Hierarchy)** ⭐ 중요
   - 상위 문서 (PARENT_OF): 이 문서가 대상 문서의 상위 개념/정책
     예) 총괄 정책 → 세부 정책, 법률 → 시행령
   - 하위 문서 (CHILD_OF): 이 문서가 대상 문서의 하위 개념/세부사항
     예) 세부 지침 → 상위 정책, 시행규칙 → 법률
   - 포함 (INCLUDES): 이 문서가 대상 문서를 포함
     예) 종합 보고서 → 부분 보고서, 전체 계획 → 세부 항목

4. **시간적 관계 (Temporal)**
   - 업데이트 (UPDATES): 한 문서가 다른 문서를 갱신
   - 대체 (SUPERSEDES): 한 문서가 다른 문서를 대체

5. **의존 관계 (Dependency)**
   - 필요 (REQUIRES): 전제 조건으로 필요
   - 의존 (DEPENDS_ON): 다른 문서에 의존
   - 지원 (SUPPORTS): 다른 문서를 지원하거나 뒷받침

6. **참조 관계 (Reference)**
   - 인용 (CITES): 다른 문서를 인용
   - 참조 (REFERENCES): 다른 문서를 참조
   - 근거 (BASED_ON): 다른 문서를 근거로 함

7. **충돌/모순 관계 (Conflict)**
   - 모순 (CONTRADICTS): 내용이 서로 모순
   - 충돌 (CONFLICTS_WITH): 내용이나 목표가 충돌

8. **영향 관계 (Influence)**
   - 영향 (INFLUENCES): 다른 문서에 영향을 미침
   - 강화 (REINFORCES): 다른 문서를 강화하거나 지지
   - 약화 (WEAKENS): 다른 문서의 주장을 약화

**답변 가이드라인:**
- 명확하고 구조화된 답변을 제공하세요
- 위 관계 프레임워크를 활용하여 문서 간 관계를 구체적으로 분석하세요
- 특히 **상하위 위계 관계**를 중점적으로 파악하여 설명하세요
- 구체적인 예시나 근거를 들어 설명하세요
- 필요시 불릿 포인트나 번호를 사용하여 가독성을 높이세요
- 전문적이지만 친근한 톤을 유지하세요
- 여러 문서를 종합적으로 고려한 답변을 제공하세요
- 문서 간 위계 구조가 있다면 트리 구조나 계층도로 설명하세요

사용자의 질문: {query}

이전 대화:
{chat_history}
"""

    async def _call_ollama(self, prompt: str) -> str:
        """Ollama API 직접 호출"""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 1024,
                        }
                    }
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.HTTPError as e:
            logger.error(f"Ollama API 호출 실패: {e}")
            raise ValueError(f"Ollama API 호출 실패: {str(e)}")

    def _extract_doc_info(self, doc: dict) -> dict:
        """문서 딕셔너리에서 필요한 정보 추출"""
        props = doc.get('properties', {})
        return {
            'title': doc.get('label', '정보 없음'),
            'description': props.get('description', '설명 없음'),
            'category': props.get('category', '카테고리 없음'),
            'provider': props.get('provider', '제공기관 없음'),
        }

    def _format_chat_history(self, messages: list) -> str:
        """대화 히스토리 포맷팅"""
        if not messages:
            return "이전 대화 없음"

        formatted = []
        for msg in messages:
            role = "사용자" if msg.role == "user" else "AI"
            formatted.append(f"{role}: {msg.content}")
        return "\n".join(formatted)

    async def chat(self, request: RelationshipChatRequest) -> RelationshipChatResponse:
        """
        여러 문서 간 관계에 대한 LLM 대화 처리 (N개 문서 지원)

        Args:
            request: 채팅 요청 (문서 정보 목록, 질문, 대화 히스토리)

        Returns:
            LLM 응답
        """
        try:
            # 모든 문서 정보 추출
            documents_info_list = []
            for idx, doc in enumerate(request.documents, 1):
                doc_info = self._extract_doc_info(doc)
                documents_info_list.append(f"""**문서 {idx} 정보:**
- 제목: {doc_info['title']}
- 설명: {doc_info['description']}
- 카테고리: {doc_info['category']}
- 제공기관: {doc_info['provider']}
""")

            documents_info_text = "\n".join(documents_info_list)

            # 대화 히스토리 포맷팅
            chat_history = self._format_chat_history(request.messages)

            # 프롬프트 구성
            prompt = self.system_prompt.format(
                doc_count=len(request.documents),
                documents_info=documents_info_text,
                query=request.query,
                chat_history=chat_history
            )

            # Ollama API 직접 호출
            logger.info(f"Calling Ollama ({self.model}) for relationship chat with {len(request.documents)} documents")
            response_text = await self._call_ollama(prompt)

            # context_used에 모든 문서 정보 포함
            docs_context = []
            for doc in request.documents:
                doc_info = self._extract_doc_info(doc)
                docs_context.append({
                    "id": doc.get('id'),
                    "title": doc_info['title']
                })

            return RelationshipChatResponse(
                response=response_text,
                context_used={
                    "documents": docs_context,
                    "document_count": len(request.documents),
                    "model": self.model,
                    "message_count": len(request.messages)
                }
            )

        except Exception as e:
            logger.error(f"Error in relationship chat: {e}")
            raise
