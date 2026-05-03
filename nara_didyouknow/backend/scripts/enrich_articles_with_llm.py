#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
신문기사에 LLM을 활용하여 주제어, 요약, 키워드 추가하는 스크립트

Ollama gemma3:4b 모델을 사용하여 각 기사를 분석하고
topic, summary, keywords를 생성하여 JSON 파일에 추가합니다.
"""
import json
import requests
from pathlib import Path
from typing import Dict, List, Any
import time


class ArticleEnricher:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model = "gemma3:4b"

    def generate_with_ollama(self, prompt: str, max_retries: int = 3) -> str:
        """Ollama API를 통해 텍스트 생성"""
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "max_tokens": 500
            }
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=60)
                response.raise_for_status()
                result = response.json()
                return result.get('response', '').strip()
            except Exception as e:
                print(f"  WARNING: Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print(f"  ERROR: Final attempt failed")
                    return ""

    def extract_article_metadata(self, article_text: str, title: str) -> Dict[str, Any]:
        """
        기사에서 topic, summary, keywords 추출

        Args:
            article_text: 기사 본문
            title: 기사 제목

        Returns:
            {"topic": str, "summary": str, "keywords": List[str]}
        """
        # Prompt 설계
        prompt = f"""다음은 뉴스 기사입니다. 이 기사를 분석하여 아래 정보를 JSON 형식으로 추출하세요.

기사 제목: {title}

기사 본문:
{article_text[:2000]}

추출할 정보:
1. topic: 이 기사의 핵심 주제를 한 문장으로 요약 (20자 이내)
2. summary: 기사 내용을 3-4문장으로 요약
3. keywords: 이 기사의 핵심 키워드 5개 (공공데이터 API 검색에 유용한 키워드)

출력 형식 (반드시 JSON 형식으로):
{{
  "topic": "주제",
  "summary": "요약 내용",
  "keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]
}}

JSON만 출력하세요:"""

        # LLM 호출
        response = self.generate_with_ollama(prompt)

        if not response:
            return {
                "topic": title[:20],
                "summary": article_text[:200],
                "keywords": []
            }

        # JSON 파싱 시도
        try:
            # JSON 부분만 추출 (```json ... ``` 형식 제거)
            json_text = response
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0].strip()

            # { ... } 부분만 추출
            start = json_text.find('{')
            end = json_text.rfind('}') + 1
            if start != -1 and end > start:
                json_text = json_text[start:end]

            metadata = json.loads(json_text)

            # 검증
            if not isinstance(metadata.get('topic'), str):
                metadata['topic'] = title[:20]
            if not isinstance(metadata.get('summary'), str):
                metadata['summary'] = article_text[:200]
            if not isinstance(metadata.get('keywords'), list):
                metadata['keywords'] = []

            # keywords가 5개가 아니면 조정
            if len(metadata['keywords']) < 5:
                metadata['keywords'].extend([''] * (5 - len(metadata['keywords'])))
            metadata['keywords'] = metadata['keywords'][:5]

            return metadata

        except Exception as e:
            print(f"  WARNING: JSON parsing failed: {e}")
            print(f"  Response: {response[:200]}")
            return {
                "topic": title[:20],
                "summary": article_text[:200],
                "keywords": []
            }

    def enrich_articles(self, json_file_path: str) -> None:
        """
        JSON 파일의 모든 기사에 metadata 추가

        Args:
            json_file_path: media_links JSON 파일 경로
        """
        # JSON 파일 읽기
        print(f"Reading file: {json_file_path}")
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        links = data.get('links', [])
        total = len(links)

        print(f"Starting analysis for {total} articles...\n")
        print("=" * 80)

        # 각 기사 처리
        for idx, link in enumerate(links, 1):
            article_text = link.get('article', '')
            title = link.get('title', '')

            # 이미 처리되었는지 확인
            if 'topic' in link and 'summary' in link and 'keywords' in link:
                print(f"[{idx}/{total}] OK - Already processed: {title[:50]}...")
                continue

            if not article_text:
                print(f"[{idx}/{total}] SKIP - No content: {title[:50]}...")
                link['topic'] = ''
                link['summary'] = ''
                link['keywords'] = []
                continue

            print(f"\n[{idx}/{total}] Processing: {title[:60]}...")

            # LLM으로 메타데이터 추출
            metadata = self.extract_article_metadata(article_text, title)

            # JSON에 추가
            link['topic'] = metadata['topic']
            link['summary'] = metadata['summary']
            link['keywords'] = metadata['keywords']

            # 결과 출력
            print(f"  Topic: {metadata['topic']}")
            print(f"  Summary: {metadata['summary'][:100]}...")
            print(f"  Keywords: {', '.join(metadata['keywords'])}")

            # 진행 상황 저장 (중간에 중단되어도 복구 가능)
            if idx % 5 == 0:
                print(f"\nSaving progress... ({idx}/{total})")
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

        # 최종 저장
        print("\n" + "=" * 80)
        print("Saving final results...")
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"DONE! {total} articles processed")
        print(f"File: {json_file_path}")


def main():
    """메인 함수"""
    # 파일 경로 설정
    base_dir = Path(__file__).parent.parent
    json_file = base_dir / "storage" / "article" / "media_links_20260128.json"

    print("=" * 80)
    print("News Article Metadata Extraction (Ollama gemma3:4b)")
    print("=" * 80)
    print(f"Target file: {json_file}")
    print(f"Model: gemma3:4b")
    print(f"Ollama URL: http://localhost:11434")
    print("=" * 80 + "\n")

    # Ollama 연결 확인
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        response.raise_for_status()
        print("OK - Ollama server connected\n")
    except Exception as e:
        print(f"ERROR - Ollama server connection failed: {e}")
        print("Please check if Ollama is running: ollama serve")
        return

    # 기사 분석 시작
    enricher = ArticleEnricher()
    enricher.enrich_articles(str(json_file))


if __name__ == "__main__":
    main()
