"""Render a completed design result as a one-page MVP presentation summary.

The image is an SVG built deterministically from the same ``DesignResponse``
the text plan comes from, so it repeats what Nara already returned and never
adds a claim of its own. SVG keeps the renderer inside the standard library
and stays insertable into slide tools as a vector image.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .schemas import CriticReport, DesignResponse

CANVAS_W, CANVAS_H = 1280, 720
HEADER_H, FOOTER_TOP = 96, 660
MARGIN = 40
LEFT_W, RIGHT_X = 520, 592
RIGHT_W = CANVAS_W - RIGHT_X - MARGIN

CARD_H, CARD_GAP = 100, 12
CARDS_TOP = 152
MAX_CARDS = 3
MAX_RELATION_LINES = 4
PLAN_LINE_H = 22
WARNING_LINE_H = 18
MAX_WARNING_LINES = 3

# The palette mirrors static/styles.css so the exported page reads as the
# same product as the workbench it came from.
INK, MUTED, LINE = "#17241e", "#66746e", "#dce3de"
SURFACE, PAPER = "#ffffff", "#f6f8f6"
ACCENT, ACCENT_DARK = "#0c805b", "#07513a"
WARNING, DANGER = "#b96313", "#a43c34"

CRITIC_LABELS = {
    "pass": "근거 검증 통과",
    "evidence_gap": "근거 부족",
    "contradiction": "근거 모순",
    "failed": "검증 실패 (결과는 유효)",
    "skipped": "검증 생략",
}
CRITIC_COLORS = {
    "pass": ACCENT_DARK,
    "evidence_gap": WARNING,
    "contradiction": DANGER,
    "failed": MUTED,
    "skipped": MUTED,
}
SAFETY_NOTE = "실제 행정 처리나 외부 시스템 변경을 수행하지 않는 검토용 요약입니다."
NO_PLAN_NOTE = "계획 생성을 생략했거나 계획 초안을 만들지 못했습니다."


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _is_cjk(char: str) -> bool:
    return bool(char) and ord(char) > 0x2E7F


def _break_point(line: str, following: str) -> int:
    """Where to cut an overflowing line so ASCII tokens stay whole.

    Hangul wraps between any two glyphs, but a service_id or an endpoint path
    must not be split mid-token, so the cut backs up to the last space when the
    overflow lands inside a Latin run.
    """
    if _is_cjk(following) or following == " " or _is_cjk(line[-1]):
        return len(line)
    floor = int(len(line) * 0.6)
    for index in range(len(line) - 1, floor, -1):
        if line[index - 1] == " " or _is_cjk(line[index]):
            return index
    return len(line)


def _width(text: str) -> float:
    """Approximate rendered width in em units.

    SVG carries no text metrics, so a Hangul/CJK glyph counts as one em and a
    Latin glyph as roughly half. Wrapping only needs to stay inside its box.
    """
    return sum(1.0 if _is_cjk(char) else 0.55 for char in text)


def _ellipsize(text: str, max_em: float) -> str:
    text = " ".join(str(text or "").split())
    if _width(text) <= max_em:
        return text
    kept: list[str] = []
    budget = max_em - 1.0
    for char in text:
        if _width("".join(kept) + char) > budget:
            break
        kept.append(char)
    return "".join(kept).rstrip() + "…"


def _wrap(text: str, max_em: float, max_lines: int) -> tuple[list[str], bool]:
    """Break text into at most ``max_lines`` lines that fit ``max_em``."""
    lines: list[str] = []
    for segment in str(text or "").splitlines():
        segment = segment.rstrip()
        if not segment:
            # Keep paragraph breaks, but never open the block with blank lines.
            if lines and lines[-1]:
                lines.append("")
            continue
        current = ""
        for char in segment:
            if _width(current + char) > max_em and current:
                cut = _break_point(current, char)
                lines.append(current[:cut].rstrip())
                current = (current[cut:] + char).lstrip(" ")
            else:
                current += char
        if current:
            lines.append(current)
    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = _ellipsize(lines[-1], max_em - 1.0) + " …"
    return lines, truncated


def _plan_text(plan: dict[str, Any] | None) -> str:
    """Flatten the combiner suggestion into slide-readable plain lines."""
    suggestion = str((plan or {}).get("suggestion") or "").strip()
    if not suggestion:
        return ""
    cleaned: list[str] = []
    for raw in suggestion.splitlines():
        line = raw.strip().replace("**", "").replace("`", "")
        while line.startswith("#"):
            line = line[1:].lstrip()
        if line.startswith(("- ", "* ")):
            line = "• " + line[2:]
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _doc_field(detail: dict[str, Any], *names: str) -> str:
    for name in names:
        value = str(detail.get(name) or "").strip()
        if value:
            return value
    return ""


def _detail_for(details: list[dict[str, Any]], service_id: str) -> dict[str, Any]:
    for doc in details:
        if str(doc.get("service_id", "")).strip() == service_id:
            return doc
    return {}


def _relation_lines(result: DesignResponse) -> list[str]:
    selected = set(result.selected_service_ids)
    lines: list[str] = []
    for relation in (result.relations or {}).get("relations") or []:
        if relation.get("source") not in selected or relation.get("target") not in selected:
            continue
        evidence = "; ".join(str(item) for item in relation.get("evidence") or [])
        label = f"{_api_id(str(relation.get('source')))} ↔ {_api_id(str(relation.get('target')))}"
        note = f"{label} · {relation.get('type') or 'relation'}"
        lines.append(f"{note} · {evidence}" if evidence else note)
    return lines


def _api_id(service_id: str) -> str:
    return service_id.split(":")[-1]


def _text(x: float, y: float, content: str, cls: str, **attrs: str) -> str:
    extra = "".join(f' {key.replace("_", "-")}="{value}"' for key, value in attrs.items())
    return f'<text x="{x}" y="{y}" class="{cls}"{extra}>{_escape(content)}</text>'


def _rect(x: float, y: float, w: float, h: float, fill: str, stroke: str | None = None,
          radius: float = 8) -> str:
    stroke_attr = f' stroke="{stroke}"' if stroke else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}"{stroke_attr}/>')


def _header(result: DesignResponse, critic: CriticReport | None, doc_count: int,
            relation_count: int) -> list[str]:
    verdict = critic.verdict if critic else "skipped"
    badge_label = CRITIC_LABELS.get(verdict, verdict)
    badge_color = CRITIC_COLORS.get(verdict, MUTED)
    badge_w = _width(badge_label) * 12 + 24
    badge_x = CANVAS_W - MARGIN - badge_w
    title = _ellipsize(result.query or "서비스 계획 요약", (badge_x - 132) / 24)
    return [
        _rect(0, 0, CANVAS_W, HEADER_H, SURFACE, radius=0),
        f'<line x1="0" y1="{HEADER_H}" x2="{CANVAS_W}" y2="{HEADER_H}" stroke="{LINE}"/>',
        _rect(MARGIN, 28, 40, 40, ACCENT, radius=8),
        _text(MARGIN + 20, 55, "N", "mark", text_anchor="middle"),
        _text(MARGIN + 56, 45, title, "title"),
        _text(MARGIN + 56, 70, "MVP 1페이지 요약 · Nara Hermes Orchestrator 읽기 전용 계획 초안",
              "subtitle"),
        _rect(badge_x, 26, badge_w, 24, "#eef2ef", radius=6),
        _text(badge_x + badge_w / 2, 42, badge_label, "badge", fill=badge_color,
              text_anchor="middle"),
        _text(CANVAS_W - MARGIN, 70, f"선택 문서 {doc_count}개 · 관계 근거 {relation_count}건",
              "meta", text_anchor="end"),
    ]


def _document_cards(result: DesignResponse) -> list[str]:
    parts = [_text(MARGIN, 132, "선택한 공공 API", "section")]
    selected = result.selected_service_ids[:MAX_CARDS]
    if not selected:
        parts.append(_rect(MARGIN, CARDS_TOP, LEFT_W, CARD_H, SURFACE, LINE))
        parts.append(_text(MARGIN + 20, CARDS_TOP + 56, "선택된 문서가 없습니다.", "empty"))
        return parts

    for index, service_id in enumerate(selected):
        top = CARDS_TOP + index * (CARD_H + CARD_GAP)
        detail = _detail_for(result.details, service_id)
        name = _doc_field(detail, "name", "title") or service_id
        agency = _doc_field(detail, "provider_agency_name", "provider", "agency")
        category = _doc_field(detail, "category", "domain")
        endpoints = (detail.get("counts") or {}).get("endpoints")
        facts = " · ".join(
            item for item in (
                agency,
                category,
                f"엔드포인트 {endpoints}개" if isinstance(endpoints, int) else "",
            ) if item
        ) or "상세 메타데이터가 없습니다."
        parts += [
            _rect(MARGIN, top, LEFT_W, CARD_H, SURFACE, LINE),
            _rect(MARGIN, top, 4, CARD_H, ACCENT, radius=2),
            _text(MARGIN + 20, top + 24, f"0{index + 1}", "card-index"),
            _text(MARGIN + 20, top + 50, _ellipsize(name, (LEFT_W - 40) / 16), "card-title"),
            _text(MARGIN + 20, top + 72, _ellipsize(facts, (LEFT_W - 40) / 12), "card-facts"),
            _text(MARGIN + 20, top + 90, service_id, "card-id"),
        ]
    return parts


def _relation_block(result: DesignResponse) -> list[str]:
    # Follow the cards that were actually drawn so a one-document result does
    # not open with a hole where the missing cards would have been.
    card_count = max(len(result.selected_service_ids[:MAX_CARDS]), 1)
    top = CARDS_TOP + card_count * (CARD_H + CARD_GAP) + 20
    lines = _relation_lines(result)
    parts = [_text(MARGIN, top + 12, "문서 관계 근거", "section")]
    if not lines:
        parts.append(_text(MARGIN, top + 38, "문서가 한 개이거나 확인된 관계 근거가 없습니다.",
                           "empty-line"))
        return parts
    for index, line in enumerate(lines[:MAX_RELATION_LINES]):
        y = top + 38 + index * 22
        parts += [
            f'<circle cx="{MARGIN + 4}" cy="{y - 4}" r="3" fill="{ACCENT}"/>',
            _text(MARGIN + 16, y, _ellipsize(line, (LEFT_W - 16) / 12), "relation"),
        ]
    if len(lines) > MAX_RELATION_LINES:
        y = top + 38 + MAX_RELATION_LINES * 22
        parts.append(_text(MARGIN + 16, y, f"외 {len(lines) - MAX_RELATION_LINES}건", "empty-line"))
    return parts


def _warning_block(warnings: list[str]) -> tuple[list[str], float]:
    """Draw warnings bottom-aligned; return the drawn parts and the block top."""
    if not warnings:
        return [], FOOTER_TOP - 20
    lines, _ = _wrap(" · ".join(warnings), (RIGHT_W - 40) / 11, MAX_WARNING_LINES)
    height = 24 + len(lines) * WARNING_LINE_H
    top = FOOTER_TOP - 20 - height
    parts = [
        _rect(RIGHT_X, top, RIGHT_W, height, "#fff4e6", radius=6),
        _rect(RIGHT_X, top, 3, height, WARNING, radius=1),
        *[
            _text(RIGHT_X + 16, top + 22 + index * WARNING_LINE_H, line, "warning")
            for index, line in enumerate(lines)
        ],
    ]
    return parts, top


def _plan_block(result: DesignResponse, warning_top: float) -> list[str]:
    height = warning_top - 12 - CARDS_TOP
    parts = [
        _text(RIGHT_X, 132, "서비스 계획 초안", "section"),
        _rect(RIGHT_X, CARDS_TOP, RIGHT_W, height, SURFACE, LINE),
    ]
    text = _plan_text(result.plan)
    if not text:
        parts.append(_text(RIGHT_X + 20, CARDS_TOP + 40, NO_PLAN_NOTE, "empty"))
        return parts

    max_lines = max(int((height - 52) // PLAN_LINE_H), 1)
    lines, truncated = _wrap(text, (RIGHT_W - 40) / 13, max_lines)
    parts += [
        _text(RIGHT_X + 20, CARDS_TOP + 34 + index * PLAN_LINE_H, line, "plan")
        for index, line in enumerate(lines)
    ]
    if truncated:
        parts.append(_text(RIGHT_X + RIGHT_W - 20, CARDS_TOP + height - 16,
                           "전체 계획 본문은 실행 결과 화면에서 확인하세요.", "note",
                           text_anchor="end"))
    return parts


def _footer(stamp: datetime) -> list[str]:
    when = stamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return [
        _rect(0, FOOTER_TOP, CANVAS_W, CANVAS_H - FOOTER_TOP, SURFACE, radius=0),
        f'<line x1="0" y1="{FOOTER_TOP}" x2="{CANVAS_W}" y2="{FOOTER_TOP}" stroke="{LINE}"/>',
        _text(MARGIN, FOOTER_TOP + 36, SAFETY_NOTE, "footer"),
        _text(CANVAS_W - MARGIN, FOOTER_TOP + 36, f"생성 {when}", "footer", text_anchor="end"),
    ]


STYLE = f"""
    text {{ font-family:"Pretendard","Noto Sans KR","Malgun Gothic",sans-serif; fill:{INK}; }}
    .mark {{ font-size:22px; font-weight:800; fill:{SURFACE}; }}
    .title {{ font-size:24px; font-weight:800; letter-spacing:-0.5px; }}
    .subtitle {{ font-size:12px; fill:{MUTED}; }}
    .badge {{ font-size:12px; font-weight:700; }}
    .meta {{ font-size:12px; fill:{MUTED}; }}
    .section {{ font-size:13px; font-weight:800; fill:{ACCENT_DARK}; letter-spacing:0.4px; }}
    .card-index {{ font-size:11px; font-weight:700; fill:{ACCENT}; font-family:ui-monospace,monospace; }}
    .card-title {{ font-size:16px; font-weight:700; }}
    .card-facts {{ font-size:12px; fill:{MUTED}; }}
    .card-id {{ font-size:11px; fill:{MUTED}; font-family:ui-monospace,monospace; }}
    .relation {{ font-size:12px; fill:#314239; }}
    .plan {{ font-size:13px; fill:#314239; }}
    .note {{ font-size:11px; fill:{MUTED}; }}
    .empty {{ font-size:13px; fill:{MUTED}; }}
    .empty-line {{ font-size:12px; fill:{MUTED}; }}
    .warning {{ font-size:11px; fill:#7b4b19; }}
    .footer {{ font-size:11px; fill:{MUTED}; }}
"""


def design_to_summary_svg(
    result: DesignResponse,
    *,
    critic: CriticReport | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Render the finished result as a one-page 16:9 summary image."""
    stamp = generated_at or datetime.now(timezone.utc)
    relation_count = len(_relation_lines(result))
    warning_parts, warning_top = _warning_block(list(result.warnings))
    body = [
        _rect(0, 0, CANVAS_W, CANVAS_H, PAPER, radius=0),
        *_header(result, critic, len(result.selected_service_ids), relation_count),
        *_document_cards(result),
        *_relation_block(result),
        *_plan_block(result, warning_top),
        *warning_parts,
        *_footer(stamp),
    ]
    title = _escape(_ellipsize(result.query or "서비스 계획 요약", 40))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
        f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" role="img" aria-label="{title} 서비스 계획 1페이지 요약">'
        f"<title>{title} · MVP 1페이지 요약</title>"
        f"<style>{STYLE}</style>" + "".join(body) + "</svg>"
    )


__all__ = ["design_to_summary_svg", "CANVAS_W", "CANVAS_H"]
