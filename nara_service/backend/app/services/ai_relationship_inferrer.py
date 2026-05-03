"""
AI 기반 관계 추론 서비스

LLM을 활용하여 문서 간 잠재적 관계를 자동으로 추론
"""

import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
import json

logger = logging.getLogger(__name__)


class AIRelationshipInferrer:
    """LLM 기반 관계 추론 엔진"""

    def __init__(self, openai_api_key: Optional[str] = None, ollama_url: str = "http://localhost:11434"):
        """
        Args:
            openai_api_key: OpenAI API 키 (선택적)
            ollama_url: Ollama 서버 URL
        """
        self.openai_client = None
        self.ollama_url = ollama_url
        self.use_openai = False

        if openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=openai_api_key)
                self.use_openai = True
                logger.info("✅ AI Relationship Inferrer initialized with OpenAI")
            except Exception as e:
                logger.warning(f"OpenAI initialization failed: {e}, will use Ollama")

        if not self.use_openai:
            logger.info("✅ AI Relationship Inferrer initialized with Ollama")

    def infer_relationships(
        self,
        documents: List[Dict[str, Any]],
        context_limit: int = 500
    ) -> Dict[str, Any]:
        """
        여러 문서 간 잠재적 관계 추론

        Args:
            documents: 분석할 문서 목록 [{"id": "...", "title": "...", "description": "..."}, ...]
            context_limit: 문서 설명의 최대 문자 수

        Returns:
            {
                "inferred_relationships": [
                    {
                        "source_id": "doc_1",
                        "target_id": "doc_2",
                        "suggested_type": "보완" | "유사" | "인과" | "참고",
                        "reason": "추론 이유",
                        "confidence": 0.0-1.0,
                        "evidence": "구체적 근거"
                    }
                ],
                "total": 추론된 관계 개수
            }
        """
        if len(documents) < 2:
            logger.warning("At least 2 documents required for relationship inference")
            return {"inferred_relationships": [], "total": 0}

        logger.info(f"Inferring relationships for {len(documents)} documents...")

        # 문서 컨텍스트 준비
        doc_summaries = []
        for doc in documents[:10]:  # 최대 10개까지만 분석 (API 비용/시간 절감)
            doc_id = doc.get("id", "")
            title = doc.get("title", "")
            description = doc.get("description", "")[:context_limit]

            doc_summaries.append({
                "id": doc_id,
                "title": title,
                "description": description
            })

        # LLM 프롬프트 생성
        prompt = self._create_inference_prompt(doc_summaries)

        # LLM 호출
        try:
            if self.use_openai:
                response_text = self._call_openai(prompt)
            else:
                response_text = self._call_ollama(prompt)

            # 응답 파싱
            inferred = self._parse_llm_response(response_text)

            logger.info(f"Inferred {len(inferred)} relationships")
            return {
                "inferred_relationships": inferred,
                "total": len(inferred)
            }

        except Exception as e:
            logger.error(f"Error inferring relationships: {e}")
            return {"inferred_relationships": [], "total": 0}

    def _create_inference_prompt(self, doc_summaries: List[Dict[str, str]]) -> str:
        """
        LLM 프롬프트 생성

        Args:
            doc_summaries: 문서 요약 목록

        Returns:
            LLM 프롬프트 문자열
        """
        # 문서 목록을 텍스트로 변환
        docs_text = ""
        for i, doc in enumerate(doc_summaries, 1):
            docs_text += f"\n**문서 {i}** (ID: {doc['id']})\n"
            docs_text += f"제목: {doc['title']}\n"
            docs_text += f"설명: {doc['description']}\n"

        prompt = f"""
당신은 공공데이터 API 문서들 간의 관계를 분석하는 전문가입니다.
주어진 문서들을 분석하여 의미 있는 관계를 추론하세요.

# 문서 목록
{docs_text}

# 관계 타입
- **보완**: 두 데이터를 결합하면 더 완전한 분석이 가능
- **유사**: 같은 주제나 분야를 다루는 유사한 데이터
- **인과**: 한 데이터가 다른 데이터의 원인이나 결과
- **참고**: 관련성은 있지만 직접적 연관은 약함
- **시계열**: 시간 흐름에 따른 데이터 (이전/이후 관계)

# 작업
1. 모든 문서 쌍을 검토하여 의미 있는 관계 찾기
2. 각 관계에 대해 타입, 이유, 신뢰도, 근거 제공
3. 신뢰도가 0.5 이상인 관계만 반환

# 응답 형식 (JSON)
```json
{{
  "relationships": [
    {{
      "source_id": "문서 ID",
      "target_id": "문서 ID",
      "suggested_type": "보완|유사|인과|참고|시계열",
      "reason": "관계 추론 이유 (한 문장)",
      "confidence": 0.0-1.0,
      "evidence": "구체적 근거 (키워드, 패턴 등)"
    }}
  ]
}}
```

응답은 **반드시 JSON 형식**으로만 작성하세요. 다른 텍스트는 포함하지 마세요.
"""
        return prompt

    def _call_openai(self, prompt: str) -> str:
        """
        OpenAI API 호출

        Args:
            prompt: LLM 프롬프트

        Returns:
            LLM 응답 텍스트
        """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # 비용 효율적인 모델
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing relationships between documents."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # 일관성 있는 응답
                max_tokens=2000
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    def _call_ollama(self, prompt: str) -> str:
        """
        Ollama API 호출

        Args:
            prompt: LLM 프롬프트

        Returns:
            LLM 응답 텍스트
        """
        import httpx

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.2:latest",
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 2000
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")

        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise

    def _parse_llm_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        LLM 응답 파싱

        Args:
            response_text: LLM 응답 텍스트

        Returns:
            추론된 관계 목록
        """
        try:
            # JSON 블록 추출 (```json ... ``` 형식)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                # JSON 블록이 없으면 전체 응답을 JSON으로 파싱 시도
                json_text = response_text.strip()

            # JSON 파싱
            data = json.loads(json_text)

            # 관계 목록 추출
            relationships = data.get("relationships", [])

            # 검증 및 필터링
            valid_relationships = []
            for rel in relationships:
                # 필수 필드 확인
                if all(k in rel for k in ["source_id", "target_id", "suggested_type", "reason", "confidence"]):
                    # 신뢰도 필터링
                    confidence = rel.get("confidence", 0.0)
                    if confidence >= 0.5:
                        valid_relationships.append({
                            "source_id": str(rel["source_id"]),
                            "target_id": str(rel["target_id"]),
                            "suggested_type": rel["suggested_type"],
                            "reason": rel["reason"],
                            "confidence": float(confidence),
                            "evidence": rel.get("evidence", "")
                        })

            return valid_relationships

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"Raw response: {response_text[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return []

    def analyze_document_pair(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        두 문서 간 관계 추론 (단일 쌍)

        Args:
            doc1: 첫 번째 문서
            doc2: 두 번째 문서

        Returns:
            추론된 관계 (없으면 None)
        """
        result = self.infer_relationships([doc1, doc2], context_limit=1000)

        if result["total"] > 0:
            return result["inferred_relationships"][0]
        return None
