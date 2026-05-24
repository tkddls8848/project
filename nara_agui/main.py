"""AGUI 데모 백엔드.

핵심: NDJSON envelope 스트리밍으로 에이전트의 사고 과정(step) + 결과 레이아웃(layout)
+ 답변 토큰(token)을 실시간 전송. LLM·검색엔진 없이 Mock 데이터로 패턴 자체만 시연.
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Nara AGUI Demo", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"])


class SearchRequest(BaseModel):
    query: str


def classify(query: str) -> Literal["single", "grid", "flow"]:
    """휴리스틱 분류기. 실제 프로젝트에선 Ollama gemma4:e4b 등으로 교체."""
    flow_keys = ["절차", "순서", "방법", "단계", "하려면", "따려면", "어떻게"]
    grid_keys = ["뭐 있", "종류", "리스트", "목록", "비교", "어떤"]
    if any(k in query for k in flow_keys):
        return "flow"
    if any(k in query for k in grid_keys):
        return "grid"
    return "single"


MOCK_SINGLE = {
    "service_id": "DEMO-S1",
    "name": "외교부_여행경보제도",
    "agency": "외교부",
    "description": "특정 국가(지역) 여행·체류 시 위험수준과 안전대책을 안내하는 제도. "
                   "1단계(유의)~4단계(금지)로 구분하여 발령.",
    "endpoints": [{"method": "GET", "path": "/getTravelWarningListV3", "desc": "여행경보 목록 조회"}],
}

MOCK_GRID = [
    {"service_id": "DEMO-G1", "name": "기상청_단기예보", "agency": "기상청", "category": "기상"},
    {"service_id": "DEMO-G2", "name": "기상청_생활기상지수", "agency": "기상청", "category": "기상"},
    {"service_id": "DEMO-G3", "name": "환경부_미세먼지정보", "agency": "환경부", "category": "환경"},
    {"service_id": "DEMO-G4", "name": "기상청_초단기실황", "agency": "기상청", "category": "기상"},
    {"service_id": "DEMO-G5", "name": "기상청_특보정보", "agency": "기상청", "category": "기상"},
    {"service_id": "DEMO-G6", "name": "환경부_대기질예보", "agency": "환경부", "category": "환경"},
]

MOCK_FLOW = {
    "nodes": [
        {"id": "DEMO-F1", "label": "체류자격 조회", "agency": "출입국외국인청", "step": 1},
        {"id": "DEMO-F2", "label": "운전면허시험 접수", "agency": "도로교통공단", "step": 2},
        {"id": "DEMO-F3", "label": "시험결과 조회", "agency": "도로교통공단", "step": 3},
        {"id": "DEMO-F4", "label": "면허증 발급", "agency": "도로교통공단", "step": 4},
    ],
    "edges": [
        {"from": "DEMO-F1", "to": "DEMO-F2", "label": "체류자격 확인 후"},
        {"from": "DEMO-F2", "to": "DEMO-F3", "label": "시험 응시 후"},
        {"from": "DEMO-F3", "to": "DEMO-F4", "label": "합격 후"},
    ],
}

ANSWERS = {
    "single": "외교부의 여행경보제도 API에 해당 정보가 있습니다. "
              "/getTravelWarningListV3 엔드포인트로 국가별 경보 단계를 조회할 수 있습니다.",
    "grid": "관련 API 6종을 찾았습니다. 기상청·환경부에서 단기예보부터 미세먼지·생활지수까지 "
            "다양한 환경 데이터를 제공하고 있습니다.",
    "flow": "외국인 운전면허 절차는 4단계입니다. 체류자격 확인 → 시험 접수 → 결과 조회 → "
            "면허증 발급 순서이며, 각 단계마다 호출 가능한 공공 API가 매핑되어 있습니다.",
}


def envelope(event_type: str, payload: dict) -> str:
    return json.dumps(
        {"type": event_type, "ts": int(time.time() * 1000), "payload": payload},
        ensure_ascii=False,
    ) + "\n"


async def stream_search(query: str):
    """AGUI 표준 envelope 시퀀스: step* → layout → token* → done."""
    # 1. 쿼리 분석
    yield envelope("step", {"name": "query_analysis", "status": "running"})
    await asyncio.sleep(0.3)
    yield envelope("step", {"name": "query_analysis", "status": "done"})

    # 2. 쿼리 분류
    yield envelope("step", {"name": "query_classify", "status": "running"})
    await asyncio.sleep(0.4)
    kind = classify(query)
    yield envelope("step", {"name": "query_classify", "status": "done", "detail": f"{kind} 으로 판단"})

    # 3. 벡터 검색 (실제로는 FAISS 호출이 들어갈 자리)
    yield envelope("step", {"name": "vector_search", "status": "running"})
    await asyncio.sleep(0.5)
    candidate_count = {"single": 1, "grid": 6, "flow": 4}[kind]
    yield envelope("step", {"name": "vector_search", "status": "done", "detail": f"{candidate_count}건 후보"})

    # 4. 레이아웃 통보 — Generative UI 핵심 이벤트
    if kind == "single":
        payload = {"kind": "single", "item": MOCK_SINGLE}
    elif kind == "grid":
        payload = {"kind": "grid", "items": MOCK_GRID}
    else:
        payload = {"kind": "flow", **MOCK_FLOW}
    yield envelope("layout", payload)

    # 5. 답변 토큰 스트리밍
    yield envelope("step", {"name": "answer_generation", "status": "running"})
    for ch in ANSWERS[kind]:
        await asyncio.sleep(0.02)
        yield envelope("token", {"data": ch})
    yield envelope("step", {"name": "answer_generation", "status": "done"})

    # 6. 완료
    yield envelope("done", {})


@app.post("/search")
async def search(req: SearchRequest):
    return StreamingResponse(
        stream_search(req.query),
        media_type="application/x-ndjson",
    )


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "service": "nara-agui-demo"}
