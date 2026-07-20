"""Convert a completed design result into a nara-dashboard flow JSON.

Target contract: nara_dashboard src/data/flowIO.js (format "nara-dashboard-flow",
version 1). Edges only serialize id/source/target there, so relation evidence
travels inside node data under nara* keys, which sanitizeNodeData preserves.
See docs/flow_export_plan.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .schemas import DesignResponse

FLOW_FORMAT = "nara-dashboard-flow"
FLOW_VERSION = 1
DEFAULT_FLOW_NAME = "나라 에이전트 결과"
FLOW_NAME_MAX = 60

# Same grid the dashboard's placeSearchResults uses.
GRID_ORIGIN_X, GRID_ORIGIN_Y = 80, 120
GRID_STEP_X, GRID_STEP_Y = 280, 240
GRID_COLUMNS = 3


def _api_id(service_id: str) -> str:
    return service_id.split(":")[-1]


def _doc_title(details: list[dict[str, Any]], service_id: str) -> str:
    for doc in details:
        if str(doc.get("service_id", "")).strip() == service_id:
            return str(doc.get("name") or doc.get("title") or "").strip()
    return ""


def _relation_note(relation: dict[str, Any]) -> str:
    evidence = "; ".join(str(item) for item in relation.get("evidence") or [])
    note = str(relation.get("type") or "relation")
    return f"{note}: {evidence}" if evidence else note


def design_to_flow(
    result: DesignResponse,
    *,
    name: str | None = None,
    exported_at: datetime | None = None,
) -> dict[str, Any]:
    selected = result.selected_service_ids
    selected_set = set(selected)
    relations = [
        rel for rel in (result.relations or {}).get("relations") or []
        if rel.get("source") in selected_set and rel.get("target") in selected_set
    ]

    notes_by_id: dict[str, list[str]] = {sid: [] for sid in selected}
    for rel in relations:
        note = _relation_note(rel)
        for endpoint in (str(rel.get("source")), str(rel.get("target"))):
            notes_by_id[endpoint].append(note)

    selection_note = f"질문 '{result.query}'에 대한 에이전트 선택 결과"
    if result.warnings:
        selection_note += " · 경고: " + " / ".join(result.warnings)

    nodes = [
        {
            "id": sid,
            "type": "apiDoc",
            "position": {
                "x": GRID_ORIGIN_X + (index % GRID_COLUMNS) * GRID_STEP_X,
                "y": GRID_ORIGIN_Y + (index // GRID_COLUMNS) * GRID_STEP_Y,
            },
            "data": {
                "apiId": _api_id(sid),
                "naraTitle": _doc_title(result.details, sid),
                "naraSelectionNote": selection_note,
                "naraRelationNotes": notes_by_id[sid],
            },
        }
        for index, sid in enumerate(selected)
    ]
    edges = [
        {
            "id": str(rel.get("id")
                      or f"rel:{rel.get('type')}:{rel.get('source')}:{rel.get('target')}"),
            "source": str(rel.get("source")),
            "target": str(rel.get("target")),
        }
        for rel in relations
    ]

    flow_name = (name or result.query or "").strip()[:FLOW_NAME_MAX] or DEFAULT_FLOW_NAME
    stamp = exported_at or datetime.now(timezone.utc)
    return {
        "format": FLOW_FORMAT,
        "version": FLOW_VERSION,
        "name": flow_name,
        "exported_at": stamp.isoformat(),
        "nodes": nodes,
        "edges": edges,
    }


__all__ = ["design_to_flow", "FLOW_FORMAT", "FLOW_VERSION"]
