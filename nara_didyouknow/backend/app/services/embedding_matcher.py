#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
임베딩 기반 API 매칭 서비스

Sentence Transformers를 사용하여 기사와 API 문서의 의미적 유사도를 계산합니다.
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class EmbeddingMatcher:
    def __init__(
        self,
        embeddings_dir: str,
        model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'
    ):
        """
        Args:
            embeddings_dir: 임베딩 파일이 저장된 디렉토리
            model_name: Sentence Transformers 모델 이름
        """
        self.embeddings_dir = Path(embeddings_dir)
        self.model_name = model_name

        # 모델 로드
        print(f"[EmbeddingMatcher] Loading model: {model_name}...")
        self.model = SentenceTransformer(model_name)

        # API 임베딩 및 매핑 로드
        self.api_embeddings = None
        self.api_mapping = None
        self.load_api_embeddings()

    def load_api_embeddings(self):
        """
        사전에 생성된 API 임베딩과 매핑 로드
        """
        embeddings_file = self.embeddings_dir / 'api_embeddings.npy'
        mapping_file = self.embeddings_dir / 'api_embeddings_mapping.json'

        if not embeddings_file.exists():
            raise FileNotFoundError(
                f"API embeddings not found: {embeddings_file}\n"
                f"Please run 'python scripts/generate_api_embeddings.py' first."
            )

        # 임베딩 로드
        print(f"[EmbeddingMatcher] Loading embeddings from: {embeddings_file}")
        self.api_embeddings = np.load(embeddings_file)

        # 매핑 로드
        with open(mapping_file, 'r', encoding='utf-8') as f:
            self.api_mapping = json.load(f)

        print(f"[EmbeddingMatcher] Loaded {len(self.api_mapping)} API embeddings")
        print(f"[EmbeddingMatcher] Embedding shape: {self.api_embeddings.shape}")

    def embed_article(self, article: Dict) -> np.ndarray:
        """
        기사를 임베딩으로 변환 (topic + summary 사용)

        Args:
            article: {"topic": "...", "summary": "...", "keywords": [...]}

        Returns:
            임베딩 벡터 (shape: [embedding_dim])
        """
        # topic + summary 결합
        topic = article.get('topic', '')
        summary = article.get('summary', '')
        text = f"{topic}. {summary}"

        # 임베딩 생성
        embedding = self.model.encode([text], convert_to_numpy=True)[0]

        return embedding

    def find_similar_apis(
        self,
        article: Dict,
        top_k: int = 30,
        min_similarity: float = 0.0
    ) -> List[Tuple[str, str, float]]:
        """
        기사와 유사한 API 찾기 (임베딩 기반)

        Args:
            article: {"topic": "...", "summary": "...", "keywords": [...]}
            top_k: 반환할 API 개수
            min_similarity: 최소 유사도 (0.0 ~ 1.0)

        Returns:
            [(api_id, api_type, similarity), ...] - 유사도 순 정렬
        """
        # 기사 임베딩
        article_embedding = self.embed_article(article)

        # 코사인 유사도 계산
        similarities = cosine_similarity(
            [article_embedding],
            self.api_embeddings
        )[0]

        # 상위 K개 선택
        top_indices = similarities.argsort()[::-1][:top_k]

        results = []
        for idx in top_indices:
            similarity = float(similarities[idx])

            # 최소 유사도 필터링
            if similarity < min_similarity:
                continue

            api_info = self.api_mapping[idx]
            results.append((
                api_info['api_id'],
                api_info['api_type'],
                similarity
            ))

        return results

    def find_similar_apis_with_details(
        self,
        article: Dict,
        documents: List[Dict],
        top_k: int = 30,
        min_similarity: float = 0.0
    ) -> List[Dict]:
        """
        기사와 유사한 API 찾기 (상세 정보 포함)

        Args:
            article: {"topic": "...", "summary": "...", "keywords": [...]}
            documents: 전체 API 문서 리스트 (index.json에서 로드)
            top_k: 반환할 API 개수
            min_similarity: 최소 유사도

        Returns:
            API 문서 리스트 (유사도 점수 포함)
        """
        # API ID 매핑 생성
        api_id_to_doc = {}
        for doc in documents:
            api_id = doc.get('api_id') or doc.get('doc_id')
            if api_id:
                api_id_to_doc[api_id] = doc

        # 유사한 API 찾기
        similar_apis = self.find_similar_apis(article, top_k, min_similarity)

        # 상세 정보 추가
        results = []
        for api_id, api_type, similarity in similar_apis:
            if api_id in api_id_to_doc:
                doc = api_id_to_doc[api_id].copy()
                doc['similarity_score'] = similarity
                doc['match_method'] = 'embedding'
                results.append(doc)

        return results


class KeywordSimilarityMatcher:
    """
    기사 키워드 ↔ API 키워드 의미적 유사도 매칭

    기사의 키워드 목록과 각 API의 키워드 목록을 각각 하나의 텍스트로 결합하여
    임베딩한 후, 코사인 유사도로 비교합니다.
    API 키워드 임베딩은 첫 실행 시 생성되어 disk에 캐시됩니다.
    """

    def __init__(
        self,
        embeddings_dir: str,
        model: SentenceTransformer,
        documents: List[Dict]
    ):
        """
        Args:
            embeddings_dir: 임베딩 캐시 디렉토리
            model: 이미 로드된 SentenceTransformer 모델 (EmbeddingMatcher와 공유)
            documents: self.documents 리스트 (index.json 로드 결과, 순서 기준)
        """
        self.embeddings_dir = Path(embeddings_dir)
        self.model = model
        self.documents = documents
        self.api_keyword_embeddings: np.ndarray = self._load_or_generate()

    # ── 캐시 로드 / 생성 ──────────────────────────────────────────────

    def _load_or_generate(self) -> np.ndarray:
        emb_file = self.embeddings_dir / 'api_keyword_embeddings.npy'
        meta_file = self.embeddings_dir / 'api_keyword_embeddings_meta.json'

        if emb_file.exists() and meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                if meta.get('num_documents') == len(self.documents):
                    print(f"[KeywordMatcher] Cached keyword embeddings loaded ({len(self.documents)} APIs)")
                    return np.load(emb_file)
                else:
                    print(f"[KeywordMatcher] Cache stale (cached={meta.get('num_documents')}, current={len(self.documents)}), regenerating…")
            except Exception as e:
                print(f"[KeywordMatcher] Cache read error: {e}, regenerating…")

        return self._generate_and_cache(emb_file, meta_file)

    def _generate_and_cache(self, emb_file: Path, meta_file: Path) -> np.ndarray:
        import time
        print(f"[KeywordMatcher] Generating keyword embeddings for {len(self.documents)} APIs…")
        start = time.time()

        # API당 키워드 텍스트 — 키워드가 없으면 제목을 대체로 사용
        keyword_texts: List[str] = []
        for doc in self.documents:
            kws = doc.get('keywords', [])
            keyword_texts.append(', '.join(kws) if kws else doc.get('title', ''))

        embeddings = self.model.encode(
            keyword_texts,
            batch_size=256,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        elapsed = time.time() - start
        print(f"[KeywordMatcher] Generation complete: {elapsed:.1f}s, shape={embeddings.shape}")

        # 캐시 저장
        np.save(emb_file, embeddings)
        with open(meta_file, 'w', encoding='utf-8') as f:
            import time as _t
            json.dump({
                'num_documents': len(self.documents),
                'generated_at': _t.strftime('%Y-%m-%d %H:%M:%S'),
            }, f, indent=2)
        print(f"[KeywordMatcher] Cached to {emb_file}")

        return embeddings

    # ── 점수 계산 ────────────────────────────────────────────────────

    def compute_scores(self, article_keywords: List[str]) -> np.ndarray:
        """
        기사 키워드와 전체 API 키워드 사이의 유사도를 한 번에 계산합니다.

        Args:
            article_keywords: 기사의 키워드 목록 (예: ["교통", "자동차", "운전"])

        Returns:
            numpy array (shape: [num_apis]) — 각 API의 유사도 점수 (0 ~ 100)
            self.documents와 동일한 순서
        """
        text = ', '.join(article_keywords)
        article_emb = self.model.encode([text], convert_to_numpy=True)[0]
        scores = cosine_similarity([article_emb], self.api_keyword_embeddings)[0]
        return scores * 100  # 0–100 스케일


class HybridMatcher:
    """
    키워드 필터링 + 임베딩 유사도 하이브리드 매칭
    """
    def __init__(self, embeddings_dir: str):
        self.embedding_matcher = EmbeddingMatcher(embeddings_dir)

    def filter_by_keywords(
        self,
        article: Dict,
        documents: List[Dict],
        min_keyword_matches: int = 1
    ) -> List[Dict]:
        """
        키워드로 1차 필터링 (빠른 검색)

        Args:
            article: {"keywords": [...]}
            documents: 전체 API 문서
            min_keyword_matches: 최소 키워드 매칭 개수

        Returns:
            필터링된 API 문서 리스트
        """
        article_keywords = set(k.lower() for k in article.get('keywords', []))

        filtered = []
        for doc in documents:
            # API 키워드
            api_keywords = doc.get('keywords', [])
            if isinstance(api_keywords, str):
                api_keywords = [k.strip() for k in api_keywords.split(',')]
            api_keywords = set(k.lower() for k in api_keywords)

            # 교집합 계산
            exact_matches = article_keywords & api_keywords
            if len(exact_matches) >= min_keyword_matches:
                filtered.append(doc)

        return filtered

    def find_similar_apis_hybrid(
        self,
        article: Dict,
        all_documents: List[Dict],
        filter_top_k: int = 1000,
        final_top_k: int = 30,
        min_similarity: float = 0.0
    ) -> List[Dict]:
        """
        하이브리드 매칭: 키워드 필터링 → 임베딩 유사도

        Args:
            article: {"topic": "...", "summary": "...", "keywords": [...]}
            all_documents: 전체 API 문서 리스트
            filter_top_k: 키워드 필터링 후 상위 K개
            final_top_k: 최종 반환 개수
            min_similarity: 최소 유사도

        Returns:
            API 문서 리스트 (유사도 순 정렬)
        """
        print(f"[HybridMatcher] Starting hybrid matching...")
        print(f"  Total documents: {len(all_documents)}")

        # Stage 1: 키워드 필터링
        filtered = self.filter_by_keywords(article, all_documents, min_keyword_matches=1)
        print(f"  After keyword filtering: {len(filtered)} documents")

        # 필터링된 문서가 너무 많으면 상위 K개만 선택
        if len(filtered) > filter_top_k:
            # 키워드 매칭 점수로 정렬
            scored = []
            article_keywords = set(k.lower() for k in article.get('keywords', []))
            for doc in filtered:
                api_keywords = doc.get('keywords', [])
                if isinstance(api_keywords, str):
                    api_keywords = [k.strip() for k in api_keywords.split(',')]
                api_keywords = set(k.lower() for k in api_keywords)

                matches = len(article_keywords & api_keywords)
                scored.append((doc, matches))

            scored.sort(key=lambda x: x[1], reverse=True)
            filtered = [doc for doc, _ in scored[:filter_top_k]]
            print(f"  Reduced to top {filter_top_k} by keyword score")

        # Stage 2: 임베딩 유사도 계산
        results = self.embedding_matcher.find_similar_apis_with_details(
            article,
            filtered,
            top_k=final_top_k,
            min_similarity=min_similarity
        )

        print(f"  Final results: {len(results)} APIs")
        return results
