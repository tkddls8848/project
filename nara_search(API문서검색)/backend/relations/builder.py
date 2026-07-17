"""apidata 전체의 derived 관계를 프리컴퓨트해 storage/relations.jsonl로 저장한다.

파일에는 param-overlap과 io-chain만 기록한다(스펙 4장). same-agency/same-domain은
쌍 수가 폭증하고 메타데이터에서 자명하므로 GET /relations가 요청 ID들 사이에서
즉석 계산한다. 전량(3,500여 건) 기준 수 분이 걸릴 수 있는 배치 작업이다.

실행: python -m backend.relations.builder
"""
import json
from pathlib import Path
from typing import Any

from ..catalog.detail_service import _build_flat_detail
from ..catalog.listing import latest_apidata_files
from ..core import config
from ..core.service_id import to_canonical
from .extractor import derive_relations, signature_from_detail

PRECOMPUTED_TYPES = {"param-overlap", "io-chain"}
MIN_SHARED_PARAMS = 2  # 전량 배치에서는 우연한 1개 공유를 잡음으로 본다


def build_relations(output_path: Path | None = None) -> dict[str, Any]:
    output_path = output_path or (config.STORAGE_DIR / "relations.jsonl")
    signatures = []
    for api_id, path in sorted(latest_apidata_files().items()):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            detail = _build_flat_detail(to_canonical(api_id), raw, path)
        except (OSError, json.JSONDecodeError, AttributeError, TypeError):
            continue
        signatures.append(signature_from_detail(detail))

    edges = derive_relations(
        signatures, min_shared_params=MIN_SHARED_PARAMS, types=PRECOMPUTED_TYPES
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for edge in edges:
            fh.write(json.dumps(edge, ensure_ascii=False) + "\n")
    return {"documents": len(signatures), "relations": len(edges), "output": output_path.name}


def main() -> None:
    summary = build_relations()
    print(f"[relations] 문서 {summary['documents']}건 → 관계 {summary['relations']}건 저장: {summary['output']}")


if __name__ == "__main__":
    main()
