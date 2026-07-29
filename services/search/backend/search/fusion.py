"""Reciprocal Rank Fusion.

벡터 유사도(코사인)와 BM25 점수는 스케일이 달라 직접 합칠 수 없으므로,
점수 대신 순위만 사용하는 RRF로 융합한다 (Azure AI Search·Weaviate 등이
쓰는 표준 기법). 공식: score(d) = Σ_lists 1 / (k + rank_d), k=60.
"""
from typing import Any

RRF_K = 60


def reciprocal_rank_fusion(
    result_lists: dict[str, list[dict[str, Any]]],
    top_k: int,
    id_key: str = "api_id",
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """이름 있는 순위 목록들을 RRF로 융합한다.

    반환 레코드에는 융합 점수("score")와 어떤 채널에서 나왔는지
    ("match_channels")가 담긴다. 메타데이터는 먼저 전달된 목록의
    레코드를 우선 사용한다.
    """
    scores: dict[str, float] = {}
    records: dict[str, dict[str, Any]] = {}
    channels: dict[str, list[str]] = {}

    channel_weights = weights or {}
    for list_name, results in result_lists.items():
        weight = max(0.0, float(channel_weights.get(list_name, 1.0)))
        for rank, record in enumerate(results, start=1):
            doc_id = str(record.get(id_key, "") or "")
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (RRF_K + rank)
            channels.setdefault(doc_id, []).append(list_name)
            records.setdefault(doc_id, record)

    ranked_ids = sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)[: max(1, top_k)]

    fused = []
    for doc_id in ranked_ids:
        record = dict(records[doc_id])
        record["score"] = round(scores[doc_id], 6)
        record["match_channels"] = channels[doc_id]
        fused.append(record)
    return fused
