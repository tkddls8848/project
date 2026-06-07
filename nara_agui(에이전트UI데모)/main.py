"""AGUI 백엔드 - 실제 apidata 기반 키워드 검색 + Ollama 분류/답변."""
import json
import time
from pathlib import Path
from typing import AsyncIterator, Literal

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
APIDATA_DIR = BASE_DIR.parent / "nara_dashboard" / "apidata"

app = FastAPI(title="Nara AGUI", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"])

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma4:e4b"


# ── Prompts ───────────────────────────────────────────────────────────────────

_P: dict[str, str] = {
    name: (BASE_DIR / "prompts" / f"{name}.txt").read_text(encoding="utf-8")
    for name in ("classify", "flow_order", "answer")
}


# ── Data loading ──────────────────────────────────────────────────────────────

def _parse_doc(raw: dict) -> dict | None:
    info = raw.get("info", {})
    swagger_info = raw.get("swagger_json", {}).get("info", {})
    name = (info.get("목록명") or swagger_info.get("title") or "").strip()
    if not name:
        return None
    return {
        "apiId":       raw.get("api_id", ""),
        "name":        name,
        "provider":    (info.get("제공기관") or "").strip(),
        "category":    (info.get("분류체계") or "").strip(),
        "keywords":    (info.get("키워드") or "").strip(),
        "description": (info.get("설명") or swagger_info.get("description", "")).strip(),
        "endpoints": [
            {"method": ep.get("method", "GET"), "path": ep.get("path", ""), "desc": ep.get("description", "")}
            for ep in raw.get("endpoints", [])
        ],
    }

def _load_docs() -> list[dict]:
    if not APIDATA_DIR.exists():
        return []
    docs = []
    for f in APIDATA_DIR.glob("*.json"):
        try:
            doc = _parse_doc(json.loads(f.read_text(encoding="utf-8")))
            if doc:
                docs.append(doc)
        except Exception:
            pass
    return docs

API_DOCS: list[dict] = _load_docs()


# ── Search ────────────────────────────────────────────────────────────────────

_WEIGHTS = [("name", 5), ("keywords", 4), ("category", 3), ("provider", 2), ("description", 2)]

def _score(doc: dict, terms: list[str]) -> int:
    score = 0
    for field, w in _WEIGHTS:
        text = doc.get(field, "").lower()
        for t in terms:
            if t in text:
                score += w
    return score

def search_docs(query: str, n: int = 6) -> list[dict]:
    terms = [t.lower() for t in query.split() if t]
    if not terms:
        return API_DOCS[:n]
    ranked = sorted(
        ((doc, _score(doc, terms)) for doc in API_DOCS),
        key=lambda x: x[1], reverse=True,
    )
    return [doc for doc, s in ranked if s > 0][:n]


# ── Ollama helpers ────────────────────────────────────────────────────────────

async def _ollama_generate(prompt: str, timeout: float = 20.0) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

async def _ollama_stream(prompt: str) -> AsyncIterator[str]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST", f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
        ) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    token = json.loads(line).get("response", "")
                    if token:
                        yield token
                except Exception:
                    pass


# ── Classify ──────────────────────────────────────────────────────────────────

def _classify_fallback(query: str) -> Literal["single", "grid", "flow"]:
    if any(k in query for k in ["절차", "순서", "방법", "단계", "하려면", "따려면", "어떻게"]):
        return "flow"
    if any(k in query for k in ["뭐 있", "종류", "리스트", "목록", "비교", "어떤"]):
        return "grid"
    return "single"

async def classify(query: str) -> Literal["single", "grid", "flow"]:
    try:
        answer = (await _ollama_generate(_P["classify"].format(query=query))).lower()
        if "flow" in answer:
            return "flow"
        if "grid" in answer:
            return "grid"
        return "single"
    except Exception:
        return _classify_fallback(query)


# ── Flow ordering ─────────────────────────────────────────────────────────────

async def build_flow(query: str, docs: list[dict]) -> tuple[list, list]:
    docs_json = json.dumps(
        [{"apiId": d["apiId"], "name": d["name"], "provider": d["provider"], "description": d["description"][:150]}
         for d in docs],
        ensure_ascii=False,
    )
    try:
        raw = await _ollama_generate(_P["flow_order"].format(query=query, docs_json=docs_json), timeout=25.0)
        start, end = raw.find("["), raw.rfind("]") + 1
        steps: list[dict] = json.loads(raw[start:end])
    except Exception:
        steps = [
            {"step": i + 1, "id": d["apiId"], "label": d["name"], "agency": d["provider"], "transition": "다음 단계"}
            for i, d in enumerate(docs[:4])
        ]

    nodes = [
        {"id": s.get("id", f"step-{s['step']}"), "label": s.get("label", ""), "agency": s.get("agency", ""), "step": s["step"]}
        for s in steps
    ]
    edges = [
        {"from": steps[i].get("id", ""), "to": steps[i + 1].get("id", ""), "label": steps[i].get("transition", "")}
        for i in range(len(steps) - 1)
    ]
    return nodes, edges


# ── Envelope ──────────────────────────────────────────────────────────────────

def envelope(event_type: str, payload: dict) -> str:
    return json.dumps(
        {"type": event_type, "ts": int(time.time() * 1000), "payload": payload},
        ensure_ascii=False,
    ) + "\n"


# ── Main stream ───────────────────────────────────────────────────────────────

async def stream_search(query: str):
    # 1. 분류 (Ollama 호출 — 실제 대기 발생)
    yield envelope("step", {"name": "query_analysis", "status": "running"})
    kind = await classify(query)
    yield envelope("step", {"name": "query_analysis", "status": "done"})
    yield envelope("step", {"name": "query_classify", "status": "done", "detail": f"{kind} 으로 판단"})

    # 2. 키워드 검색
    yield envelope("step", {"name": "vector_search", "status": "running"})
    n = {"single": 1, "grid": 6, "flow": 6}[kind]
    docs = search_docs(query, n=n)
    yield envelope("step", {"name": "vector_search", "status": "done", "detail": f"{len(docs)}건 검색"})

    # 3. 레이아웃 페이로드
    if not docs:
        layout_payload: dict = {
            "kind": "single",
            "item": {"service_id": "", "name": "결과 없음", "agency": "", "description": "관련 API를 찾지 못했습니다.", "endpoints": []},
        }
    elif kind == "single":
        d = docs[0]
        layout_payload = {
            "kind": "single",
            "item": {
                "service_id": d["apiId"],
                "name": d["name"],
                "agency": d["provider"],
                "description": d["description"],
                "endpoints": [{"method": ep["method"], "path": ep["path"], "desc": ep["desc"]} for ep in d["endpoints"][:3]],
            },
        }
    elif kind == "grid":
        layout_payload = {
            "kind": "grid",
            "items": [
                {
                    "service_id": d["apiId"],
                    "name": d["name"],
                    "agency": d["provider"],
                    "category": d["category"].split(" - ")[0] if " - " in d["category"] else d["category"],
                }
                for d in docs
            ],
        }
    else:  # flow
        yield envelope("step", {"name": "flow_ordering", "status": "running"})
        nodes, edges = await build_flow(query, docs)
        yield envelope("step", {"name": "flow_ordering", "status": "done"})
        layout_payload = {"kind": "flow", "nodes": nodes, "edges": edges}

    yield envelope("layout", layout_payload)

    # 4. 답변 생성 (Ollama 스트리밍)
    yield envelope("step", {"name": "answer_generation", "status": "running"})
    docs_summary = "\n".join(
        f"- {d['name']} ({d['provider']}): {d['description'][:120]}" for d in docs
    )
    answer_prompt = _P["answer"].format(query=query, kind=kind, docs_summary=docs_summary)
    try:
        async for token in _ollama_stream(answer_prompt):
            yield envelope("token", {"data": token})
    except Exception:
        for ch in f"관련 API {len(docs)}건을 찾았습니다.":
            yield envelope("token", {"data": ch})
    yield envelope("step", {"name": "answer_generation", "status": "done"})

    yield envelope("done", {})


# ── Routes ────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str

@app.post("/search")
async def search(req: SearchRequest):
    return StreamingResponse(stream_search(req.query), media_type="application/x-ndjson")

@app.get("/")
def index():
    return FileResponse(BASE_DIR / "index.html")

@app.get("/health")
def health():
    return {"ok": True, "service": "nara-agui", "docs_loaded": len(API_DOCS)}
