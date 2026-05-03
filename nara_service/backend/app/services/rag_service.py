import json
import os
from pathlib import Path
from typing import List, Dict, Any
import torch
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from openai import OpenAI
import httpx
import hashlib
from app.prompts import standard, insight
from app.core.llm_config import llm_settings
from app.services.rag_utils import (
    flatten_documents,
    create_search_text,
    format_context_text,
    format_relationships_text
)
# Neo4j service removed


class RAGService:
    def __init__(self, data_path: str = None, openai_api_key: str = None, ollama_url: str = "http://localhost:11434"):
        """
        RAG 서비스 초기화

        Args:
            data_path: JSON 데이터 파일 경로
            openai_api_key: OpenAI API 키
            ollama_url: Ollama 서버 URL (기본값: http://localhost:11434)
        """
        # 데이터 경로 설정
        if data_path is None:
            # storage/index.json 경로
            # Docker: /app/storage, Local: backend/storage
            backend_dir = Path(__file__).resolve().parent.parent.parent
            data_path = backend_dir / "storage" / "index.json"

        self.data_path = data_path
        self.openai_api_key = openai_api_key

        # 캐시 디렉토리 설정
        backend_dir = Path(__file__).resolve().parent.parent.parent
        self.cache_dir = backend_dir / "storage" / "cache" / "index_rag"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Ensure ollama_url has a protocol
        if ollama_url and not ollama_url.startswith(("http://", "https://")):
            self.ollama_url = f"http://{ollama_url}"
        else:
            self.ollama_url = ollama_url

        # GPU 가용성 확인
        self.use_gpu = torch.cuda.is_available()
        self.device = "cuda" if self.use_gpu else "cpu"

        if self.use_gpu:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"[indexRAG] GPU detected: {gpu_name} ({gpu_memory:.1f}GB)")
            print(f"[indexRAG] CUDA version: {torch.version.cuda}")
        else:
            print("[indexRAG] No GPU detected, using CPU")

        # 로컬 임베딩 모델 초기화 (sentence-transformers)
        # 한국어 지원 모델 사용
        print(f"[indexRAG] Loading embedding model on {self.device}...")
        self.embedding_model = SentenceTransformer('jhgan/ko-sroberta-multitask', device=self.device)
        print("[indexRAG] Embedding model loaded")

        # OpenAI 클라이언트 초기화
        if openai_api_key and openai_api_key.strip():
            try:
                self.openai_client = OpenAI(api_key=openai_api_key)
                print("[indexRAG] OpenAI client initialized")
            except Exception as e:
                print(f"[indexRAG] Warning: Failed to initialize OpenAI client: {e}")
                self.openai_client = None
        else:
            print("[indexRAG] No OpenAI API key provided, using basic search mode")
            self.openai_client = None

        # 데이터 및 인덱스
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = None
        self.index = None

        # 초기화
        self._load_data()
        self._build_index()

    def _load_data(self):
        """JSON 데이터 로드 - index.json의 중첩 구조 처리"""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 순수 함수를 사용하여 데이터 평탄화
            self.documents = flatten_documents(data)

            print(f"Loaded {len(self.documents)} documents from index.json")
        except FileNotFoundError:
            print(f"Warning: Data file not found at {self.data_path}")
            self.documents = []
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            self.documents = []

    def _get_data_fingerprint(self) -> str:
        """데이터 파일의 지문(fingerprint) 생성 - 수정 시간과 파일 크기 기반"""
        try:
            stat = os.stat(self.data_path)
            # 수정 시간과 파일 크기를 결합하여 고유 식별자 생성
            fingerprint = f"{stat.st_mtime}_{stat.st_size}"
            return fingerprint
        except Exception as e:
            print(f"[indexRAG] Failed to get data fingerprint: {e}")
            return ""

    def _is_cache_valid(self) -> bool:
        """캐시가 유효한지 확인"""
        metadata_path = self.cache_dir / "metadata.json"
        embeddings_path = self.cache_dir / "embeddings.npy"
        index_path = self.cache_dir / "index.faiss"

        # 캐시 파일이 모두 존재하는지 확인
        if not (metadata_path.exists() and embeddings_path.exists() and index_path.exists()):
            return False

        try:
            # 메타데이터 로드
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 데이터 파일의 현재 지문과 캐시된 지문 비교
            current_fingerprint = self._get_data_fingerprint()
            cached_fingerprint = metadata.get('data_fingerprint', '')

            if current_fingerprint != cached_fingerprint:
                print("[indexRAG] Data file has changed, cache invalid")
                return False

            # 문서 수 확인
            cached_doc_count = metadata.get('doc_count', 0)
            if cached_doc_count != len(self.documents):
                print("[indexRAG] Document count mismatch, cache invalid")
                return False

            return True
        except Exception as e:
            print(f"[indexRAG] Failed to validate cache: {e}")
            return False

    def _save_cache(self):
        """캐시 저장"""
        try:
            # 임베딩 저장
            embeddings_path = self.cache_dir / "embeddings.npy"
            np.save(embeddings_path, self.embeddings)

            # FAISS 인덱스 저장 (GPU 인덱스인 경우 CPU로 변환 후 저장)
            index_path = self.cache_dir / "index.faiss"
            if self.use_gpu and hasattr(self.index, 'index'):
                # GPU 인덱스를 CPU로 변환
                cpu_index = faiss.index_gpu_to_cpu(self.index)
                faiss.write_index(cpu_index, str(index_path))
            else:
                faiss.write_index(self.index, str(index_path))

            # 메타데이터 저장
            metadata = {
                'data_fingerprint': self._get_data_fingerprint(),
                'doc_count': len(self.documents),
                'embedding_dim': self.embeddings.shape[1],
                'use_gpu': self.use_gpu
            }
            metadata_path = self.cache_dir / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            print(f"[indexRAG] Cache saved to {self.cache_dir}")
        except Exception as e:
            print(f"[indexRAG] Failed to save cache: {e}")

    def _load_cache(self) -> bool:
        """캐시 로드, 성공하면 True 반환"""
        try:
            # 임베딩 로드
            embeddings_path = self.cache_dir / "embeddings.npy"
            self.embeddings = np.load(embeddings_path)

            # FAISS 인덱스 로드
            index_path = self.cache_dir / "index.faiss"
            cpu_index = faiss.read_index(str(index_path))

            # GPU 사용 가능하면 GPU로 이동
            if self.use_gpu:
                try:
                    res = faiss.StandardGpuResources()
                    self.index = faiss.index_cpu_to_gpu(res, 0, cpu_index)
                    print(f"[indexRAG] Loaded cache and moved to GPU ({self.index.ntotal} vectors)")
                except (AttributeError, RuntimeError) as e:
                    print(f"[indexRAG] GPU transfer failed ({e}), using CPU index")
                    self.index = cpu_index
                    print(f"[indexRAG] Loaded cache on CPU ({self.index.ntotal} vectors)")
            else:
                self.index = cpu_index
                print(f"[indexRAG] Loaded cache on CPU ({self.index.ntotal} vectors)")

            return True
        except Exception as e:
            print(f"[indexRAG] Failed to load cache: {e}")
            return False

    def _build_index(self):
        """FAISS 인덱스 구축 (GPU 사용 가능 시 GPU 기반) - 캐시 지원"""
        if not self.documents:
            print("[indexRAG] No documents to index")
            return

        # 캐시 확인 및 로드
        if self._is_cache_valid():
            print("[indexRAG] Valid cache found, loading from cache...")
            if self._load_cache():
                print("[indexRAG] Successfully loaded from cache")
                return

        # 캐시가 없거나 유효하지 않으면 새로 생성
        print("[indexRAG] Building new index...")

        # 각 문서를 텍스트로 변환 (검색 가능한 형태) - 순수 함수 사용
        texts = [create_search_text(doc) for doc in self.documents]

        # 임베딩 생성
        print("[indexRAG] Generating embeddings...")
        batch_size = 64 if self.use_gpu else 32  # GPU 시 배치 크기 증가
        self.embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True,
            batch_size=batch_size,
            normalize_embeddings=True  # 코사인 유사도를 위해 정규화
        )

        # FAISS 인덱스 생성 (Inner Product 사용 - 정규화된 벡터로 코사인 유사도 계산)
        dimension = self.embeddings.shape[1]

        # GPU 사용 가능 여부에 따라 인덱스 타입 선택
        if self.use_gpu:
            try:
                # GPU 리소스 확인
                res = faiss.StandardGpuResources()

                # CPU 인덱스 생성 후 GPU로 이동
                cpu_index = faiss.IndexFlatIP(dimension)

                # GPU 인덱스로 변환
                self.index = faiss.index_cpu_to_gpu(res, 0, cpu_index)
                self.index.add(self.embeddings)

                print(f"[indexRAG] Built GPU FAISS index with {self.index.ntotal} vectors")
            except (AttributeError, RuntimeError) as e:
                # faiss-gpu가 설치되지 않았거나 GPU 메모리 부족 시 CPU로 폴백
                print(f"[indexRAG] GPU index creation failed ({e}), falling back to CPU")
                self.index = faiss.IndexFlatIP(dimension)
                self.index.add(self.embeddings)
                print(f"[indexRAG] Built CPU FAISS index with {self.index.ntotal} vectors")
        else:
            # CPU 인덱스
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(self.embeddings)
            print(f"[indexRAG] Built CPU FAISS index with {self.index.ntotal} vectors")

        # 캐시 저장
        self._save_cache()

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        쿼리와 유사한 문서 검색 (FAISS 벡터 검색)

        Args:
            query: 검색 쿼리
            top_k: 반환할 상위 문서 개수

        Returns:
            유사한 문서 리스트
        """
        if not self.index or self.index.ntotal == 0:
            return []

        # 쿼리 임베딩 생성 (정규화하여 코사인 유사도 계산)
        query_embedding = self.embedding_model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        # FAISS 검색 (IndexFlatIP는 inner product를 반환 - 정규화된 벡터의 경우 코사인 유사도)
        scores, indices = self.index.search(query_embedding, top_k)

        # 결과 반환
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < len(self.documents):
                doc = self.documents[idx].copy()
                # Inner Product = 코사인 유사도 (-1 ~ 1 범위)
                # 0 ~ 1 범위로 정규화
                cosine_similarity = float(score)
                normalized_score = max(0.0, min(1.0, (cosine_similarity + 1.0) / 2.0))
                doc['similarity_score'] = normalized_score
                doc['cosine_similarity'] = cosine_similarity
                results.append(doc)

        return results

    def search_with_relations(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """
        쿼리와 유사한 문서 검색 + Neo4j 관계 기반 관련 문서 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 상위 문서 개수

        Returns:
            {
                "main_results": [...],      # FAISS 벡터 검색 결과
                "related_docs": [...],      # Neo4j 관계 기반 관련 문서
                "context_insights": [...]   # Neo4j가 제공하는 컨텍스트 텍스트
            }
        """
        # 1. FAISS 벡터 검색
        main_results = self.search(query, top_k)

        # 2. Neo4j 관계 기반 검색
        related_docs = []
        context_insights = []

        try:
            # 검색된 문서의 api_id 추출
            api_ids = [doc.get('id') for doc in main_results if doc.get('id')]

            # Neo4j removed - related docs feature disabled
            # if api_ids:
            #     context_insights = neo4j_service.get_related_context(api_ids)
            #     related_docs = self._extract_related_docs_from_context(context_insights)

        except Exception as e:
            print(f"관련 문서 검색 중 오류: {e}")

        return {
            "main_results": main_results,
            "related_docs": related_docs,
            "context_insights": context_insights
        }

    def _extract_related_docs_from_context(self, context_insights: List[str]) -> List[Dict[str, Any]]:
        """
        컨텍스트 텍스트에서 언급된 문서 제목을 추출하여 실제 문서 정보 반환
        (간단한 구현: 제목 매칭)

        Args:
            context_insights: Neo4j에서 반환한 컨텍스트 텍스트 리스트

        Returns:
            관련 문서 리스트
        """
        related_docs = []

        # 모든 문서 제목 목록
        all_titles = {doc.get('title'): doc for doc in self.documents if doc.get('title')}

        # 컨텍스트에서 언급된 제목 찾기
        for insight in context_insights:
            for title, doc in all_titles.items():
                if title in insight:
                    # 이미 추가되지 않았으면 추가
                    if not any(d.get('id') == doc.get('id') for d in related_docs):
                        related_docs.append(doc.copy())

        return related_docs

    def generate_response(self, query: str, context_docs: List[Dict[str, Any]], relationships: List[str] = [], llm_type: str = "openai", prompt_mode: str = "standard"):
        """
        LLM을 사용하여 쿼리에 대한 스트리밍 응답 생성 (Generator)

        Args:
            query: 사용자 질문
            context_docs: 검색된 관련 문서들
            relationships: 문서 간 관계 정보 리스트
            llm_type: 사용할 LLM 타입 ("openai" 또는 "ollama")
            prompt_mode: 프롬프트 모드 ("standard": 기본, "insight": 통찰/창의)

        Yields:
            생성된 응답 토큰
        """
        if llm_type == "ollama":
            yield from self._generate_with_ollama(query, context_docs, relationships, prompt_mode)
        else:
            yield from self._generate_with_openai(query, context_docs, relationships, prompt_mode)

    def _generate_with_openai(self, query: str, context_docs: List[Dict[str, Any]], relationships: List[str] = [], prompt_mode: str = "standard"):
        """OpenAI를 사용하여 스트리밍 응답 생성"""
        if not self.openai_client:
            # OpenAI 클라이언트가 없으면 간단한 응답 반환 (스트리밍 흉내)
            if not context_docs:
                yield "관련된 데이터를 찾을 수 없습니다."
                return

            # 검색 결과를 간단히 정리
            response_parts = [f"'{query}'에 대한 검색 결과입니다:\n"]
            for i, doc in enumerate(context_docs, 1):
                response_parts.append(
                    f"\n{i}. {doc.get('title', 'N/A')}\n"
                    f"   - 설명: {doc.get('description', 'N/A')}\n"
                    f"   - URL: {doc.get('url', 'N/A')}\n"
                    f"   - 타입: {doc.get('type', 'N/A')}"
                )
            full_response = ''.join(response_parts)
            # 한 번에 전송
            yield full_response
            return

        # OpenAI를 사용한 응답 생성
        # 컨텍스트 및 관계 정보 포맷팅 (순수 함수 사용)
        context_text = format_context_text(context_docs)
        relationships_text = format_relationships_text(relationships)

        if prompt_mode == "insight":
            system_prompt = insight.get_system_prompt()
            user_prompt = insight.get_user_prompt(context_text, relationships_text, query)
        else:
            system_prompt = standard.get_system_prompt()
            user_prompt = standard.get_user_prompt(context_text, query)

        try:
            # OpenAI API 호출 (스트리밍)
            stream = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            print(f"OpenAI API Error: {e}")
            yield f"응답 생성 중 오류가 발생했습니다. 검색된 관련 데이터: {len(context_docs)}개"

    def _generate_with_ollama(self, query: str, context_docs: List[Dict[str, Any]], relationships: List[str] = [], prompt_mode: str = "standard"):
        """Ollama를 사용하여 스트리밍 응답 생성"""
        # 컨텍스트 및 관계 정보 포맷팅 (순수 함수 사용)
        context_text = format_context_text(context_docs)
        relationships_text = format_relationships_text(relationships)

        if prompt_mode == "insight":
            prompt = insight.get_ollama_prompt(context_text, relationships_text, query)
        else:
            prompt = standard.get_ollama_prompt(context_text, query)

        try:
            # Ollama 스트리밍 API 호출
            with httpx.stream(
                "POST",
                f"{self.ollama_url}/api/generate",
                json={
                    "model": llm_settings.model,
                    "prompt": prompt,
                    "stream": True,  # 스트리밍 활성화
                    "options": llm_settings.options
                },
                timeout=120.0
            ) as response:
                response.raise_for_status()

                # 스트리밍 응답 yield
                for line in response.iter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue

        except httpx.ConnectError:
            yield "Ollama 서버에 연결할 수 없습니다."
        except Exception as e:
            yield f"오류: {str(e)}"