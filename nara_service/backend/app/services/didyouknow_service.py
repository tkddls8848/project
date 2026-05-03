"""
Did You Know 서비스 - 공공데이터 API 문서 기반 흥미로운 사실 생성
"""

import json
import uuid
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from collections import Counter
import httpx

from app.prompts.didyouknow import (
    get_api_introduction_prompt,
    get_provider_introduction_prompt,
    get_usage_tip_prompt,
)


class FactCategory(str, Enum):
    """Did You Know 콘텐츠 카테고리"""
    API_INTRODUCTION = "api_introduction"       # 특정 API 소개
    PROVIDER_INTRO = "provider_introduction"    # 제공 기관 소개
    USAGE_TIP = "usage_tip"                     # 데이터 활용 팁


class DidYouKnowService:
    """
    Did You Know 콘텐츠 생성 및 관리 서비스

    RAG 시스템과 LLM을 활용하여 흥미로운 사실을 자동 생성하고 캐싱
    """

    def __init__(self, rag_service, ollama_url: str = "http://localhost:11434"):
        """
        Args:
            rag_service: RAGService 인스턴스 (문서 접근용)
            ollama_url: Ollama 서버 URL
        """
        self.rag_service = rag_service

        # Ollama URL 설정
        if ollama_url and not ollama_url.startswith(("http://", "https://")):
            self.ollama_url = f"http://{ollama_url}"
        else:
            self.ollama_url = ollama_url

        # 캐시 디렉토리 설정
        backend_dir = Path(__file__).resolve().parent.parent.parent
        self.cache_dir = backend_dir / "storage" / "didyouknow"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "facts.json"

        print(f"[DidYouKnow] Service initialized")
        print(f"[DidYouKnow] Cache directory: {self.cache_dir}")
        print(f"[DidYouKnow] Ollama URL: {self.ollama_url}")

    def _generate_doc_url(self, api_id: str, api_type: str) -> str:
        """
        공공데이터포털 문서 URL 생성

        Args:
            api_id: API ID (예: "15000001")
            api_type: API 타입 (openapi_old, fileData, standard 등)

        Returns:
            문서 URL
        """
        # API 타입 매핑 (공공데이터포털 URL 형식으로 변환)
        type_mapping = {
            'openapi_old': 'openapi',
            'openapi_new': 'openapi',
            'openapi_link': 'openapi',
            'fileData': 'fileData',
            'standard': 'standard'
        }

        mapped_type = type_mapping.get(api_type, 'openapi')
        return f"https://www.data.go.kr/data/{api_id}/{mapped_type}.do"

    def generate_fact(self, category: FactCategory, llm_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        특정 카테고리의 사실 1개 생성

        Args:
            category: 생성할 카테고리
            llm_params: LLM 생성 파라미터 (temperature, top_p, max_tokens)

        Returns:
            생성된 사실 딕셔너리
        """
        try:
            # 원천 문서 선택
            source_docs = self._select_source_documents(category)
            if not source_docs:
                raise ValueError(f"No source documents found for category: {category}")

            # 랜덤으로 하나 선택
            source_doc = random.choice(source_docs)

            # API ID와 타입 추출
            api_id = source_doc.get('doc_id') or source_doc.get('api_id') or source_doc.get('id')
            api_type = source_doc.get('api_type', 'openapi_old')

            # API 타입 매핑 (공공데이터포털 URL 형식으로 변환)
            type_mapping = {
                'openapi_old': 'openapi',
                'openapi_new': 'openapi',
                'openapi_link': 'openapi',
                'fileData': 'fileData',
                'standard': 'standard'
            }
            url_type = type_mapping.get(api_type, 'openapi')

            # 프롬프트 생성
            prompt = self._get_prompt_for_category(category, source_doc, api_id or "", url_type)

            # LLM으로 콘텐츠 생성
            content = self._generate_with_llm(prompt, llm_params)

            # 콘텐츠 검증
            if not content or len(content) < 10:
                raise ValueError("Generated content is too short")

            # 최종 콘텐츠
            final_content = content.strip()

            # 문서 URL (metadata 저장용)
            doc_url = f"https://www.data.go.kr/data/{api_id}/{url_type}.do" if api_id else ""

            # 사실 객체 생성
            fact = {
                "id": str(uuid.uuid4()),
                "category": category.value,
                "content": final_content,
                "source_doc_id": api_id,
                "created_at": datetime.now().isoformat(),
                "metadata": {
                    "provider": source_doc.get('provider', ''),
                    "title": source_doc.get('title', ''),
                    "category": api_type,
                    "doc_url": doc_url
                }
            }

            print(f"[DidYouKnow] Generated fact for {category}: {final_content[:50]}...")
            return fact

        except Exception as e:
            print(f"[DidYouKnow] Error generating fact for {category}: {e}")
            raise

    def generate_batch(self, counts_per_category: Dict[FactCategory, int], llm_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        카테고리별로 여러 개 사실 생성

        Args:
            counts_per_category: {FactCategory.API_STATISTICS: 20, ...}
            llm_params: LLM 생성 파라미터 (temperature, top_p, max_tokens)

        Returns:
            생성된 사실 리스트
        """
        all_facts = []

        for category, count in counts_per_category.items():
            print(f"[DidYouKnow] Generating {count} facts for {category}...")

            for i in range(count):
                try:
                    fact = self.generate_fact(category, llm_params)
                    all_facts.append(fact)
                    print(f"[DidYouKnow] Progress: {i+1}/{count} for {category}")
                except Exception as e:
                    print(f"[DidYouKnow] Failed to generate fact {i+1}/{count} for {category}: {e}")
                    continue

        print(f"[DidYouKnow] Total generated: {len(all_facts)} facts")
        return all_facts

    def load_facts(self) -> List[Dict[str, Any]]:
        """
        캐시에서 사실 로드

        Returns:
            사실 리스트
        """
        if not self.cache_file.exists():
            print("[DidYouKnow] No cache file found, returning empty list")
            return []

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            facts = data.get('facts', [])
            print(f"[DidYouKnow] Loaded {len(facts)} facts from cache")
            return facts
        except Exception as e:
            print(f"[DidYouKnow] Error loading cache: {e}")
            return []

    def save_facts(self, facts: List[Dict[str, Any]]) -> None:
        """
        캐시에 사실 저장

        Args:
            facts: 저장할 사실 리스트
        """
        try:
            data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_count": len(facts),
                "facts": facts
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"[DidYouKnow] Saved {len(facts)} facts to cache")
        except Exception as e:
            print(f"[DidYouKnow] Error saving cache: {e}")
            raise

    def get_random_fact(self, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        랜덤 사실 1개 반환

        Args:
            category: 카테고리 필터 (선택)

        Returns:
            랜덤 사실 또는 None
        """
        facts = self.load_facts()

        if category:
            facts = [f for f in facts if f.get('category') == category]

        if not facts:
            return None

        return random.choice(facts)

    def _select_source_documents(self, category: FactCategory) -> List[Dict[str, Any]]:
        """
        카테고리에 맞는 원천 문서 선택

        Args:
            category: 카테고리

        Returns:
            선택된 문서 리스트
        """
        all_docs = self.rag_service.documents

        if category == FactCategory.API_INTRODUCTION:
            # 흥미로운 키워드가 있는 API 선택
            interesting_keywords = [
                "실시간", "위치", "예보", "가격", "정보", "조회",
                "날씨", "교통", "버스", "지하철", "주유소", "문화재"
            ]
            filtered = [
                doc for doc in all_docs
                if any(kw in doc.get('title', '') or kw in ' '.join(doc.get('keywords', []))
                       for kw in interesting_keywords)
            ]
            return filtered if filtered else all_docs[:100]

        elif category == FactCategory.PROVIDER_INTRO:
            # 제공 기관별 그룹핑
            providers = {}
            for doc in all_docs:
                provider = doc.get('provider', '제공기관 미상')
                if provider not in providers:
                    providers[provider] = []
                providers[provider].append(doc)

            # 3개 이상 API를 가진 기관만 선택
            provider_data = []
            for provider, docs in providers.items():
                if len(docs) >= 3:
                    # 기관 정보 구성
                    categories = [d.get('category', '') for d in docs if d.get('category')]
                    category_counts = Counter(categories)
                    main_categories = [cat for cat, _ in category_counts.most_common(3)]

                    sample_apis = [d.get('title', '') for d in docs[:3]]

                    # 대표 API 선택 (첫 번째 API의 정보 사용)
                    representative_doc = docs[0]
                    api_id = representative_doc.get('doc_id') or representative_doc.get('api_id') or representative_doc.get('id')
                    api_type = representative_doc.get('api_type', 'openapi_old')

                    provider_info = {
                        "name": provider,
                        "api_count": len(docs),
                        "main_categories": main_categories,
                        "sample_apis": sample_apis,
                        "doc_types": dict(Counter([d.get('api_type', 'unknown') for d in docs])),
                        "api_id": api_id,
                        "api_type": api_type
                    }
                    provider_data.append(provider_info)

            return provider_data

        elif category == FactCategory.USAGE_TIP:
            # REST API 타입만 선택 (활용 팁은 API 기반)
            filtered = [
                doc for doc in all_docs
                if doc.get('api_type') in ['openapi_link', 'openapi_new', 'openapi_old']
                and doc.get('total_endpoints', 0) > 0
            ]
            return filtered if filtered else all_docs[:100]

        return all_docs[:100]

    def _get_prompt_for_category(self, category: FactCategory, source_doc: Dict[str, Any], api_id: str = "", api_type: str = "") -> str:
        """
        카테고리에 맞는 프롬프트 생성

        Args:
            category: 카테고리
            source_doc: 원천 문서
            api_id: API ID (예: "15000001")
            api_type: API 타입 (예: "openapi", "fileData")

        Returns:
            프롬프트 문자열
        """
        if category == FactCategory.API_INTRODUCTION:
            return get_api_introduction_prompt(source_doc, api_id, api_type)
        elif category == FactCategory.PROVIDER_INTRO:
            return get_provider_introduction_prompt(source_doc)
        elif category == FactCategory.USAGE_TIP:
            return get_usage_tip_prompt(source_doc, api_id, api_type)
        else:
            raise ValueError(f"Unknown category: {category}")

    def _generate_with_llm(self, prompt: str, llm_params: Optional[Dict[str, Any]] = None) -> str:
        """
        Ollama LLM 호출하여 텍스트 생성

        Args:
            prompt: LLM 프롬프트
            llm_params: LLM 생성 파라미터 (temperature, top_p, max_tokens)

        Returns:
            생성된 텍스트
        """
        # 기본 파라미터 설정
        default_params = {
            "temperature": 0.8,
            "top_p": 0.9,
            "max_tokens": 100
        }

        # llm_params가 제공되면 기본값 덮어쓰기
        if llm_params:
            default_params.update(llm_params)

        try:
            url = f"{self.ollama_url}/api/generate"
            payload = {
                "model": "gemma3:4b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": default_params["temperature"],
                    "top_p": default_params["top_p"],
                    "max_tokens": default_params["max_tokens"]
                }
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()

                result = response.json()
                generated_text = result.get('response', '').strip()

                return generated_text

        except Exception as e:
            print(f"[DidYouKnow] LLM generation error: {e}")
            raise
