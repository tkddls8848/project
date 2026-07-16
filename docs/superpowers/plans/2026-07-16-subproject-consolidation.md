# 서브프로젝트 정리·통합 제품 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** openclaw·gov24_link_resolver를 archive/로 보류하고, crawler→search→combiner→dashboard 4개를 "자연어 질의 → API 문서 노드 배치 → 근거 있는 관계 엣지 → 조합 제안"이 한 흐름으로 도는 로컬 완성품으로 수렴한다.

**Architecture:** nara_search가 관계 추출(derived 엣지)과 경량 카탈로그를 새로 제공하고, nara_dashboard가 eager 번들 대신 백엔드를 호출하는 제품 UI가 된다. nara_combiner는 변경 없이 조합 제안 패널의 백엔드로 붙는다. 스펙: `docs/superpowers/specs/2026-07-16-subproject-consolidation-design.md`

**Tech Stack:** FastAPI + pytest (search), Vite + React + React Flow + vitest (dashboard), PowerShell 5.1 (기동 스크립트)

## Global Constraints

- 프로젝트 간 Python/JS 모듈 직접 import 금지 — 연결은 HTTP API 또는 파일 계약으로만
- service_id 외부 노출 형식: `{source}:{api_id}` (예: `openapi_new:15000001`)
- HTTP 오류 본문: `{ok: false, error_code, message}` (search·combiner 기존 계약과 동일)
- 관계 status 규칙: 기계 도출은 `derived`, LLM 제안은 `llm-suggested` — 절대 섞지 않는다. `relations.jsonl`에는 `derived`만 기록
- 응답·산출물에 로컬 절대 경로, stack trace, 민감정보 금지
- 배포 범위는 로컬 완성품 — 호스팅·배포 작업을 이 계획에 넣지 않는다
- 커밋 메시지는 기존 스타일(한국어 conventional commits, 예: `feat(search): ...`)
- 테스트 실행: search는 프로젝트 디렉터리에서 `python -m pytest tests -v`, dashboard는 `npm test`

**경로 표기:** 아래에서 `search/` = `D:\project\nara_search(API문서검색)\`, `dashboard/` = `D:\project\nara_dashboard(API관계대시보드)\`, `combiner/` = `D:\project\nara_combiner(API문서조합기)\`. 괄호가 든 실제 디렉터리명을 그대로 쓴다 (셸에서 따옴표 필수).

---

### Task 1: 아카이브 이동과 계획 문서 대체

**Files:**
- Move: `nara_openclaw(행정서비스실행기)/` → `archive/nara_openclaw(행정서비스실행기)/`
- Move: `nara_gov24_link_resolver(정부24서비스링크매핑)/` → `archive/nara_gov24_link_resolver(정부24서비스링크매핑)/`
- Rewrite: `plan unified.md`
- Modify: `nara_combiner(API문서조합기)/README.md:3` 및 하단 openclaw 문단

**Interfaces:**
- Consumes: 없음
- Produces: `archive/` 디렉터리 (이후 태스크는 아카이브된 프로젝트를 참조하지 않는다)

- [ ] **Step 1: archive 디렉터리 생성 및 git mv**

```powershell
New-Item -ItemType Directory -Force archive
git mv "nara_openclaw(행정서비스실행기)" "archive/nara_openclaw(행정서비스실행기)"
git mv "nara_gov24_link_resolver(정부24서비스링크매핑)" "archive/nara_gov24_link_resolver(정부24서비스링크매핑)"
```

`git mv`는 디렉터리를 통째로 디스크에서 옮기고 추적 파일의 rename을 스테이징한다. `git status`로 rename으로 잡혔는지 확인한다.

- [ ] **Step 2: plan unified.md를 통합 제품 계획으로 대체**

기존 내용 전체를 삭제하고 아래로 교체한다:

```markdown
# Nara 통합 제품 계획

- 기준일: 2026-07-16
- 설계 근거: docs/superpowers/specs/2026-07-16-subproject-consolidation-design.md
- 이 문서는 이전의 "서브프로젝트 독립 개발 계획"을 대체한다.

## 목표

자연어 질의 → 관련 공공 API 문서 검색 → 문서 노드 간 연결관계(근거 포함) 연출 →
조합 제안으로 새로운 결과 도출. korea100을 벤치마크한다:
완성 우선 태도, 근거 있는 관계 데이터 계약, 사용자 관점의 단일 웹 제품.

배포 범위는 우선 로컬 완성품이다. 호스팅·공개 배포는 완성 후 별도 결정한다.

## 프로젝트 구성

| 프로젝트 | 역할 |
| --- | --- |
| `nara_dashboard(API관계대시보드)` | 제품의 얼굴 — 자연어 질의 바, 노드 캔버스, 관계 엣지, 조합 제안 패널 |
| `nara_search(API문서검색)` | 검색·상세·카탈로그·관계(derived) API |
| `nara_combiner(API문서조합기)` | LLM 조합 제안 API (변경 최소) |
| `nara_crawler(API문서크롤러)` | apidata 공급 파이프라인 (변경 없음) |
| `korea100` | 독립 유지 — 벤치마크 대상 |

## 보류 (archive/)

- `archive/nara_openclaw(행정서비스실행기)` — 실행 기능 일체는 범위 밖
- `archive/nara_gov24_link_resolver(정부24서비스링크매핑)` — 링크 데이터셋은 범위 밖

보류 프로젝트는 유지보수하지 않는다. 재개 여부는 통합 제품 완성 후 판단한다.

## 완성 기준

- `start-all.ps1` 하나로 search + combiner + dashboard 기동
- E2E 시나리오(질의→노드→관계 엣지→조합 제안)가 고정 fixture 테스트로 재현
- 관계 빌더·백엔드 연동 테스트 포함 전체 테스트 통과
```

- [ ] **Step 3: combiner README에서 openclaw를 범위 밖으로 표시**

`nara_combiner(API문서조합기)/README.md` 3행의 문장에서
`실행, 승인, dry-run, 감사 로그는 \`nara_openclaw(행정서비스실행기)\`의 책임이다.` 를
`실행, 승인, dry-run, 감사 로그는 범위 밖이다 (실행기 프로젝트는 archive/에 보류).` 로 교체.

하단 `### GET /compose-stream` 위의 문단
`응답은 조합 아이디어와 계획 초안이다. 실제 실행은 이 응답을 구조화한 뒤 \`nara_openclaw(행정서비스실행기)\`에 전달한다. 실행·승인 기능은 이 서비스에 포함하지 않는다.` 를
`응답은 조합 아이디어와 계획 초안이다. 실행·승인 기능은 이 서비스에 포함하지 않는다 (실행기 프로젝트는 archive/에 보류).` 로 교체.

같은 파일에 `nara_openclaw`가 더 남았는지 검색(`## 역할`의 "넘길 수 있는 계획 초안" 항목은 `조합 결과 계획 초안 작성`으로 단순화)하고 정리한다.

- [ ] **Step 4: 커밋**

```powershell
git add -A
git commit -m "chore: openclaw·gov24_link_resolver를 archive/로 보류하고 통합 제품 계획으로 대체"
```

---

### Task 2: [search] 관계 추출기 (순수 함수 모듈)

**Files:**
- Create: `search/backend/relations/__init__.py` (빈 파일)
- Create: `search/backend/relations/extractor.py`
- Test: `search/tests/test_relations_extractor.py`

**Interfaces:**
- Consumes: detail_service의 상세조회 계약 dict (`service_id`, `provider_agency_name`, `category`, `request_fields[].name`, `response_fields[].name`)
- Produces:
  - `signature_from_detail(detail: dict) -> dict` — `{service_id, provider, category, request_params: {lower: 원본}, response_fields: {lower: 원본}}`
  - `derive_relations(signatures: list[dict], *, generated_at: str | None = None, min_shared_params: int = 1, types: set[str] | None = None) -> list[dict]` — 엣지 dict 목록. 엣지 스키마: `{id, source, target, type, evidence: list[str], confidence: float, status: "derived", generatedAt}`
  - 상수 `COMMON_REQUEST_PARAMS`, `COMMON_RESPONSE_FIELDS`

- [ ] **Step 1: 실패하는 테스트 작성** — `search/tests/test_relations_extractor.py`

```python
from backend.relations.extractor import derive_relations, signature_from_detail


def _detail(service_id, provider, category, request, response):
    return {
        "service_id": service_id,
        "provider_agency_name": provider,
        "category": category,
        "request_fields": [{"name": n} for n in request],
        "response_fields": [{"name": n} for n in response],
    }


AIR = _detail(
    "openapi_new:15000001", "한국환경공단", "환경기상 - 대기",
    ["serviceKey", "sidoName", "numOfRows"],
    ["pm10Value", "pm25Value", "dataTime"],
)
STATION = _detail(
    "openapi_new:15000003", "한국환경공단", "환경기상 - 대기",
    ["serviceKey", "sidoName", "stationName"],
    ["stationName", "addr", "sidoName"],
)
BUS = _detail("openapi_new:15000002", "국토교통부", "교통물류", [], [])


def _by_type(edges):
    grouped = {}
    for edge in edges:
        grouped.setdefault(edge["type"], []).append(edge)
    return grouped


def test_signature_excludes_common_params():
    sig = signature_from_detail(AIR)
    assert sig["request_params"] == {"sidoname": "sidoName"}
    assert set(sig["response_fields"]) == {"pm10value", "pm25value", "datatime"}


def test_same_agency_and_domain_edges():
    edges = _by_type(derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]))
    assert edges["same-agency"][0]["evidence"] == ["제공기관: 한국환경공단"]
    assert edges["same-agency"][0]["confidence"] == 1.0
    assert edges["same-domain"][0]["evidence"] == ["분류체계: 환경기상 - 대기"]


def test_param_overlap_edge():
    edges = _by_type(derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]))
    overlap = edges["param-overlap"][0]
    assert overlap["evidence"] == ["공유 요청 파라미터: sidoName"]
    assert overlap["confidence"] == 0.5
    # 무방향 관계는 service_id 사전순으로 source 고정
    assert overlap["source"] == "openapi_new:15000001"


def test_io_chain_is_directional():
    edges = _by_type(derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]))
    chains = edges["io-chain"]
    # STATION 응답 sidoName → AIR 요청 sidoName 한 방향만 존재
    assert len(chains) == 1
    assert chains[0]["source"] == "openapi_new:15000003"
    assert chains[0]["target"] == "openapi_new:15000001"
    assert chains[0]["evidence"] == ["응답 sidoName → 요청 sidoName"]


def test_unrelated_docs_have_no_edges():
    assert derive_relations([signature_from_detail(AIR), signature_from_detail(BUS)]) == []


def test_min_shared_params_threshold():
    edges = _by_type(derive_relations(
        [signature_from_detail(AIR), signature_from_detail(STATION)], min_shared_params=2
    ))
    assert "param-overlap" not in edges


def test_types_filter_limits_output():
    edges = derive_relations(
        [signature_from_detail(AIR), signature_from_detail(STATION)],
        types={"io-chain"},
    )
    assert {edge["type"] for edge in edges} == {"io-chain"}


def test_all_edges_are_derived_status():
    for edge in derive_relations([signature_from_detail(AIR), signature_from_detail(STATION)]):
        assert edge["status"] == "derived"
        assert edge["generatedAt"]
```

- [ ] **Step 2: 실패 확인**

```powershell
cd "D:\project\nara_search(API문서검색)"
python -m pytest tests/test_relations_extractor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.relations'`

- [ ] **Step 3: 구현** — `search/backend/relations/extractor.py` (그리고 빈 `__init__.py`)

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
python -m pytest tests/test_relations_extractor.py -v
```

Expected: 8 passed

- [ ] **Step 5: 커밋**

```powershell
git add backend/relations tests/test_relations_extractor.py
git commit -m "feat(search): API 문서 간 derived 관계 추출기 추가"
```

---

### Task 3: [search] GET /relations API

**Files:**
- Create: `search/tests/fixtures/apidata/15000003_20260101120000.json`
- Modify: `search/backend/main.py` (`service_detail` 아래에 endpoint 추가, import 2건)
- Test: `search/tests/test_relations_api.py`

**Interfaces:**
- Consumes: Task 2의 `signature_from_detail`, `derive_relations`; 기존 `detail_provider.get_detail(cid)`, `normalize_service_id`
- Produces: `GET /relations?ids=a,b,...` → `{"ids": [...정규화된 ID...], "missing": [...], "relations": [엣지 dict...]}`. 오류: 2개 미만/20개 초과/형식 오류 400, 데이터 소스 없음 503

- [ ] **Step 1: 신규 fixture 작성** — `search/tests/fixtures/apidata/15000003_20260101120000.json`

15000001(대기오염정보)과 io-chain·param-overlap이 생기도록 설계된 측정소정보 API:

```json
{
  "api_id": "15000003",
  "crawled_url": "https://www.data.go.kr/data/15000003/openapi.do",
  "info": {
    "목록명": "한국환경공단_에어코리아_측정소정보",
    "제공기관": "한국환경공단",
    "분류체계": "환경기상 - 대기",
    "키워드": "측정소,대기질,관측",
    "설명": "대기질 측정소 위치와 정보를 조회하는 서비스",
    "수정일": "2026-01-01"
  },
  "endpoints": [
    { "method": "GET", "path": "/getMsrstnList", "description": "측정소 목록 조회" }
  ],
  "swagger_json": {
    "info": { "title": "측정소정보", "description": "측정소 정보 조회" },
    "paths": {
      "/getMsrstnList": {
        "get": {
          "summary": "측정소 목록 조회",
          "parameters": [
            { "name": "serviceKey", "in": "query", "required": true, "type": "string", "description": "인증키" },
            { "name": "sidoName", "in": "query", "required": false, "type": "string", "description": "시도 이름" },
            { "name": "stationName", "in": "query", "required": false, "type": "string", "description": "측정소 이름" }
          ]
        }
      }
    },
    "definitions": {
      "Item": {
        "properties": {
          "stationName": { "type": "string", "description": "측정소 이름" },
          "addr": { "type": "string", "description": "측정소 주소" },
          "sidoName": { "type": "string", "description": "시도 이름" }
        }
      }
    }
  }
}
```

fixture 추가 후 기존 테스트 전체를 돌려 문서 수(2건)를 가정한 테스트가 있는지 확인한다:

```powershell
python -m pytest tests -v
```

문서 수를 세는 단정문이 깨지면 3건 기준으로 수정한다 (깨지는 게 없으면 그대로 진행).

- [ ] **Step 2: 실패하는 테스트 작성** — `search/tests/test_relations_api.py`

기존 `tests/test_detail_api.py`의 스타일(공용 `app_client` fixture)을 따른다:

```python
def _types(payload):
    return {edge["type"] for edge in payload["relations"]}


def test_relations_between_air_and_station(app_client):
    res = app_client.get("/relations", params={"ids": "15000001,15000003"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["ids"] == ["openapi_new:15000001", "openapi_new:15000003"]
    assert payload["missing"] == []
    assert _types(payload) == {"same-agency", "same-domain", "param-overlap", "io-chain"}
    chain = [e for e in payload["relations"] if e["type"] == "io-chain"][0]
    assert chain["source"] == "openapi_new:15000003"
    assert chain["evidence"] == ["응답 sidoName → 요청 sidoName"]
    assert all(e["status"] == "derived" for e in payload["relations"])


def test_relations_reports_missing_ids(app_client):
    res = app_client.get("/relations", params={"ids": "15000001,15999999"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["missing"] == ["openapi_new:15999999"]
    assert payload["relations"] == []


def test_relations_requires_at_least_two_ids(app_client):
    res = app_client.get("/relations", params={"ids": "15000001"})
    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_IDS"


def test_relations_rejects_malformed_id(app_client):
    res = app_client.get("/relations", params={"ids": "15000001,bogus prefix:x"})
    assert res.status_code == 400
```

(`bogus prefix:x`가 `normalize_service_id`에서 통과해 버리면 `tests/test_service_id.py`에서 확실히 거부되는 형식을 골라 바꾼다.)

- [ ] **Step 3: 실패 확인**

```powershell
python -m pytest tests/test_relations_api.py -v
```

Expected: FAIL — `/relations` 404

- [ ] **Step 4: endpoint 구현** — `search/backend/main.py`

import에 추가:

```python
from .relations.extractor import derive_relations, signature_from_detail
```

`service_detail` 함수 아래에 추가:

```python
@app.get("/relations")
def relations(ids: str = ""):
    """요청된 service_id들 사이의 derived 관계를 즉석 계산해 반환한다.

    같은 추출기를 relations.jsonl 프리컴퓨트(backend.relations.builder)와 공유하므로
    엣지 스키마는 항상 동일하다.
    """
    raw_ids = [part.strip() for part in ids.split(",") if part.strip()]
    if not 2 <= len(raw_ids) <= 20:
        return _error_response(400, "INVALID_IDS", "ids는 쉼표로 구분한 2~20개의 service_id여야 합니다")

    canonical_ids: list[str] = []
    for raw in raw_ids:
        try:
            cid = normalize_service_id(raw)
        except ServiceIdError as exc:
            return _error_response(400, exc.error_code, exc.message)
        if cid not in canonical_ids:
            canonical_ids.append(cid)

    signatures, missing = [], []
    for cid in canonical_ids:
        try:
            detail = detail_provider.get_detail(cid)
        except DetailUnavailableError as exc:
            return _error_response(503, "SERVICE_UNAVAILABLE", exc.message)
        if detail is None:
            missing.append(cid)
        else:
            signatures.append(signature_from_detail(detail))

    return {"ids": canonical_ids, "missing": missing, "relations": derive_relations(signatures)}
```

- [ ] **Step 5: 전체 테스트 통과 확인**

```powershell
python -m pytest tests -v
```

Expected: 기존 + 신규 모두 PASS

- [ ] **Step 6: 커밋**

```powershell
git add backend/main.py tests/test_relations_api.py tests/fixtures/apidata/15000003_20260101120000.json
git commit -m "feat(search): GET /relations — 요청 ID 간 derived 관계 계산 API"
```

---

### Task 4: [search] GET /catalog 경량 카탈로그 API

**Files:**
- Create: `search/backend/catalog/listing.py`
- Modify: `search/backend/main.py` (endpoint + `_on_complete` reload)
- Modify: `search/tests/conftest.py` (`app_client`에 listing reload 추가)
- Test: `search/tests/test_catalog_api.py`

**Interfaces:**
- Consumes: `detail_service._build_flat_detail`, `config.APIDATA_DIR`, `to_canonical`
- Produces:
  - `latest_apidata_files() -> dict[str, Path]` — api_id → 최신 파일 (Task 5 빌더가 재사용)
  - `CatalogListing.list_docs() -> list[dict]`, `CatalogListing.reload()`
  - `GET /catalog` → `{"total": int, "docs": [{service_id, api_id, name, provider, category, keywords, description, fields: [{key, desc}], endpoints: [{method, path, description}]}]}`

- [ ] **Step 1: 실패하는 테스트 작성** — `search/tests/test_catalog_api.py`

```python
def test_catalog_lists_fixture_docs(app_client):
    res = app_client.get("/catalog")
    assert res.status_code == 200
    payload = res.json()
    assert payload["total"] == 3
    by_id = {doc["api_id"]: doc for doc in payload["docs"]}
    air = by_id["15000001"]
    assert air["service_id"] == "openapi_new:15000001"
    assert air["provider"] == "한국환경공단"
    assert {"key": "pm10Value", "desc": "미세먼지(PM10) 농도"} in air["fields"]
    assert air["endpoints"][0]["method"] == "GET"
    # swagger가 빈 문서도 목록에는 나온다
    assert by_id["15000002"]["fields"] == []


def test_catalog_empty_when_apidata_missing(app_client, monkeypatch, tmp_path):
    from backend.core import config
    from backend import main

    monkeypatch.setattr(config, "APIDATA_DIR", tmp_path / "none")
    main.catalog_listing.reload()
    res = app_client.get("/catalog")
    assert res.status_code == 200
    assert res.json() == {"total": 0, "docs": []}
```

- [ ] **Step 2: 실패 확인**

```powershell
python -m pytest tests/test_catalog_api.py -v
```

Expected: FAIL — `/catalog` 404

- [ ] **Step 3: 구현** — `search/backend/catalog/listing.py`

```python
"""대시보드용 경량 카탈로그 목록 (GET /catalog).

apidata 평면 JSON을 스캔해 문서별 요약(fields/endpoints 포함)을 만들고 메모리에 캐시한다.
인덱스 빌드 완료 시 main._on_complete가 reload()로 캐시를 비운다.
"""
import json
from pathlib import Path
from typing import Any

from ..core import config
from ..core.service_id import to_canonical
from .detail_service import _build_flat_detail


def latest_apidata_files() -> dict[str, Path]:
    """api_id → 최신 파일. 파일명 {api_id}_{date}.json이 정렬로 최신이 뒤에 온다."""
    latest: dict[str, Path] = {}
    if not config.APIDATA_DIR.exists():
        return latest
    for path in sorted(config.APIDATA_DIR.glob("*.json")):
        latest[path.stem.split("_")[0]] = path
    return latest


class CatalogListing:
    def __init__(self) -> None:
        self._cache: list[dict[str, Any]] | None = None

    def reload(self) -> None:
        self._cache = None

    def list_docs(self) -> list[dict[str, Any]]:
        if self._cache is None:
            self._cache = self._scan()
        return self._cache

    def _scan(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for api_id, path in sorted(latest_apidata_files().items()):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            detail = _build_flat_detail(to_canonical(api_id), raw, path)
            docs.append({
                "service_id": detail["service_id"],
                "api_id": api_id,
                "name": detail["name"],
                "provider": detail["provider_agency_name"],
                "category": detail["category"],
                "keywords": detail["keywords"],
                "description": detail["description"],
                "fields": [
                    {"key": f["name"], "desc": f["description"] or f["name"]}
                    for f in detail["response_fields"]
                ],
                "endpoints": [
                    {"method": e["method"], "path": e["path"], "description": e["summary"]}
                    for e in detail["endpoints"]
                ],
            })
        return docs
```

`search/backend/main.py`:

```python
from .catalog.listing import CatalogListing
# 전역 인스턴스 (retriever들 옆에)
catalog_listing = CatalogListing()
```

```python
@app.get("/catalog")
def catalog():
    docs = catalog_listing.list_docs()
    return {"total": len(docs), "docs": docs}
```

`trigger_build`의 `_on_complete`에 `catalog_listing.reload()` 추가.

`search/tests/conftest.py`의 `app_client`에서 `main.detail_provider.reload()` 옆에 `main.catalog_listing.reload()`를 yield 전후 모두 추가.

- [ ] **Step 4: 전체 테스트 통과 확인**

```powershell
python -m pytest tests -v
```

Expected: PASS

- [ ] **Step 5: 커밋**

```powershell
git add backend/catalog/listing.py backend/main.py tests/test_catalog_api.py tests/conftest.py
git commit -m "feat(search): GET /catalog — 대시보드용 경량 카탈로그 API"
```

---

### Task 5: [search] relations.jsonl 프리컴퓨트 빌더 CLI

**Files:**
- Create: `search/backend/relations/builder.py`
- Test: `search/tests/test_relations_builder.py`
- Modify: `search/README.md` (실행 방법 추가 — Step 6)

**Interfaces:**
- Consumes: Task 2 `derive_relations`/`signature_from_detail`, Task 4 `latest_apidata_files`, `_build_flat_detail`
- Produces: `build_relations(output_path: Path | None = None) -> dict` (`{"documents", "relations", "output"}`), CLI `python -m backend.relations.builder`, 산출물 `storage/relations.jsonl` (derived param-overlap·io-chain만, 1행 1엣지)

- [ ] **Step 1: 실패하는 테스트 작성** — `search/tests/test_relations_builder.py`

```python
import json


def test_build_relations_writes_derived_jsonl(monkeypatch, tmp_path, fixture_apidata_dir):
    from backend.core import config
    from backend.relations.builder import build_relations

    monkeypatch.setattr(config, "APIDATA_DIR", fixture_apidata_dir)
    output = tmp_path / "relations.jsonl"
    summary = build_relations(output_path=output)

    assert summary["documents"] == 3
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    # 파일에는 param-overlap·io-chain만 기록한다 (min_shared_params=2라 1개 공유는 제외)
    assert {edge["type"] for edge in lines} == {"io-chain"}
    assert all(edge["status"] == "derived" for edge in lines)
    chain = lines[0]
    assert chain["source"] == "openapi_new:15000003"
    assert chain["target"] == "openapi_new:15000001"
```

- [ ] **Step 2: 실패 확인**

```powershell
python -m pytest tests/test_relations_builder.py -v
```

Expected: FAIL — `No module named 'backend.relations.builder'`

- [ ] **Step 3: 구현** — `search/backend/relations/builder.py`

```python
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
        except (OSError, json.JSONDecodeError):
            continue
        signatures.append(signature_from_detail(_build_flat_detail(to_canonical(api_id), raw, path)))

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
```

- [ ] **Step 4: 테스트 통과 확인**

```powershell
python -m pytest tests/test_relations_builder.py -v
```

Expected: PASS

- [ ] **Step 5: CLI 스모크 실행** (fixture로)

```powershell
$env:NARA_SEARCH_APIDATA_DIR = "$PWD\tests\fixtures\apidata"
$env:NARA_SEARCH_STORAGE_DIR = "$env:TEMP\nara_relations_smoke"
python -m backend.relations.builder
Remove-Item Env:NARA_SEARCH_APIDATA_DIR; Remove-Item Env:NARA_SEARCH_STORAGE_DIR
```

Expected: `[relations] 문서 3건 → 관계 1건 저장: relations.jsonl`

- [ ] **Step 6: README에 신규 API·빌더 문서화**

`search/README.md`의 실행 섹션 뒤에 추가:

```markdown
## 관계·카탈로그 API

- `GET /catalog` — 대시보드용 경량 카탈로그 (문서별 name/provider/category/fields/endpoints)
- `GET /relations?ids=15000001,15000003` — 요청 ID 간 derived 관계
  (same-agency / same-domain / param-overlap / io-chain, evidence·confidence 포함)
- `python -m backend.relations.builder` — apidata 전량의 param-overlap·io-chain을
  `storage/relations.jsonl`로 프리컴퓨트 (배치, 수 분 소요 가능)
```

- [ ] **Step 7: 커밋**

```powershell
git add backend/relations/builder.py tests/test_relations_builder.py README.md
git commit -m "feat(search): relations.jsonl 프리컴퓨트 빌더 CLI"
```

---

### Task 6: [dashboard] eager 번들 제거 — 런타임 카탈로그 로딩

**Files:**
- Modify: `dashboard/src/data/apiDocs.js` (glob 제거, loadCatalog 추가)
- Modify: `dashboard/src/App.jsx` (로딩 상태 + 연결 오류 배너)
- Test: `dashboard/src/data/__tests__/apiDocs.test.js` (신규)

**Interfaces:**
- Consumes: Task 4의 `GET /catalog` (vite 프록시 `/api/catalog` — 기존 `/api/*` → 127.0.0.1:8000 프록시 그대로 사용)
- Produces:
  - `apiDocs: Array` / `apiDocMap: Object` — **같은 참조를 유지한 채** loadCatalog가 내용을 채우는 mutable export (기존 소비자 ApiDocNode/MergeNode/NodeProperties/NodePalette/workflowEngine 수정 불필요)
  - `loadCatalog({ force } = {}) -> Promise<{state: 'ready'|'error', error: string}>`
  - 기존 export 유지: `searchApiDocs`, `toWorkflowDoc`, `uniqueDocs`

- [ ] **Step 1: 실패하는 테스트 작성** — `dashboard/src/data/__tests__/apiDocs.test.js`

```js
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiDocs, apiDocMap, loadCatalog, searchApiDocs } from '../apiDocs.js';

const CATALOG_PAYLOAD = {
  total: 1,
  docs: [{
    service_id: 'openapi_new:15000001',
    api_id: '15000001',
    name: '한국환경공단_에어코리아_대기오염정보',
    provider: '한국환경공단',
    category: '환경기상 - 대기',
    keywords: ['대기오염', '미세먼지'],
    description: '시도별 실시간 대기오염 측정정보를 조회하는 서비스',
    fields: [{ key: 'pm10Value', desc: '미세먼지(PM10) 농도' }],
    endpoints: [{ method: 'GET', path: '/getCtprvnRltmMesureDnsty', description: '시도별 실시간 측정정보 조회' }],
  }],
};

afterEach(() => vi.unstubAllGlobals());

describe('loadCatalog', () => {
  it('백엔드 카탈로그로 apiDocs/apiDocMap을 채운다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => CATALOG_PAYLOAD }));
    const result = await loadCatalog({ force: true });

    expect(result.state).toBe('ready');
    expect(fetch).toHaveBeenCalledWith('/api/catalog');
    expect(apiDocs).toHaveLength(1);
    expect(apiDocMap['15000001'].topCategory).toBe('환경기상');
    expect(apiDocMap['15000001'].serviceId).toBe('openapi_new:15000001');
    expect(searchApiDocs('미세먼지')).toHaveLength(1);
  });

  it('백엔드 미기동이면 error 상태를 반환하고 기존 문서를 지우지 않는다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    const before = apiDocs.length;
    const result = await loadCatalog({ force: true });

    expect(result.state).toBe('error');
    expect(result.error).toBeTruthy();
    expect(apiDocs).toHaveLength(before);
  });
});
```

- [ ] **Step 2: 실패 확인**

```powershell
cd "D:\project\nara_dashboard(API관계대시보드)"
npm test
```

Expected: FAIL — `loadCatalog` export 없음

- [ ] **Step 3: apiDocs.js 재작성**

파일 상단의 `import.meta.glob` 블록과 `extractFields`/`extractEndpoints` 함수, 기존 `export const apiDocs = ...`/`apiDocMap` 정의를 삭제하고 아래로 교체한다. `topCategory`, `parseKeywords`와 검색·유틸 함수들(`normalizeText`부터 `uniqueDocs`까지)은 그대로 둔다:

```js
// 카탈로그는 빌드 타임 번들이 아니라 nara_search 백엔드(GET /api/catalog)에서
// 런타임에 로딩한다. apiDocs/apiDocMap은 같은 참조를 유지한 채 내용만 채워지므로
// 기존 소비자(노드·팔레트·워크플로우 엔진)는 로딩 완료 후 그대로 동작한다.
export const apiDocs = [];
export const apiDocMap = {};

let loadState = 'idle'; // idle | loading | ready | error
let loadError = '';

function toClientDoc(raw) {
  return {
    apiId: raw.api_id ?? '',
    serviceId: raw.service_id ?? '',
    name: raw.name ?? raw.api_id ?? '',
    provider: raw.provider ?? '',
    topCategory: topCategory(raw.category),
    category: raw.category ?? '',
    keywords: Array.isArray(raw.keywords) ? raw.keywords : parseKeywords(raw.keywords),
    description: raw.description ?? '',
    fields: raw.fields ?? [],
    endpoints: raw.endpoints ?? [],
  };
}

export async function loadCatalog({ force = false } = {}) {
  if (!force && (loadState === 'ready' || loadState === 'loading')) {
    return { state: loadState, error: loadError };
  }
  loadState = 'loading';
  try {
    const res = await fetch('/api/catalog');
    if (!res.ok) throw new Error(`카탈로그 응답 오류 (HTTP ${res.status})`);
    const payload = await res.json();
    const docs = (payload.docs ?? [])
      .map(toClientDoc)
      .sort((a, b) => a.topCategory.localeCompare(b.topCategory, 'ko'));

    apiDocs.length = 0;
    apiDocs.push(...docs);
    Object.keys(apiDocMap).forEach(key => delete apiDocMap[key]);
    docs.forEach(doc => { apiDocMap[doc.apiId] = doc; });

    loadState = 'ready';
    loadError = '';
  } catch (error) {
    // 실패 시 이전에 로딩된 문서는 유지한다 (기능 저하 모드)
    loadState = 'error';
    loadError = error?.message || 'nara_search 백엔드에 연결할 수 없습니다.';
  }
  return { state: loadState, error: loadError };
}
```

- [ ] **Step 4: App.jsx에 로딩·오류 배너 추가**

`App.jsx` import에 `useEffect` 추가(`react`), `loadCatalog` 추가(`./data/apiDocs.js`). `App` 컴포넌트 상단에:

```js
const [catalog, setCatalog] = useState({ state: 'loading', error: '' });

useEffect(() => {
  loadCatalog().then(setCatalog);
}, []);

const retryCatalog = useCallback(() => {
  setCatalog({ state: 'loading', error: '' });
  loadCatalog({ force: true }).then(setCatalog);
}, []);
```

`<Toolbar ... />` 바로 아래에 배너를 렌더링한다:

```jsx
{catalog.state === 'error' && (
  <div style={{
    background: '#450a0a', borderBottom: '1px solid #7f1d1d', color: '#fca5a5',
    padding: '6px 14px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 10,
  }}>
    <span>nara_search 백엔드에 연결할 수 없습니다 — 카탈로그가 빈 상태로 동작합니다. ({catalog.error})</span>
    <button onClick={retryCatalog} style={{
      background: 'transparent', border: '1px solid #f8717144', borderRadius: 5,
      color: '#f87171', fontSize: 11, padding: '2px 8px', cursor: 'pointer',
    }}>다시 시도</button>
  </div>
)}
```

카탈로그 state 변경으로 App이 리렌더되면 NodePalette·NodeProperties가 채워진 `apiDocs`를 다시 읽는다 (별도 prop 불필요).

- [ ] **Step 5: 테스트·빌드 확인**

```powershell
npm test
npm run build
```

Expected: 전체 테스트 PASS (기존 workflowEngine 테스트는 apiDocs를 mock하므로 영향 없음), build 성공 — 대형 청크 경고가 사라지거나 크게 줄었는지 출력에서 확인해 기록

- [ ] **Step 6: 커밋**

```powershell
git add src/data/apiDocs.js src/data/__tests__/apiDocs.test.js src/App.jsx
git commit -m "feat(dashboard): apidata eager 번들 제거 — 백엔드 카탈로그 런타임 로딩"
```

---

### Task 7: [dashboard] 자연어 질의 바 — 검색 결과 노드 자동 배치 + 관계 점선 엣지

**Files:**
- Create: `dashboard/src/data/searchClient.js`
- Create: `dashboard/src/data/relationEdges.js`
- Create: `dashboard/src/components/QueryBar.jsx`
- Modify: `dashboard/src/App.jsx` (질의 핸들러·QueryBar 렌더)
- Modify: `dashboard/src/data/workflowEngine.js:41-43` (`outputDocsFor`의 apiDoc 분기)
- Modify: `dashboard/src/nodes/ApiDocNode.jsx:27`, `dashboard/src/nodes/MergeNode.jsx:10,18`, `dashboard/src/components/NodeProperties.jsx:439` (`data.doc` 우선)
- Test: `dashboard/src/data/__tests__/searchClient.test.js`, `dashboard/src/data/__tests__/relationEdges.test.js` (신규), `dashboard/src/data/__tests__/workflowEngine.test.js` (케이스 추가)

**Interfaces:**
- Consumes: search API `POST /api/search` `{query, top_k}` → `{results: [{service_id, name, ...}]}`; `GET /api/services/{service_id}` → 상세 계약(`provider_agency_name`, `category`, `keywords`, `endpoints[].summary`, `response_fields[].name/description`); `GET /api/relations?ids=...` → Task 3 계약
- Produces:
  - `searchClient.js`: `searchDocsWithDetails(query, topK) -> Promise<doc[]>` (doc = `{apiId, serviceId, name, provider, topCategory, category, keywords, description, fields, endpoints}`), `fetchRelations(serviceIds) -> Promise<relation[]>`, `detailToWorkflowDoc(detail) -> doc`
  - `relationEdges.js`: `SUGGESTED_EDGE_STYLE`, `APPROVED_EDGE_STYLE`, `placeSearchResults(docs, relations, makeId, origin?) -> {nodes, edges}` — apiDoc 노드는 `data: {apiId, doc}`, 관계 엣지는 점선·`data: {relation}`
  - apiDoc 노드 규약 확장: `data.doc`이 있으면 `apiDocMap`보다 우선한다 (flowIO의 `sanitizeNodeData`는 `doc`을 보존하므로 내보내기/가져오기에도 유지됨)

- [ ] **Step 1: 실패하는 테스트 작성 (searchClient)** — `dashboard/src/data/__tests__/searchClient.test.js`

```js
import { afterEach, describe, expect, it, vi } from 'vitest';
import { detailToWorkflowDoc, fetchRelations, searchDocsWithDetails } from '../searchClient.js';

const SEARCH_PAYLOAD = {
  query: '대기오염',
  results: [
    { service_id: 'openapi_new:15000001', name: '대기오염정보' },
    { service_id: 'openapi_new:15000003', name: '측정소정보' },
  ],
};

const DETAILS = {
  'openapi_new:15000001': {
    service_id: 'openapi_new:15000001',
    name: '한국환경공단_에어코리아_대기오염정보',
    provider_agency_name: '한국환경공단',
    category: '환경기상 - 대기',
    keywords: ['대기오염'],
    description: '시도별 실시간 대기오염 측정정보',
    endpoints: [{ method: 'GET', path: '/getCtprvnRltmMesureDnsty', summary: '시도별 조회' }],
    request_fields: [{ name: 'sidoName', description: '시도 이름' }],
    response_fields: [{ name: 'pm10Value', description: '미세먼지(PM10) 농도' }],
  },
  'openapi_new:15000003': {
    service_id: 'openapi_new:15000003',
    name: '한국환경공단_에어코리아_측정소정보',
    provider_agency_name: '한국환경공단',
    category: '환경기상 - 대기',
    keywords: ['측정소'],
    description: '측정소 위치와 정보',
    endpoints: [{ method: 'GET', path: '/getMsrstnList', summary: '측정소 목록' }],
    request_fields: [{ name: 'sidoName', description: '시도 이름' }],
    response_fields: [{ name: 'sidoName', description: '시도 이름' }],
  },
};

const RELATIONS_PAYLOAD = {
  ids: Object.keys(DETAILS),
  missing: [],
  relations: [{
    id: 'rel:io-chain:openapi_new:15000003:openapi_new:15000001',
    source: 'openapi_new:15000003',
    target: 'openapi_new:15000001',
    type: 'io-chain',
    evidence: ['응답 sidoName → 요청 sidoName'],
    confidence: 0.6,
    status: 'derived',
    generatedAt: '2026-07-16',
  }],
};

function stubBackend() {
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    const path = String(url);
    if (path === '/api/search' || path.startsWith('/api/search')) {
      return { ok: true, json: async () => SEARCH_PAYLOAD };
    }
    if (path.startsWith('/api/relations')) {
      return { ok: true, json: async () => RELATIONS_PAYLOAD };
    }
    const detail = DETAILS[decodeURIComponent(path.replace('/api/services/', ''))];
    return detail
      ? { ok: true, json: async () => detail }
      : { ok: false, status: 404, json: async () => ({ ok: false }) };
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe('searchClient', () => {
  it('검색 결과를 상세조회로 보강한 워크플로우 doc으로 돌려준다', async () => {
    stubBackend();
    const docs = await searchDocsWithDetails('대기오염', 5);
    expect(docs).toHaveLength(2);
    expect(docs[0]).toMatchObject({
      apiId: '15000001',
      serviceId: 'openapi_new:15000001',
      provider: '한국환경공단',
      topCategory: '환경기상',
      fields: [{ key: 'pm10Value', desc: '미세먼지(PM10) 농도' }],
    });
  });

  it('fetchRelations는 relations 배열을 반환한다', async () => {
    stubBackend();
    const relations = await fetchRelations(Object.keys(DETAILS));
    expect(relations).toHaveLength(1);
    expect(relations[0].type).toBe('io-chain');
  });

  it('detailToWorkflowDoc은 endpoints summary를 description으로 매핑한다', () => {
    const doc = detailToWorkflowDoc(DETAILS['openapi_new:15000001']);
    expect(doc.endpoints).toEqual([
      { method: 'GET', path: '/getCtprvnRltmMesureDnsty', description: '시도별 조회' },
    ]);
  });

  it('백엔드 미기동이면 명확한 오류를 던진다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    await expect(searchDocsWithDetails('대기오염', 5)).rejects.toThrow(/연결/);
  });
});
```

- [ ] **Step 2: 실패하는 테스트 작성 (relationEdges)** — `dashboard/src/data/__tests__/relationEdges.test.js`

```js
import { describe, expect, it } from 'vitest';
import { placeSearchResults, SUGGESTED_EDGE_STYLE } from '../relationEdges.js';

const DOCS = [
  { apiId: '15000001', serviceId: 'openapi_new:15000001', name: '대기오염정보' },
  { apiId: '15000003', serviceId: 'openapi_new:15000003', name: '측정소정보' },
];

const RELATIONS = [{
  id: 'rel:io-chain:openapi_new:15000003:openapi_new:15000001',
  source: 'openapi_new:15000003',
  target: 'openapi_new:15000001',
  type: 'io-chain',
  evidence: ['응답 sidoName → 요청 sidoName'],
  confidence: 0.6,
  status: 'derived',
  generatedAt: '2026-07-16',
}];

function makeIdFactory() {
  let n = 0;
  return () => `node-q${++n}`;
}

describe('placeSearchResults', () => {
  it('doc이 내장된 apiDoc 노드와 점선 관계 엣지를 만든다', () => {
    const { nodes, edges } = placeSearchResults(DOCS, RELATIONS, makeIdFactory());
    expect(nodes).toHaveLength(2);
    expect(nodes[0].type).toBe('apiDoc');
    expect(nodes[0].data).toEqual({ apiId: '15000001', doc: DOCS[0] });
    expect(nodes[0].position).not.toEqual(nodes[1].position);

    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe(nodes[1].id); // 15000003 노드
    expect(edges[0].target).toBe(nodes[0].id);
    expect(edges[0].style).toEqual(SUGGESTED_EDGE_STYLE);
    expect(edges[0].animated).toBe(true);
    expect(edges[0].data.relation.evidence).toEqual(['응답 sidoName → 요청 sidoName']);
  });

  it('캔버스에 없는 ID를 가리키는 관계는 버린다', () => {
    const { edges } = placeSearchResults([DOCS[0]], RELATIONS, makeIdFactory());
    expect(edges).toHaveLength(0);
  });
});
```

- [ ] **Step 3: 실패 확인**

```powershell
npm test
```

Expected: FAIL — 두 모듈 없음

- [ ] **Step 4: searchClient.js 구현**

```js
// nara_search 백엔드 클라이언트 (vite 프록시 /api → 127.0.0.1:8000).
// 검색 결과에는 fields가 없으므로 상세조회로 보강해 워크플로우 doc을 만든다.

function apiIdOf(serviceId) {
  const idx = String(serviceId ?? '').lastIndexOf(':');
  return idx >= 0 ? String(serviceId).slice(idx + 1) : String(serviceId ?? '');
}

async function backendFetch(input, init) {
  let res;
  try {
    res = await fetch(input, init);
  } catch {
    throw new Error('nara_search 백엔드에 연결할 수 없습니다.');
  }
  return res;
}

export function detailToWorkflowDoc(detail) {
  const category = detail.category ?? '';
  return {
    apiId: apiIdOf(detail.service_id),
    serviceId: detail.service_id ?? '',
    name: detail.name ?? '',
    provider: detail.provider_agency_name ?? '',
    topCategory: category.split(' - ')[0].trim() || '기타',
    category,
    keywords: detail.keywords ?? [],
    description: detail.description ?? '',
    fields: (detail.response_fields ?? []).map(f => ({ key: f.name, desc: f.description || f.name })),
    endpoints: (detail.endpoints ?? []).map(e => ({
      method: e.method ?? 'GET',
      path: e.path ?? '',
      description: e.summary ?? '',
    })),
  };
}

export async function searchRemote(query, topK = 6) {
  const res = await backendFetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error(`검색 실패 (HTTP ${res.status})`);
  const payload = await res.json();
  return payload.results ?? [];
}

export async function fetchDetail(serviceId) {
  const res = await backendFetch(`/api/services/${encodeURIComponent(serviceId)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`상세조회 실패 (HTTP ${res.status})`);
  return res.json();
}

export async function fetchRelations(serviceIds) {
  const res = await backendFetch(`/api/relations?ids=${encodeURIComponent(serviceIds.join(','))}`);
  if (!res.ok) throw new Error(`관계 조회 실패 (HTTP ${res.status})`);
  const payload = await res.json();
  return payload.relations ?? [];
}

export async function searchDocsWithDetails(query, topK = 6) {
  const results = await searchRemote(query, topK);
  const details = await Promise.all(results.map(r => fetchDetail(r.service_id)));
  return details.filter(Boolean).map(detailToWorkflowDoc);
}
```

- [ ] **Step 5: relationEdges.js 구현**

```js
// 검색 결과 doc과 derived 관계를 캔버스 노드·엣지로 변환 — DOM 의존 없는 순수 함수.

export const SUGGESTED_EDGE_STYLE = { stroke: '#f59e0b', strokeWidth: 1.5, strokeDasharray: '6 4' };
export const APPROVED_EDGE_STYLE = { stroke: '#475569', strokeWidth: 2 };

export function placeSearchResults(docs, relations, makeId, origin = { x: 80, y: 120 }) {
  const nodes = docs.map((doc, index) => ({
    id: makeId(),
    type: 'apiDoc',
    position: {
      x: origin.x + (index % 3) * 280,
      y: origin.y + Math.floor(index / 3) * 240,
    },
    data: { apiId: doc.apiId, doc },
  }));

  const idByService = new Map(docs.map((doc, index) => [doc.serviceId, nodes[index].id]));
  const edges = (relations ?? [])
    .filter(rel => idByService.has(rel.source) && idByService.has(rel.target))
    .map(rel => ({
      id: `rel-${rel.id}`,
      source: idByService.get(rel.source),
      target: idByService.get(rel.target),
      type: 'smoothstep',
      label: rel.type,
      animated: true,
      style: SUGGESTED_EDGE_STYLE,
      data: { relation: rel },
    }));

  return { nodes, edges };
}
```

- [ ] **Step 6: `data.doc` 우선 규약 적용 (4개 파일)**

`workflowEngine.js` `outputDocsFor`의 apiDoc 분기:

```js
  if (node.type === 'apiDoc') {
    const doc = node.data?.doc ?? apiDocMap[node.data?.apiId];
    return doc ? [toWorkflowDoc(doc)] : [];
  }
```

`ApiDocNode.jsx:27`: `const doc = data.doc ?? apiDocMap[data.apiId];`

`MergeNode.jsx:10`: `return node.data?.doc?.name ?? apiDocMap[node.data?.apiId]?.name ?? node.data?.apiId ?? '?';`
`MergeNode.jsx:18`: `const doc = node.data?.doc ?? apiDocMap[node.data?.apiId];`

`NodeProperties.jsx`는 두 곳을 고친다 — 354행 호출부:
`{node.type === 'apiDoc' && <ApiDocProperties apiId={node.data?.apiId} doc={node.data?.doc} />}`
그리고 438-439행 시그니처:

```js
function ApiDocProperties({ apiId, doc: embeddedDoc }) {
  const doc = embeddedDoc ?? apiDocMap[apiId];
```

`workflowEngine.test.js`에 케이스 추가:

```js
it('apiDoc 노드는 data.doc이 있으면 카탈로그 없이 동작한다', () => {
  const embedded = { apiId: 'X9', name: '내장 문서', provider: 'T', topCategory: '기타',
    category: '기타', keywords: [], description: '', fields: [], endpoints: [] };
  const nodes = [
    { id: 'doc-1', type: 'apiDoc', data: { apiId: 'X9', doc: embedded } },
    { id: 'out-1', type: 'exportNode', data: { format: 'JSON', filename: 'r' } },
  ];
  const edges = [{ id: 'e1', source: 'doc-1', target: 'out-1' }];
  const result = runWorkflowForOutput(nodes, edges, 'out-1');
  const outNode = result.find(n => n.id === 'out-1');
  expect(outNode.data.status).toBe('success');
  expect(outNode.data.output.docs[0].name).toBe('내장 문서');
});
```

- [ ] **Step 7: QueryBar.jsx 구현**

```jsx
import { useState } from 'react';

export function QueryBar({ onQuery, busy, error }) {
  const [query, setQuery] = useState('');

  const submit = () => {
    const trimmed = query.trim();
    if (trimmed.length >= 2 && !busy) onQuery(trimmed);
  };

  return (
    <div style={{
      background: '#0b1322', borderBottom: '1px solid #1e2d3d',
      padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0,
    }}>
      <span style={{ fontSize: 12, color: '#64748b', flexShrink: 0 }}>자연어 질의</span>
      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') submit(); }}
        placeholder="예: 부모님 병원 이동을 지원받으려면?"
        style={{
          flex: 1, maxWidth: 560, background: '#111827', color: '#e2e8f0',
          border: '1px solid #1e2d3d', borderRadius: 6, padding: '6px 10px', fontSize: 12,
        }}
      />
      <button onClick={submit} disabled={busy} style={{
        background: busy ? '#1e2d3d' : '#16a34a', color: 'white', border: 'none',
        borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 700,
        cursor: busy ? 'wait' : 'pointer',
      }}>
        {busy ? '검색 중…' : '검색 → 노드 배치'}
      </button>
      {error && <span style={{ fontSize: 11, color: '#f87171' }}>{error}</span>}
    </div>
  );
}
```

- [ ] **Step 8: App.jsx 배선**

import 추가:

```js
import { QueryBar } from './components/QueryBar.jsx';
import { fetchRelations, searchDocsWithDetails } from './data/searchClient.js';
import { placeSearchResults } from './data/relationEdges.js';
```

`App` 안에 상태·핸들러 추가:

```js
const [queryState, setQueryState] = useState({ busy: false, error: '' });

const handleNaturalQuery = useCallback(async (query) => {
  setQueryState({ busy: true, error: '' });
  try {
    const docs = await searchDocsWithDetails(query, 6);
    if (docs.length === 0) {
      setQueryState({ busy: false, error: '검색 결과가 없습니다.' });
      return;
    }
    let relations = [];
    try {
      relations = await fetchRelations(docs.map(doc => doc.serviceId));
    } catch {
      // 관계 조회 실패는 기능 저하 모드: 노드만 배치한다
    }
    const placed = placeSearchResults(docs, relations, nextId);
    setNodes(nds => nds.concat(placed.nodes));
    setEdges(eds => eds.concat(placed.edges));
    setQueryState({ busy: false, error: '' });
  } catch (error) {
    setQueryState({ busy: false, error: error.message });
  }
}, [setNodes, setEdges]);
```

렌더 트리에서 `<Toolbar ... />`(그리고 Task 6의 배너) 아래에 추가:

```jsx
<QueryBar onQuery={handleNaturalQuery} busy={queryState.busy} error={queryState.error} />
```

- [ ] **Step 9: 테스트·빌드 확인**

```powershell
npm test
npm run build
```

Expected: PASS + build 성공

- [ ] **Step 10: 커밋**

```powershell
git add src/data/searchClient.js src/data/relationEdges.js src/components/QueryBar.jsx src/App.jsx src/data/workflowEngine.js src/nodes/ApiDocNode.jsx src/nodes/MergeNode.jsx src/components/NodeProperties.jsx src/data/__tests__
git commit -m "feat(dashboard): 자연어 질의 바 — 검색 노드 자동 배치와 근거 점선 엣지"
```

---

### Task 8: [dashboard] 관계 엣지 근거 표시·승인

**Files:**
- Modify: `dashboard/src/data/relationEdges.js` (`approveRelationEdge` 추가)
- Create: `dashboard/src/components/RelationProperties.jsx`
- Modify: `dashboard/src/App.jsx` (엣지 선택 상태, 패널 분기)
- Test: `dashboard/src/data/__tests__/relationEdges.test.js` (케이스 추가)

**Interfaces:**
- Consumes: Task 7의 엣지 `data.relation` (`{type, evidence, confidence, status}`), `APPROVED_EDGE_STYLE`
- Produces: `approveRelationEdge(edges, edgeId) -> edges` — 해당 엣지를 실선으로 바꾸고 `data.relation.status`를 `'approved'`로 표시 (클라이언트 상태 전용; `reviewed` 승격 영속화는 후속 후보)

- [ ] **Step 1: 실패하는 테스트 추가** — `relationEdges.test.js`에:

```js
import { approveRelationEdge, APPROVED_EDGE_STYLE } from '../relationEdges.js';

describe('approveRelationEdge', () => {
  it('점선 관계 엣지를 실선 승인 엣지로 바꾼다', () => {
    const { nodes, edges } = placeSearchResults(DOCS, RELATIONS, makeIdFactory());
    const approved = approveRelationEdge(edges, edges[0].id);
    expect(approved[0].animated).toBe(false);
    expect(approved[0].style).toEqual(APPROVED_EDGE_STYLE);
    expect(approved[0].data.relation.status).toBe('approved');
    expect(nodes).toHaveLength(2); // 노드는 건드리지 않는다
  });

  it('relation이 없는 일반 엣지는 그대로 둔다', () => {
    const plain = [{ id: 'e1', source: 'a', target: 'b' }];
    expect(approveRelationEdge(plain, 'e1')).toEqual(plain);
  });
});
```

- [ ] **Step 2: 실패 확인** — `npm test` → FAIL (`approveRelationEdge` 없음)

- [ ] **Step 3: 구현** — `relationEdges.js`에 추가:

```js
export function approveRelationEdge(edges, edgeId) {
  return edges.map(edge => {
    if (edge.id !== edgeId || !edge.data?.relation) return edge;
    return {
      ...edge,
      animated: false,
      style: APPROVED_EDGE_STYLE,
      data: { ...edge.data, relation: { ...edge.data.relation, status: 'approved' } },
    };
  });
}
```

- [ ] **Step 4: RelationProperties.jsx 구현**

```jsx
// 선택된 관계 엣지의 근거(evidence)를 보여주고 승인하는 우측 패널.
const TYPE_LABEL = {
  'same-agency': '같은 제공기관',
  'same-domain': '같은 분류체계',
  'param-overlap': '요청 파라미터 공유',
  'io-chain': '응답→요청 연결',
  'llm-suggested': 'LLM 제안',
};

export function RelationProperties({ edge, onApprove }) {
  const rel = edge?.data?.relation;
  if (!rel) return null;

  const approved = rel.status === 'approved';
  return (
    <div style={{
      width: 280, flexShrink: 0, background: '#0b1322', borderLeft: '1px solid #1e2d3d',
      padding: 14, overflowY: 'auto', color: '#e2e8f0', fontSize: 12,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>관계 근거</div>
      <div style={{ color: '#f59e0b', fontWeight: 700, marginBottom: 8 }}>
        {TYPE_LABEL[rel.type] ?? rel.type}
      </div>
      <div style={{ color: '#94a3b8', marginBottom: 4 }}>근거</div>
      <ul style={{ margin: '0 0 10px', paddingLeft: 16 }}>
        {rel.evidence.map(line => <li key={line} style={{ marginBottom: 3 }}>{line}</li>)}
      </ul>
      <div style={{ color: '#94a3b8', marginBottom: 10 }}>
        confidence {rel.confidence} · {rel.status === 'derived' ? '기계 도출' : rel.status}
        {rel.generatedAt ? ` · ${rel.generatedAt}` : ''}
      </div>
      {approved ? (
        <div style={{ color: '#22c55e', fontWeight: 700 }}>✓ 승인됨 — 워크플로우 엣지로 확정</div>
      ) : (
        <button onClick={() => onApprove(edge.id)} style={{
          background: '#16a34a', color: 'white', border: 'none', borderRadius: 6,
          padding: '6px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer',
        }}>이 관계 승인</button>
      )}
    </div>
  );
}
```

- [ ] **Step 5: App.jsx 배선**

import에 `RelationProperties`, `approveRelationEdge` 추가. 상태:

```js
const [selectedEdgeId, setSelectedEdgeId] = useState(null);
```

`onSelectionChange`를 엣지도 받도록 교체:

```js
const onSelectionChange = useCallback(({ nodes: selected, edges: selectedEdges }) => {
  setSelectedNode(selected.length === 1 ? selected[0] : null);
  setSelectedEdgeId(
    selected.length === 0 && selectedEdges.length === 1 ? selectedEdges[0].id : null
  );
}, []);
```

승인 핸들러:

```js
const handleApproveRelation = useCallback((edgeId) => {
  setEdges(eds => approveRelationEdge(eds, edgeId));
}, [setEdges]);
```

렌더에서 우측 패널 분기 — 기존 `<NodeProperties ... />` 자리를:

```jsx
{(() => {
  const selectedEdge = selectedEdgeId ? edges.find(e => e.id === selectedEdgeId) : null;
  return selectedEdge?.data?.relation ? (
    <RelationProperties edge={selectedEdge} onApprove={handleApproveRelation} />
  ) : (
    <NodeProperties node={liveSelectedNode} edges={edges} onUpdateData={handleUpdateNodeData} />
  );
})()}
```

- [ ] **Step 6: 테스트 확인·커밋**

```powershell
npm test
git add src/data/relationEdges.js src/components/RelationProperties.jsx src/App.jsx src/data/__tests__/relationEdges.test.js
git commit -m "feat(dashboard): 관계 엣지 근거 패널과 승인(점선→실선)"
```

참고: flowIO는 엣지의 `label/style/data`를 직렬화하지 않으므로, 내보낸 flow JSON을 다시 가져오면 관계 엣지는 일반 엣지가 된다. 이는 알려진 한계로 dashboard README에 기록한다(Task 10).

---

### Task 9: [dashboard] 조합 제안 패널 (combiner 연동)

**Files:**
- Modify: `dashboard/vite.config.js` (`/combiner` 프록시 추가)
- Create: `dashboard/src/data/composeClient.js`
- Create: `dashboard/src/components/ComposePanel.jsx`
- Modify: `dashboard/src/components/Toolbar.jsx` (`onCompose` 버튼)
- Modify: `dashboard/src/App.jsx` (선택 노드 → 패널 열기)
- Test: `dashboard/src/data/__tests__/composeClient.test.js`

**Interfaces:**
- Consumes: combiner `POST /compose` `{service_ids: string[], question: string}` → 200 `{service_ids, domains, warning, missing, suggestion, truncated, elapsed_ms, model}`; 오류 `{ok: false, error_code, message}` (404 `NO_SERVICES_FOUND`, 503 `UPSTREAM_UNAVAILABLE`). combiner는 순수 api_id와 `openapi_new:` 정식 ID 모두 허용
- Produces: `compose(serviceIds, question) -> Promise<result>`, 실패 시 `ComposeError` (`message`, `errorCode`); `ComposePanel` — 대상 목록, 질문 입력, 제안 본문 표시

- [ ] **Step 1: 실패하는 테스트 작성** — `dashboard/src/data/__tests__/composeClient.test.js`

```js
import { afterEach, describe, expect, it, vi } from 'vitest';
import { compose, ComposeError } from '../composeClient.js';

afterEach(() => vi.unstubAllGlobals());

describe('compose', () => {
  it('성공 응답을 그대로 반환한다', async () => {
    const payload = {
      service_ids: ['openapi_new:15000001'], domains: ['환경기상'],
      warning: null, missing: [], suggestion: '조합 제안 본문',
      truncated: false, elapsed_ms: 1200, model: 'gemma4:e4b',
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
    const result = await compose(['openapi_new:15000001'], '무엇이 가능한가?');
    expect(result.suggestion).toBe('조합 제안 본문');
    expect(fetch).toHaveBeenCalledWith('/combiner/compose', expect.objectContaining({ method: 'POST' }));
  });

  it('오류 계약(error_code/message)을 ComposeError로 변환한다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 503,
      json: async () => ({ ok: false, error_code: 'UPSTREAM_UNAVAILABLE', message: 'Ollama 연결 실패' }),
    }));
    await expect(compose(['1'], 'q')).rejects.toMatchObject({
      errorCode: 'UPSTREAM_UNAVAILABLE', message: 'Ollama 연결 실패',
    });
  });

  it('백엔드 미기동이면 CONNECTION 오류를 던진다', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    await expect(compose(['1'], 'q')).rejects.toBeInstanceOf(ComposeError);
  });
});
```

- [ ] **Step 2: 실패 확인** — `npm test` → FAIL

- [ ] **Step 3: composeClient.js 구현**

```js
// nara_combiner 클라이언트 (vite 프록시 /combiner → 127.0.0.1:8003).

export class ComposeError extends Error {
  constructor(message, errorCode) {
    super(message);
    this.name = 'ComposeError';
    this.errorCode = errorCode;
  }
}

export async function compose(serviceIds, question) {
  let res;
  try {
    res = await fetch('/combiner/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_ids: serviceIds, question }),
    });
  } catch {
    throw new ComposeError('nara_combiner 백엔드에 연결할 수 없습니다.', 'CONNECTION');
  }
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ComposeError(
      payload.message || payload.error || `조합 요청 실패 (HTTP ${res.status})`,
      payload.error_code || String(res.status),
    );
  }
  return payload;
}
```

- [ ] **Step 4: vite.config.js 프록시 추가** — `proxy` 객체에:

```js
'/combiner': {
  target: 'http://127.0.0.1:8003',
  changeOrigin: true,
  rewrite: path => path.replace(/^\/combiner/, ''),
},
```

- [ ] **Step 5: ComposePanel.jsx 구현**

```jsx
import { useState } from 'react';
import { compose } from '../data/composeClient.js';

const DEFAULT_QUESTION = '이 API들을 조합하면 어떤 행정 서비스 계획을 만들 수 있나?';

export function ComposePanel({ targets, onClose }) {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [state, setState] = useState({ loading: false, result: null, error: '' });

  const run = async () => {
    setState({ loading: true, result: null, error: '' });
    try {
      const result = await compose(targets.map(t => t.serviceId), question.trim() || DEFAULT_QUESTION);
      setState({ loading: false, result, error: '' });
    } catch (error) {
      setState({ loading: false, result: null, error: error.message });
    }
  };

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, bottom: 0, width: 380, zIndex: 20,
      background: '#0b1322', borderLeft: '1px solid #1e2d3d', color: '#e2e8f0',
      padding: 16, overflowY: 'auto', fontSize: 12, boxShadow: '-8px 0 32px #00000088',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontWeight: 700, fontSize: 13 }}>⚡ 조합 제안 (nara_combiner)</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}>✕</button>
      </div>

      <div style={{ color: '#94a3b8', marginBottom: 6 }}>대상 API {targets.length}건</div>
      <ul style={{ margin: '0 0 10px', paddingLeft: 16 }}>
        {targets.map(t => <li key={t.serviceId}>{t.name}</li>)}
      </ul>

      <textarea
        value={question}
        onChange={e => setQuestion(e.target.value)}
        rows={3}
        maxLength={500}
        style={{
          width: '100%', boxSizing: 'border-box', background: '#111827', color: '#e2e8f0',
          border: '1px solid #1e2d3d', borderRadius: 6, padding: 8, fontSize: 12, resize: 'vertical',
        }}
      />
      <button onClick={run} disabled={state.loading} style={{
        marginTop: 8, background: state.loading ? '#1e2d3d' : '#16a34a', color: 'white',
        border: 'none', borderRadius: 6, padding: '6px 14px', fontSize: 12, fontWeight: 700,
        cursor: state.loading ? 'wait' : 'pointer',
      }}>
        {state.loading ? 'LLM 제안 생성 중…' : '조합 제안 요청'}
      </button>

      {state.error && (
        <div style={{ marginTop: 10, color: '#f87171' }}>{state.error}</div>
      )}
      {state.result && (
        <div style={{ marginTop: 12 }}>
          {state.result.warning && (
            <div style={{ color: '#f59e0b', marginBottom: 8 }}>⚠ {state.result.warning}</div>
          )}
          {state.result.missing?.length > 0 && (
            <div style={{ color: '#f87171', marginBottom: 8 }}>
              카탈로그에 없는 ID: {state.result.missing.join(', ')}
            </div>
          )}
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{state.result.suggestion}</div>
          <div style={{ marginTop: 10, color: '#475569', fontSize: 10 }}>
            {state.result.model} · {state.result.elapsed_ms}ms{state.result.truncated ? ' · 길이 제한으로 잘림' : ''}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Toolbar·App 배선**

`Toolbar.jsx` props에 `onCompose` 추가, 액션 버튼 줄 맨 앞에:

```jsx
<GhostBtn onClick={onCompose} color="#f59e0b">⚡ 조합 제안</GhostBtn>
```

`App.jsx`:

```js
import { ComposePanel } from './components/ComposePanel.jsx';
import { apiDocMap } from './data/apiDocs.js';

const [composeTargets, setComposeTargets] = useState(null);

const handleOpenCompose = useCallback(() => {
  const targets = nodes
    .filter(node => node.selected && node.type === 'apiDoc')
    .map(node => {
      const doc = node.data?.doc ?? apiDocMap[node.data?.apiId];
      return doc ? { serviceId: doc.serviceId ?? doc.apiId, name: doc.name } : null;
    })
    .filter(Boolean)
    .slice(0, 10); // combiner 계약: 1~10개
  if (targets.length === 0) {
    window.alert('조합할 API 문서 노드를 먼저 선택하세요 (Shift+클릭으로 복수 선택).');
    return;
  }
  setComposeTargets(targets);
}, [nodes]);
```

`<Toolbar ... onCompose={handleOpenCompose} />` 전달. 캔버스를 감싸는 `<div ref={reactFlowWrapper} style={{ flex: 1 }}>`에 `position: 'relative'`를 추가하고 그 안 마지막에:

```jsx
{composeTargets && (
  <ComposePanel targets={composeTargets} onClose={() => setComposeTargets(null)} />
)}
```

- [ ] **Step 7: 테스트·빌드 확인·커밋**

```powershell
npm test
npm run build
git add vite.config.js src/data/composeClient.js src/components/ComposePanel.jsx src/components/Toolbar.jsx src/App.jsx src/data/__tests__/composeClient.test.js
git commit -m "feat(dashboard): 선택 노드 조합 제안 패널 — combiner /compose 연동"
```

---

### Task 10: 통합 기동 스크립트, E2E fixture 테스트, 문서 갱신

**Files:**
- Create: `D:\project\start-all.ps1`
- Test: `dashboard/src/data/__tests__/queryFlow.test.js` (E2E 체인 fixture 재현)
- Modify: `dashboard/README.md`, `plan unified.md`는 Task 1에서 완료 — 여기서는 dashboard README만

**Interfaces:**
- Consumes: Task 3~9의 전 산출물
- Produces: 한 스크립트 기동 + 스펙 8장 완성 기준 충족 증거

- [ ] **Step 1: E2E 체인 fixture 테스트** — `dashboard/src/data/__tests__/queryFlow.test.js`

질의→검색→상세→관계→노드·엣지 배치 체인을 백엔드 계약 fixture로 재현한다 (스펙 6장 시나리오의 단위 재현). Task 7 `searchClient.test.js`의 `SEARCH_PAYLOAD`/`DETAILS`/`RELATIONS_PAYLOAD`/`stubBackend`를 이 파일로 옮겨 `__tests__/fixtures/backendContracts.js`로 공용화한 뒤 양쪽에서 import한다:

```js
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchRelations, searchDocsWithDetails } from '../searchClient.js';
import { placeSearchResults, SUGGESTED_EDGE_STYLE } from '../relationEdges.js';
import { stubBackend } from './fixtures/backendContracts.js';

afterEach(() => vi.unstubAllGlobals());

it('E2E: 자연어 질의 → 노드 배치 → 근거 점선 엣지까지 fixture로 재현된다', async () => {
  stubBackend();
  const docs = await searchDocsWithDetails('대기오염 실시간 측정', 6);
  const relations = await fetchRelations(docs.map(doc => doc.serviceId));
  let n = 0;
  const { nodes, edges } = placeSearchResults(docs, relations, () => `node-e2e-${++n}`);

  expect(nodes).toHaveLength(2);
  expect(nodes.every(node => node.type === 'apiDoc' && node.data.doc)).toBe(true);
  expect(edges).toHaveLength(1);
  expect(edges[0].style).toEqual(SUGGESTED_EDGE_STYLE);
  expect(edges[0].data.relation.type).toBe('io-chain');
  expect(edges[0].data.relation.status).toBe('derived');
  expect(edges[0].data.relation.evidence).toEqual(['응답 sidoName → 요청 sidoName']);
});
```

`npm test`로 통과 확인.

- [ ] **Step 2: start-all.ps1 작성** — `D:\project\start-all.ps1`

```powershell
# Nara 통합 제품 로컬 기동: search(8000) + combiner(8003) + dashboard(5173)
# 사용: .\start-all.ps1 [-ApidataDir <경로>]
param(
  [string]$ApidataDir = (Join-Path $PSScriptRoot 'nara_search(API문서검색)\apidata')
)

if (-not (Test-Path $ApidataDir)) {
  Write-Warning "apidata 디렉터리가 없습니다: $ApidataDir"
  Write-Warning "검색·카탈로그가 빈 상태로 뜹니다. nara_crawler 산출물 경로를 -ApidataDir로 지정하세요."
}

$search    = Join-Path $PSScriptRoot 'nara_search(API문서검색)'
$combiner  = Join-Path $PSScriptRoot 'nara_combiner(API문서조합기)'
$dashboard = Join-Path $PSScriptRoot 'nara_dashboard(API관계대시보드)'

Start-Process powershell -WorkingDirectory $search -ArgumentList '-NoExit', '-Command',
  "`$env:NARA_SEARCH_APIDATA_DIR='$ApidataDir'; python -m uvicorn backend.main:app --port 8000"
Start-Process powershell -WorkingDirectory $combiner -ArgumentList '-NoExit', '-Command',
  "`$env:NARA_DATA_DIR='$ApidataDir'; python .\app\main.py"
Start-Process powershell -WorkingDirectory $dashboard -ArgumentList '-NoExit', '-Command', 'npm run dev'

Write-Host ''
Write-Host '기동 완료 (각 창에서 로그 확인):'
Write-Host '  검색     http://127.0.0.1:8000/health'
Write-Host '  조합     http://127.0.0.1:8003/health'
Write-Host '  대시보드 http://localhost:5173'
```

스모크: `.\start-all.ps1` 실행 후 세 URL이 응답하는지 확인하고 창을 닫는다. (combiner의 실제 기동 인자·경로가 다르면 combiner README의 실행 명령에 맞춰 수정한다.)

- [ ] **Step 3: dashboard README 갱신**

`dashboard/README.md`의 "데이터 모드 (local)" 섹션을 교체:

```markdown
## 데이터 모드 (backend)

카탈로그는 `nara_search` 백엔드에서 런타임 로딩한다 (`GET /api/catalog`,
vite 프록시 → 127.0.0.1:8000). 빌드 타임 eager 번들은 제거되었다.

- 백엔드 미기동: 상단에 연결 오류 배너 + 빈 카탈로그로 동작 (앱은 죽지 않음)
- **자연어 질의 바**: `/api/search`(FAISS+BM25) → 결과를 apiDoc 노드로 자동 배치,
  `/api/relations` → 노드 간 근거 점선 엣지 표시. 엣지 클릭 → 근거 확인·승인(실선 확정)
- **⚡ 조합 제안**: apiDoc 노드를 선택하고 툴바 버튼 → `nara_combiner /compose`
  제안을 우측 패널에 표시 (프록시 `/combiner` → 127.0.0.1:8003)
- 전체 기동: 저장소 루트의 `..\start-all.ps1`

알려진 한계: flow JSON 내보내기는 엣지의 관계 메타데이터(label/근거)를 직렬화하지
않으므로, 가져온 관계 엣지는 일반 엣지가 된다.
```

- [ ] **Step 4: 최종 전체 검증**

```powershell
cd "D:\project\nara_search(API문서검색)"; python -m pytest tests -v
cd "D:\project\nara_dashboard(API관계대시보드)"; npm test; npm run build
cd "D:\project\nara_combiner(API문서조합기)"; python -m pytest tests -v
```

Expected: 모두 PASS (combiner는 변경이 README뿐이므로 기존 13개 그대로)

- [ ] **Step 5: 커밋**

```powershell
cd D:\project
git add start-all.ps1 "nara_dashboard(API관계대시보드)/README.md" "nara_dashboard(API관계대시보드)/src/data/__tests__"
git commit -m "feat: 통합 기동 스크립트와 E2E fixture 테스트, 대시보드 문서 갱신"
```
