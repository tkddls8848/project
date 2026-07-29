"""API 문서 간 관계(엣지) 도출 — 순수 함수 모듈.

detail_service 상세조회 계약(request_fields/response_fields/provider_agency_name/category)을
입력으로 받아 derived 관계만 계산한다. LLM 제안(llm-suggested)은 여기서 만들지 않는다.
"""
from datetime import date
from itertools import combinations
from typing import Any

# 거의 모든 공공 API에 공통이라 관계의 근거가 될 수 없는 이름 (소문자 비교)
COMMON_REQUEST_PARAMS = {
    "servicekey", "numofrows", "pageno", "resulttype", "type", "_type",
    "returntype", "pagesize", "startindex", "endindex",
}
COMMON_RESPONSE_FIELDS = {"resultcode", "resultmsg", "totalcount", "numofrows", "pageno"}

ALL_TYPES = {"same-agency", "same-domain", "param-overlap", "io-chain"}


def signature_from_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """상세조회 payload에서 관계 계산에 필요한 서명만 뽑는다."""

    def _named(fields: Any, common: set[str]) -> dict[str, str]:
        named: dict[str, str] = {}
        for field in fields or []:
            name = str(field.get("name", "")) if isinstance(field, dict) else ""
            if name and name.lower() not in common:
                named[name.lower()] = name
        return named

    return {
        "service_id": str(detail.get("service_id", "")),
        "provider": str(detail.get("provider_agency_name", "")).strip(),
        "category": str(detail.get("category", "")).strip(),
        "request_params": _named(detail.get("request_fields"), COMMON_REQUEST_PARAMS),
        "response_fields": _named(detail.get("response_fields"), COMMON_RESPONSE_FIELDS),
    }


def _edge(rtype: str, source: str, target: str, evidence: list[str],
          confidence: float, generated_at: str) -> dict[str, Any]:
    return {
        "id": f"rel:{rtype}:{source}:{target}",
        "source": source,
        "target": target,
        "type": rtype,
        "evidence": evidence,
        "confidence": confidence,
        "status": "derived",
        "generatedAt": generated_at,
    }


def _pair_edges(a: dict, b: dict, generated_at: str,
                min_shared_params: int, types: set[str]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    # 무방향 관계는 service_id 사전순으로 source를 고정해 결정적으로 만든다
    lo, hi = sorted((a, b), key=lambda sig: sig["service_id"])

    if "same-agency" in types and a["provider"] and a["provider"] == b["provider"]:
        edges.append(_edge("same-agency", lo["service_id"], hi["service_id"],
                           [f"제공기관: {a['provider']}"], 1.0, generated_at))

    if "same-domain" in types and a["category"] and a["category"] == b["category"]:
        edges.append(_edge("same-domain", lo["service_id"], hi["service_id"],
                           [f"분류체계: {a['category']}"], 1.0, generated_at))

    if "param-overlap" in types:
        shared = sorted(set(lo["request_params"]) & set(hi["request_params"]))
        if len(shared) >= min_shared_params:
            names = [lo["request_params"][key] for key in shared]
            edges.append(_edge("param-overlap", lo["service_id"], hi["service_id"],
                               [f"공유 요청 파라미터: {', '.join(names)}"],
                               round(min(0.9, 0.3 + 0.2 * len(names)), 2), generated_at))

    if "io-chain" in types:
        # 방향성: source의 응답 필드 → target의 요청 파라미터
        for src, tgt in ((a, b), (b, a)):
            links = sorted(set(src["response_fields"]) & set(tgt["request_params"]))
            if links:
                evidence = [
                    f"응답 {src['response_fields'][key]} → 요청 {tgt['request_params'][key]}"
                    for key in links
                ]
                edges.append(_edge("io-chain", src["service_id"], tgt["service_id"],
                                   evidence,
                                   round(min(0.9, 0.4 + 0.2 * len(links)), 2), generated_at))
    return edges


def derive_relations(signatures: list[dict[str, Any]], *,
                     generated_at: str | None = None,
                     min_shared_params: int = 1,
                     types: set[str] | None = None) -> list[dict[str, Any]]:
    stamp = generated_at or date.today().isoformat()
    active = ALL_TYPES if types is None else (set(types) & ALL_TYPES)
    edges: list[dict[str, Any]] = []
    for a, b in combinations(signatures, 2):
        if a["service_id"] and b["service_id"] and a["service_id"] != b["service_id"]:
            edges.extend(_pair_edges(a, b, stamp, min_shared_params, active))
    return edges
