import re
from collections import defaultdict
from typing import Any

from .data_loader import DataRepository, clean_text


def normalize(value: str) -> str:
    text = clean_text(value).lower()
    return re.sub(r"[^0-9a-z가-힣]+", " ", text).strip()


def compact(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", normalize(value))


def tokenize(value: str) -> list[str]:
    tokens = []
    seen = set()
    for token in normalize(value).split():
        if len(token) < 2:
            continue
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


class LexicalSearcher:
    def __init__(self, repo: DataRepository) -> None:
        self.repo = repo

    def search(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        phrase = normalize(query)
        phrase_compact = compact(query)
        tokens = tokenize(query)
        scores: dict[str, float] = defaultdict(float)
        reasons: dict[str, list[str]] = defaultdict(list)

        for service_id, blobs in self.repo.search_blobs.items():
            service_score = 0.0
            service_reasons: list[str] = []

            service_score += self._score_blob(blobs["endpoint_paths"], phrase, phrase_compact, tokens, 0.35, "endpoint path", service_reasons)
            service_score += self._score_blob(blobs["field_names"], phrase, phrase_compact, tokens, 0.30, "field name", service_reasons)
            service_score += self._score_blob(blobs["field_descriptions"], phrase, phrase_compact, tokens, 0.25, "field description", service_reasons)
            service_score += self._score_blob(blobs["service_name"], phrase, phrase_compact, tokens, 0.25, "service name", service_reasons)
            service_score += self._score_blob(blobs["keywords"], phrase, phrase_compact, tokens, 0.18, "keyword", service_reasons)
            service_score += self._score_blob(blobs["endpoint_summaries"], phrase, phrase_compact, tokens, 0.18, "endpoint summary", service_reasons)
            service_score += self._score_blob(blobs["semantic"], phrase, phrase_compact, tokens, 0.12, "semantic tag", service_reasons)
            service_score += self._score_blob(blobs["all"], phrase, phrase_compact, tokens, 0.08, "document text", service_reasons)

            if service_score > 0:
                scores[service_id] += min(service_score, 1.5)
                reasons[service_id].extend(service_reasons[:6])

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [
            {
                "service_id": service_id,
                "lexical_score": score,
                "reasons": self._dedupe_reasons(reasons[service_id]),
            }
            for service_id, score in ranked
        ]

    def _score_blob(
        self,
        blob: str,
        phrase: str,
        phrase_compact: str,
        tokens: list[str],
        weight: float,
        label: str,
        reasons: list[str],
    ) -> float:
        if not blob:
            return 0.0
        blob_norm = normalize(blob)
        blob_compact = compact(blob)
        score = 0.0
        if phrase and phrase in blob_norm:
            score += weight
            reasons.append(f"{label}: phrase")
        elif phrase_compact and phrase_compact in blob_compact:
            score += weight * 0.95
            reasons.append(f"{label}: compact phrase")

        token_hits = [token for token in tokens if token in blob_norm or token in blob_compact]
        if token_hits:
            ratio = len(token_hits) / max(len(tokens), 1)
            score += weight * 0.7 * ratio
            reasons.append(f"{label}: {', '.join(token_hits[:4])}")
        return score

    def _dedupe_reasons(self, values: list[str]) -> list[str]:
        result = []
        seen = set()
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

