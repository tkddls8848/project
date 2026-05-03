"""
Search RAG Service - 청크 기반 RAG 검색 서비스
"""
import json
import os
import numpy as np
import faiss
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer, CrossEncoder
import torch


class SearchRAGService:
    """
    청크 기반 RAG 검색 서비스 (FAISS 사용)
    """

    def __init__(self, storage_path: str = None):
        """
        초기화

        Args:
            storage_path: storage 디렉토리 경로
        """
        if storage_path is None:
            backend_dir = Path(__file__).resolve().parent.parent.parent
            storage_path = backend_dir / "storage"

        self.storage_path = Path(storage_path)
        self.chunks_dir = self.storage_path / "data" / "vector_chunks"
        self.list_data_dir = self.storage_path / "data"
        self.index_json_path = self.storage_path / "index.json"

        # 캐시 디렉토리 설정
        self.cache_dir = self.storage_path / "cache" / "search_rag"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # GPU 가용성 확인
        self.use_gpu = torch.cuda.is_available()
        self.device = "cuda" if self.use_gpu else "cpu"

        if self.use_gpu:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"[SearchRAG] GPU detected: {gpu_name} ({gpu_memory:.1f}GB)")
            print(f"[SearchRAG] CUDA version: {torch.version.cuda}")
        else:
            print("[SearchRAG] No GPU detected, using CPU")

        # 임베딩 모델 초기화
        print(f"[SearchRAG] Loading embedding model on {self.device}...")
        self.embedding_model = SentenceTransformer('jhgan/ko-sroberta-multitask', device=self.device)
        print("[SearchRAG] Embedding model loaded")

        # Reranking을 위한 Cross-Encoder 모델 초기화 (현재 비활성화 - 한국어 지원 불충분)
        # print(f"[SearchRAG] Loading cross-encoder model on {self.device}...")
        # self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512, device=self.device)
        # print("[SearchRAG] Cross-encoder model loaded")
        self.reranker = None

        # 데이터 및 인덱스
        self.chunks: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = None
        self.index = None

        # 초기화
        self._load_chunks()
        self._build_index()

    def _load_chunks(self):
        """청크 데이터 로드"""
        # 1. data/vector_chunks에서 JSONL 파일 로드 시도
        if self.chunks_dir.exists():
            jsonl_files = list(self.chunks_dir.glob("*.jsonl"))
            if jsonl_files:
                print(f"[SearchRAG] Loading chunks from {len(jsonl_files)} JSONL files...")
                for jsonl_file in jsonl_files:
                    self._load_chunks_from_jsonl(jsonl_file)

        # 2. chunks가 없으면 index.json에서 로드
        if not self.chunks and self.index_json_path.exists():
            print("[SearchRAG] No chunks found, loading from index.json...")
            self._load_chunks_from_index_json()

        print(f"[SearchRAG] Loaded {len(self.chunks)} chunks total")

    def _load_chunks_from_jsonl(self, jsonl_path: Path):
        """JSONL 파일에서 청크 로드"""
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        chunk_data = json.loads(line)
                        self.chunks.append(chunk_data)
        except Exception as e:
            print(f"[SearchRAG] Error loading {jsonl_path}: {e}")

    def _load_chunks_from_index_json(self):
        """index.json에서 문서를 청크로 변환하여 로드"""
        try:
            with open(self.index_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # index.json 구조 처리
            for category, apis in data.items():
                if isinstance(apis, dict):
                    for api_id, api_data in apis.items():
                        # 각 API를 하나의 청크로 변환
                        chunk = self._convert_api_to_chunk(api_id, api_data, category)
                        if chunk:
                            self.chunks.append(chunk)

        except Exception as e:
            print(f"[SearchRAG] Error loading index.json: {e}")

    def _convert_api_to_chunk(self, api_id: str, api_data: Dict, category: str) -> Optional[Dict]:
        """API 데이터를 청크 형식으로 변환"""
        try:
            # 메타데이터 추출
            metadata = api_data.get('metadata', {})
            title = metadata.get('title', '제목 없음')
            provider = metadata.get('provider', '제공기관 미상')
            description = metadata.get('description', '')

            # 청크 콘텐츠 생성
            content = f"# {title}\n\n"
            content += f"**제공기관**: {provider}\n"
            content += f"**카테고리**: {category}\n\n"

            if description:
                content += f"## 설명\n{description}\n\n"

            # 엔드포인트 정보 (있으면)
            endpoints = api_data.get('endpoints', [])
            if endpoints:
                content += f"## 엔드포인트\n"
                content += f"총 {len(endpoints)}개의 엔드포인트 제공\n\n"

            return {
                "chunk_id": f"{api_id}_main",
                "chunk_type": "document",
                "content": content,
                "metadata": {
                    "doc_id": api_id,
                    "api_id": api_id,
                    "title": title,
                    "provider": provider,
                    "category": category,
                    "doc_type": api_data.get('type', 'unknown'),
                    "keywords": metadata.get('keywords', [])
                }
            }
        except Exception as e:
            print(f"[SearchRAG] Error converting API {api_id}: {e}")
            return None

    def _get_data_fingerprint(self) -> str:
        """데이터 소스의 지문(fingerprint) 생성 - JSONL 파일들과 index.json의 수정 시간 기반"""
        try:
            fingerprints = []

            # JSONL 파일들의 fingerprint
            if self.chunks_dir.exists():
                jsonl_files = sorted(self.chunks_dir.glob("*.jsonl"))
                for jsonl_file in jsonl_files:
                    stat = os.stat(jsonl_file)
                    fingerprints.append(f"{jsonl_file.name}:{stat.st_mtime}:{stat.st_size}")

            # index.json의 fingerprint
            if self.index_json_path.exists():
                stat = os.stat(self.index_json_path)
                fingerprints.append(f"index.json:{stat.st_mtime}:{stat.st_size}")

            # 모든 fingerprint를 결합
            return "|".join(fingerprints)
        except Exception as e:
            print(f"[SearchRAG] Failed to get data fingerprint: {e}")
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

            # 데이터 소스의 현재 지문과 캐시된 지문 비교
            current_fingerprint = self._get_data_fingerprint()
            cached_fingerprint = metadata.get('data_fingerprint', '')

            if current_fingerprint != cached_fingerprint:
                print("[SearchRAG] Data sources have changed, cache invalid")
                return False

            # 청크 수 확인
            cached_chunk_count = metadata.get('chunk_count', 0)
            if cached_chunk_count != len(self.chunks):
                print("[SearchRAG] Chunk count mismatch, cache invalid")
                return False

            return True
        except Exception as e:
            print(f"[SearchRAG] Failed to validate cache: {e}")
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
                'chunk_count': len(self.chunks),
                'embedding_dim': self.embeddings.shape[1],
                'use_gpu': self.use_gpu
            }
            metadata_path = self.cache_dir / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            print(f"[SearchRAG] Cache saved to {self.cache_dir}")
        except Exception as e:
            print(f"[SearchRAG] Failed to save cache: {e}")

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
                    print(f"[SearchRAG] Loaded cache and moved to GPU ({self.index.ntotal} vectors)")
                except (AttributeError, RuntimeError) as e:
                    print(f"[SearchRAG] GPU transfer failed ({e}), using CPU index")
                    self.index = cpu_index
                    print(f"[SearchRAG] Loaded cache on CPU ({self.index.ntotal} vectors)")
            else:
                self.index = cpu_index
                print(f"[SearchRAG] Loaded cache on CPU ({self.index.ntotal} vectors)")

            return True
        except Exception as e:
            print(f"[SearchRAG] Failed to load cache: {e}")
            return False

    def _build_index(self):
        """FAISS 인덱스 구축 (GPU 사용 가능 시 GPU 기반) - 캐시 지원"""
        if not self.chunks:
            print("[SearchRAG] No chunks to index")
            return

        # 캐시 확인 및 로드
        if self._is_cache_valid():
            print("[SearchRAG] Valid cache found, loading from cache...")
            if self._load_cache():
                print("[SearchRAG] Successfully loaded from cache")
                return

        # 캐시가 없거나 유효하지 않으면 새로 생성
        print("[SearchRAG] Building new index...")

        # 청크 콘텐츠에서 텍스트 추출
        texts = [chunk.get('content', '') for chunk in self.chunks]

        # 임베딩 생성
        print("[SearchRAG] Generating embeddings...")
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

                print(f"[SearchRAG] Built GPU FAISS index with {self.index.ntotal} vectors")
            except (AttributeError, RuntimeError) as e:
                # faiss-gpu가 설치되지 않았거나 GPU 메모리 부족 시 CPU로 폴백
                print(f"[SearchRAG] GPU index creation failed ({e}), falling back to CPU")
                self.index = faiss.IndexFlatIP(dimension)
                self.index.add(self.embeddings)
                print(f"[SearchRAG] Built CPU FAISS index with {self.index.ntotal} vectors")
        else:
            # CPU 인덱스
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(self.embeddings)
            print(f"[SearchRAG] Built CPU FAISS index with {self.index.ntotal} vectors")

        # 캐시 저장
        self._save_cache()

    def search_chunks(
        self,
        query: str,
        top_k: int = 5,
        doc_type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        청크 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 상위 결과 개수
            doc_type_filter: 문서 타입 필터 (선택)

        Returns:
            검색 결과 리스트
        """
        if not self.index or self.index.ntotal == 0:
            return []

        # 쿼리 임베딩 생성 (정규화하여 코사인 유사도 계산)
        query_embedding = self.embedding_model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        # doc_type 필터가 있으면 더 많이 검색 후 필터링
        search_k = top_k * 3 if doc_type_filter else top_k

        # FAISS 검색 (IndexFlatIP는 inner product를 반환 - 정규화된 벡터의 경우 코사인 유사도)
        scores, indices = self.index.search(query_embedding, min(search_k, len(self.chunks)))

        # 결과 수집
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < len(self.chunks):
                chunk = self.chunks[idx].copy()

                # doc_type 필터링
                if doc_type_filter:
                    chunk_doc_type = chunk.get('metadata', {}).get('doc_type', '')
                    if chunk_doc_type != doc_type_filter:
                        continue

                # 유사도 점수 (Inner Product = 코사인 유사도, -1 ~ 1 범위)
                # 0 ~ 1 범위로 정규화
                cosine_similarity = float(score)
                normalized_score = max(0.0, min(1.0, (cosine_similarity + 1.0) / 2.0))

                chunk['score'] = normalized_score
                chunk['cosine_similarity'] = cosine_similarity
                results.append(chunk)

                # 필요한 개수만큼 수집
                if len(results) >= top_k:
                    break

        return results

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Cross-Encoder를 사용하여 검색 결과를 재순위화

        Args:
            query: 검색 쿼리
            results: 초기 검색 결과 리스트
            top_k: 반환할 상위 결과 개수

        Returns:
            재순위화된 결과 리스트
        """
        if not results:
            return []

        # Cross-Encoder 입력 쌍 생성 (query, document)
        pairs = []
        for result in results:
            content = result.get('content', '')
            # 긴 텍스트는 앞부분만 사용 (토큰 제한)
            truncated_content = content[:1000] if len(content) > 1000 else content
            pairs.append([query, truncated_content])

        # Cross-Encoder로 relevance score 계산
        rerank_scores = self.reranker.predict(pairs)

        # 결과에 rerank score 추가 (시그모이드 함수로 0~1 범위로 정규화)
        for i, result in enumerate(results):
            # 시그모이드 함수: 1 / (1 + e^(-x))
            raw_score = float(rerank_scores[i])
            normalized_score = 1.0 / (1.0 + np.exp(-raw_score))

            result['rerank_score'] = normalized_score
            result['raw_rerank_score'] = raw_score  # 원본 점수도 보존
            # 원래 점수도 보존
            result['initial_score'] = result.get('score', 0.0)

        # rerank_score 기준으로 정렬
        reranked_results = sorted(
            results,
            key=lambda x: x.get('rerank_score', 0.0),
            reverse=True
        )

        # 상위 top_k개만 반환
        return reranked_results[:top_k]

    def get_chunk_stats(self) -> Dict[str, Any]:
        """청크 통계 정보 반환"""
        # 문서 ID 추출 (중복 제거)
        doc_ids = set()
        doc_types = {}

        for chunk in self.chunks:
            doc_id = chunk.get('metadata', {}).get('doc_id')
            if doc_id:
                doc_ids.add(doc_id)

            doc_type = chunk.get('metadata', {}).get('doc_type', 'unknown')
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

        return {
            "total_chunks": len(self.chunks),
            "total_documents": len(doc_ids),
            "index_size": self.index.ntotal if self.index else 0,
            "doc_types": doc_types,
            "storage_path": str(self.storage_path)
        }
