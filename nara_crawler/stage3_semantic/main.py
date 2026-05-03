"""
Stage 3: 02_catalog → 03_semantic (의미 통합 계층)

부처 간 사일로 해소를 위해 카탈로그 데이터에서 표준 개념, 기관별 별칭,
필드 매핑, 서비스 태그를 생성한다.

Usage:
    python stage3_semantic/main.py [--data-type openapi|fileData|standard]

Pipeline inputs  (02_catalog/):
    services.jsonl, endpoints.jsonl, fields.jsonl, agencies.jsonl

Pipeline outputs (03_semantic/):
    taxonomy.json
    concepts.jsonl
    aliases.jsonl
    field_mappings.jsonl
    service_tags.jsonl
    concept_relations.jsonl
    agency_glossary.jsonl
    query_examples.jsonl
"""
import argparse
import os
import sys
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

CATALOG_DIR_NAME  = "02_catalog"
SEMANTIC_DIR_NAME = "03_semantic"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: catalog → semantic layer")
    parser.add_argument(
        "--data-type",
        choices=["openapi", "fileData", "standard"],
        help="특정 데이터 타입만 처리 (미지정 시 전체)",
    )
    args = parser.parse_args()

    base_dir    = Path(BASE_DIR)
    catalog_dir = base_dir / "data" / CATALOG_DIR_NAME
    output_dir  = base_dir / "data" / SEMANTIC_DIR_NAME

    if not catalog_dir.exists():
        print(f"[error] 카탈로그 디렉터리 없음: {catalog_dir}")
        print("  먼저 stage2_catalog/main.py 를 실행하세요.")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Catalog dir : {catalog_dir}")
    print(f"Output dir  : {output_dir}")

    raise NotImplementedError(
        "Stage 3 is not yet implemented.\n"
        "구현 예정 순서:\n"
        "  1. taxonomy.json  — 도메인 분류 체계 (수작업 초안)\n"
        "  2. concepts.jsonl — 표준 개념 목록 (수작업 + LLM 후보)\n"
        "  3. aliases.jsonl  — 기관별 동의어/약어 → 표준 개념 연결\n"
        "  4. field_mappings.jsonl — API 필드 → 표준 개념 매핑\n"
        "  5. service_tags.jsonl  — 서비스별 대상/혜택/자격/지역 태그\n"
        "  6. concept_relations.jsonl, agency_glossary.jsonl, query_examples.jsonl"
    )


if __name__ == "__main__":
    main()
