#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 문서 임베딩 생성 스크립트

Sentence Transformers를 사용하여 모든 API 문서를 임베딩으로 변환하고 캐싱합니다.
초기 1회만 실행하면 이후 빠르게 로딩 가능합니다.
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import time


class APIEmbeddingGenerator:
    def __init__(self, model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2'):
        """
        Args:
            model_name: Sentence Transformers 모델 이름
                        (다국어 지원 모델 사용)
        """
        print(f"Loading model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print(f"Model loaded successfully!")

    def load_api_documents(self, index_file: str) -> List[Dict]:
        """
        index.json에서 모든 API 문서 로드

        Args:
            index_file: index.json 파일 경로

        Returns:
            API 문서 리스트
        """
        print(f"Loading API documents from: {index_file}")
        with open(index_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        documents = []
        for api_type, apis in data.items():
            if isinstance(apis, dict):
                for api_id, api_doc in apis.items():
                    doc = api_doc.copy()
                    doc['api_id'] = api_id
                    doc['api_type'] = api_type

                    # keywords 파싱
                    if 'keyword' in doc and isinstance(doc['keyword'], str):
                        doc['keywords'] = [k.strip() for k in doc['keyword'].split(',') if k.strip()]
                    else:
                        doc['keywords'] = []

                    documents.append(doc)

        print(f"Total API documents loaded: {len(documents)}")
        return documents

    def format_api_text(self, api_doc: Dict) -> str:
        """
        API 문서를 임베딩을 위한 텍스트로 변환

        Args:
            api_doc: API 문서

        Returns:
            포맷된 텍스트
        """
        title = api_doc.get('title', '')
        keywords = ', '.join(api_doc.get('keywords', [])[:10])  # 상위 10개 키워드
        description = api_doc.get('description', '')[:300]  # 300자까지만

        # 조합: "제목. 키워드들. 설명"
        text = f"{title}. {keywords}. {description}"
        return text

    def generate_embeddings(self, documents: List[Dict], batch_size: int = 256) -> np.ndarray:
        """
        모든 API 문서에 대한 임베딩 생성

        Args:
            documents: API 문서 리스트
            batch_size: 배치 크기 (GPU 메모리에 따라 조정)

        Returns:
            임베딩 배열 (shape: [num_docs, embedding_dim])
        """
        print(f"\nGenerating embeddings for {len(documents)} documents...")
        print(f"Batch size: {batch_size}")

        # 텍스트 준비
        texts = [self.format_api_text(doc) for doc in documents]

        # 임베딩 생성
        start_time = time.time()
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        elapsed = time.time() - start_time

        print(f"\nEmbedding generation complete!")
        print(f"  Time taken: {elapsed:.2f} seconds")
        print(f"  Embedding shape: {embeddings.shape}")
        print(f"  Memory size: {embeddings.nbytes / 1024 / 1024:.2f} MB")

        return embeddings

    def format_keyword_text(self, api_doc: Dict) -> str:
        """키워드만 사용한 임베딩용 텍스트 (제목·설명 제외)"""
        keywords = api_doc.get('keywords', [])
        return ', '.join(keywords) if keywords else api_doc.get('title', '')

    def generate_keyword_embeddings(self, documents: List[Dict], batch_size: int = 256) -> np.ndarray:
        """키워드 전용 임베딩 생성 (기사 키워드 ↔ API 키워드 유사도 비교용)"""
        print(f"\nGenerating keyword-only embeddings for {len(documents)} documents…")
        texts = [self.format_keyword_text(doc) for doc in documents]

        start_time = time.time()
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        print(f"Keyword embedding generation complete! ({time.time()-start_time:.2f}s, shape={embeddings.shape})")
        return embeddings

    def save_embeddings(self, embeddings: np.ndarray, documents: List[Dict], output_dir: str):
        """
        임베딩과 문서 ID 매핑 저장

        Args:
            embeddings: 임베딩 배열
            documents: API 문서 리스트
            output_dir: 출력 디렉토리
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. 임베딩 저장
        embeddings_file = output_path / 'api_embeddings.npy'
        np.save(embeddings_file, embeddings)
        print(f"\nEmbeddings saved to: {embeddings_file}")

        # 2. 문서 ID 매핑 저장
        mapping = [
            {
                'api_id': doc['api_id'],
                'api_type': doc['api_type'],
                'title': doc.get('title', ''),
            }
            for doc in documents
        ]
        mapping_file = output_path / 'api_embeddings_mapping.json'
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
        print(f"Mapping saved to: {mapping_file}")

        # 3. 메타데이터 저장
        metadata = {
            'model_name': self.model.get_sentence_embedding_dimension(),
            'embedding_dim': embeddings.shape[1],
            'num_documents': len(documents),
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        metadata_file = output_path / 'api_embeddings_metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"Metadata saved to: {metadata_file}")


def main():
    """메인 함수"""
    # 경로 설정
    base_dir = Path(__file__).parent.parent
    index_file = base_dir / 'storage' / 'index.json'
    output_dir = base_dir / 'storage' / 'embeddings'

    print("=" * 80)
    print("API Document Embedding Generation")
    print("=" * 80)
    print(f"Index file: {index_file}")
    print(f"Output directory: {output_dir}")
    print("=" * 80 + "\n")

    # 임베딩 생성기 초기화
    generator = APIEmbeddingGenerator()

    # API 문서 로드
    documents = generator.load_api_documents(str(index_file))

    # 전체 텍스트 임베딩 생성 (title + keywords + description)
    embeddings = generator.generate_embeddings(documents, batch_size=256)
    generator.save_embeddings(embeddings, documents, str(output_dir))

    # 키워드 전용 임베딩 생성 (기사 키워드 ↔ API 키워드 유사도 비교용)
    keyword_embeddings = generator.generate_keyword_embeddings(documents, batch_size=256)
    kw_emb_file = Path(output_dir) / 'api_keyword_embeddings.npy'
    np.save(kw_emb_file, keyword_embeddings)
    print(f"Keyword embeddings saved to: {kw_emb_file}")

    kw_meta_file = Path(output_dir) / 'api_keyword_embeddings_meta.json'
    with open(kw_meta_file, 'w', encoding='utf-8') as f:
        import json as _json
        _json.dump({
            'num_documents': len(documents),
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        }, f, indent=2)
    print(f"Keyword metadata saved to: {kw_meta_file}")

    print("\n" + "=" * 80)
    print("DONE! API embeddings generated successfully.")
    print("=" * 80)


if __name__ == "__main__":
    main()
