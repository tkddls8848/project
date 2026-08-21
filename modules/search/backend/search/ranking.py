"""검색 채널 후보의 수집 범위와 최종 랭킹 정책."""

from dataclasses import dataclass
from typing import Any, Callable

from ..core import config
from ..core.service_id import to_canonical
from .coverage import apply_coverage_prior
from .fusion import reciprocal_rank_fusion

Candidate = dict[str, Any]
CandidateSearch = Callable[[str, int], list[Candidate]]
DetailAvailability = Callable[[str], bool]


@dataclass(frozen=True)
class RankingResult:
    results: list[Candidate]
    vector_candidates: list[Candidate]
    lexical_candidates: list[Candidate]
    fusion: str
    unavailable_ids: list[str]


def rank_candidates(
    *,
    query: str,
    top_k: int,
    use_vector: bool,
    vector_search: CandidateSearch,
    lexical_search: CandidateSearch,
    detail_available: DetailAvailability,
) -> RankingResult:
    """후보를 과다 수집한 뒤 RRF·커버리지 prior·상세 필터를 적용한다."""
    candidate_k = min(
        config.MAX_TOP_K,
        max(top_k, top_k * config.CANDIDATE_MULTIPLIER),
    )
    vector_candidates = vector_search(query, candidate_k) if use_vector else []
    lexical_candidates = lexical_search(query, candidate_k)

    if vector_candidates and lexical_candidates:
        ranked = reciprocal_rank_fusion(
            {"vector": vector_candidates, "lexical": lexical_candidates},
            top_k=candidate_k,
            weights={
                "vector": config.VECTOR_RRF_WEIGHT,
                "lexical": config.LEXICAL_RRF_WEIGHT,
            },
        )
        ranked = apply_coverage_prior(
            ranked,
            query,
            config.COVERAGE_PRIOR_BONUS,
        )
        fusion = "rrf"
    elif vector_candidates or lexical_candidates:
        channel = "vector" if vector_candidates else "lexical"
        ranked = [
            dict(candidate, match_channels=[channel])
            for candidate in (vector_candidates or lexical_candidates)
        ][:candidate_k]
        fusion = channel
    else:
        ranked = []
        fusion = "none"

    available = []
    unavailable_ids = []
    for candidate in ranked:
        canonical_id = to_canonical(str(candidate.get("api_id", "")))
        if detail_available(canonical_id):
            available.append(candidate)
        else:
            unavailable_ids.append(canonical_id)
    available = available[:top_k]
    if not available:
        fusion = "none"

    return RankingResult(
        results=available,
        vector_candidates=vector_candidates,
        lexical_candidates=lexical_candidates,
        fusion=fusion,
        unavailable_ids=unavailable_ids,
    )
