"""
Did You Know 서비스 - 공공데이터 API 흥미로운 사실 생성
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
    API_INTRODUCTION = "api_introduction"
    PROVIDER_INTRO = "provider_introduction"
    USAGE_TIP = "usage_tip"


class DidYouKnowService:
    """
    Did You Know 콘텐츠 생성 및 관리 서비스
    """

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        """
        Args:
            ollama_url: Ollama 서버 URL
        """
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

        # API 문서 로드 (index.json에서)
        self.documents = self._load_documents_from_index()

        print(f"[DidYouKnow] Service initialized")
        print(f"[DidYouKnow] Cache directory: {self.cache_dir}")
        print(f"[DidYouKnow] Ollama URL: {self.ollama_url}")
        print(f"[DidYouKnow] Loaded documents: {len(self.documents)}")

    def _load_documents_from_index(self) -> List[Dict[str, Any]]:
        """index.json에서 API 문서 데이터 로드. 파일이 없으면 빈 리스트 반환."""
        index_file = self.cache_dir.parent / "index.json"

        if not index_file.exists():
            print(f"[DidYouKnow] ERROR: index.json not found at {index_file}")
            print("[DidYouKnow] API 문서를 로드할 수 없습니다. storage/index.json 파일을 추가해주세요.")
            return []

        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)

            documents = []

            # fileData, openapi_old, openapi_new 등 각 타입별 처리
            for api_type, apis in index_data.items():
                for api_id, api_info in apis.items():
                    # keywords를 리스트로 변환
                    keywords_str = api_info.get('keyword', '')
                    keywords = [k.strip() for k in keywords_str.split(',')] if keywords_str else []

                    doc = {
                        "doc_id": api_id,
                        "api_id": api_id,
                        "api_type": api_type,
                        "title": api_info.get('title', ''),
                        "provider": api_info.get('org', ''),
                        "description": api_info.get('description', ''),
                        "keywords": keywords,
                        "category": api_info.get('type', ''),
                        "total_endpoints": 0  # index.json에는 이 정보가 없음
                    }
                    documents.append(doc)

            print(f"[DidYouKnow] Loaded {len(documents)} documents from index.json")

            # 샘플 문서 정보 출력
            if documents:
                sample = documents[0]
                print(f"[DidYouKnow] Sample document:")
                print(f"  - Title: {sample.get('title', '')[:50]}")
                print(f"  - Keywords: {sample.get('keywords', [])[:3]}")
                print(f"  - Provider: {sample.get('provider', '')}")

            return documents

        except Exception as e:
            print(f"[DidYouKnow] Error loading index.json: {e}")
            print("[DidYouKnow] API 문서를 로드할 수 없습니다. storage/index.json 파일을 확인해주세요.")
            return []

    def generate_fact(self, category: FactCategory, llm_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        특정 카테고리의 사실 1개 생성

        Args:
            category: 생성할 카테고리
            llm_params: LLM 생성 파라미터

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

            # API 타입 매핑
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

            # 문서 URL
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
        """카테고리별로 여러 개 사실 생성"""
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
        """캐시에서 사실 로드"""
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
        """캐시에 사실 저장"""
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
        """랜덤 사실 1개 반환"""
        facts = self.load_facts()

        if category:
            facts = [f for f in facts if f.get('category') == category]

        if not facts:
            return None

        return random.choice(facts)

    def _select_source_documents(self, category: FactCategory) -> List[Dict[str, Any]]:
        """카테고리에 맞는 원천 문서 선택"""
        all_docs = self.documents

        if category == FactCategory.API_INTRODUCTION:
            return all_docs

        elif category == FactCategory.PROVIDER_INTRO:
            # 제공 기관별 그룹핑
            providers = {}
            for doc in all_docs:
                provider = doc.get('provider', '제공기관 미상')
                if provider not in providers:
                    providers[provider] = []
                providers[provider].append(doc)

            # 제공 기관 정보 구성
            provider_data = []
            for provider, docs in providers.items():
                representative_doc = docs[0]
                api_id = representative_doc.get('doc_id') or representative_doc.get('api_id')
                api_type = representative_doc.get('api_type', 'openapi_old')

                provider_info = {
                    "name": provider,
                    "api_count": len(docs),
                    "main_categories": list(set([d.get('category', '') for d in docs if d.get('category')])),
                    "sample_apis": [d.get('title', '') for d in docs[:3]],
                    "doc_types": dict(Counter([d.get('api_type', 'unknown') for d in docs])),
                    "api_id": api_id,
                    "api_type": api_type
                }
                provider_data.append(provider_info)

            return provider_data

        elif category == FactCategory.USAGE_TIP:
            # REST API 타입만 선택
            filtered = [
                doc for doc in all_docs
                if doc.get('api_type') in ['openapi_link', 'openapi_new', 'openapi_old']
                and doc.get('total_endpoints', 0) > 0
            ]
            return filtered if filtered else all_docs

        return all_docs

    def _get_prompt_for_category(self, category: FactCategory, source_doc: Dict[str, Any], api_id: str = "", api_type: str = "") -> str:
        """카테고리에 맞는 프롬프트 생성"""
        if category == FactCategory.API_INTRODUCTION:
            return get_api_introduction_prompt(source_doc, api_id, api_type)
        elif category == FactCategory.PROVIDER_INTRO:
            return get_provider_introduction_prompt(source_doc)
        elif category == FactCategory.USAGE_TIP:
            return get_usage_tip_prompt(source_doc, api_id, api_type)
        else:
            raise ValueError(f"Unknown category: {category}")

    def _generate_with_llm(self, prompt: str, llm_params: Optional[Dict[str, Any]] = None) -> str:
        """Ollama LLM 호출하여 텍스트 생성"""
        default_params = {
            "temperature": 0.8,
            "top_p": 0.9,
            "max_tokens": 150
        }

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
                    "num_predict": default_params["max_tokens"]
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
