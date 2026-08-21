"""Offline detection and quality checks for Korean address columns.

The profiler deliberately works from the bounded samples produced by
``schema_infer``.  A positive result therefore describes the sample evidence,
not a claim that every value in the source file has been validated.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


ROAD_ADDRESS_RE = re.compile(
    r"(?:^|\s)(?:[가-힣A-Za-z0-9·.-]+(?:대로|로|길))\s+\d{1,5}(?:-\d{1,5})?(?:\s|$)"
)
JIBUN_ADDRESS_RE = re.compile(
    r"(?:^|\s)[가-힣A-Za-z0-9·.-]+(?:동|읍|면|리|가)\s+(?:산\s*)?\d{1,5}(?:-\d{1,5})?(?:\s|$)"
)
POSTAL_CODE_RE = re.compile(r"^(?:\d{5}|\d{3}-\d{3})$")

_POSTAL_NAMES = ("우편번호", "우편 번호", "postal", "postcode", "post_code", "zipcode", "zip_code")
_ROAD_NAMES = ("도로명주소", "도로명 주소", "도로주소", "road_address", "road address")
_JIBUN_NAMES = ("지번주소", "지번 주소", "번지주소", "lot_address", "parcel_address")
_GENERIC_NAMES = ("주소", "소재지", "위치", "address", "addr")


@dataclass(frozen=True)
class AddressValidation:
    """Result of validating one value without any network lookup."""

    status: str
    kind: Optional[str]
    normalized: str
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AddressColumnProfile:
    """Address evidence and quality for one inferred column."""

    name: str
    kind: str
    status: str
    quality_score: float
    valid_sample_ratio: Optional[float]
    valid_samples: int
    sampled_values: int
    null_ratio: float
    format_counts: Dict[str, int]
    evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def validate_address(value: Any, expected_kind: Optional[str] = None) -> AddressValidation:
    """Validate a Korean road, lot-number, or postal-code representation.

    This is intentionally format validation only.  It does not establish that
    the address exists, so callers should not treat it as geocoded evidence.
    """

    normalized = _normalize(value)
    if not normalized:
        return AddressValidation("unverified", expected_kind, normalized, "empty value")

    detected = _detect_value_kind(normalized)
    if detected is None:
        return AddressValidation("invalid", expected_kind, normalized, "no supported address pattern")
    if expected_kind and expected_kind not in {"address", detected}:
        return AddressValidation(
            "invalid", detected, normalized, f"expected {expected_kind}, found {detected}"
        )
    return AddressValidation("verified", detected, normalized)


def detect_address_columns(schema: Any) -> List[AddressColumnProfile]:
    """Find address-like columns in a T3 schema inference result.

    ``schema`` may be a ``SchemaInference`` instance, a sequence of
    ``ColumnSchema`` objects, or their serialized mapping equivalents.
    """

    profiles: List[AddressColumnProfile] = []
    for column in _schema_columns(schema):
        name = str(_field(column, "name", ""))
        samples = [str(value) for value in (_field(column, "sample_values", []) or [])]
        null_ratio = _bounded_float(_field(column, "null_ratio", 0.0))
        header_kind = _header_kind(name)
        validations = [validate_address(value) for value in samples]
        counts = {"road": 0, "jibun": 0, "postal": 0}
        for result in validations:
            if result.status == "verified" and result.kind:
                counts[result.kind] += 1

        dominant_kind = max(counts, key=counts.get) if any(counts.values()) else None
        kind = header_kind or dominant_kind
        valid_count = sum(
            count
            for candidate, count in counts.items()
            if header_kind in {None, "address", candidate}
        )
        ratio = valid_count / len(samples) if samples else None

        # Sample-only postal detection is too easily confused with identifiers.
        sample_evidence = bool(dominant_kind) and not (
            dominant_kind == "postal" and header_kind is None
        )
        if header_kind is None and not sample_evidence:
            continue

        evidence: List[str] = []
        if header_kind:
            evidence.append(f"column_name:{header_kind}")
        if dominant_kind:
            evidence.append(f"sample_pattern:{dominant_kind}")

        if samples and ratio is not None and ratio >= 0.6:
            status = "verified"
        elif samples and valid_count == 0 and header_kind:
            status = "invalid"
        else:
            status = "unverified"

        header_score = 0.30 if header_kind else 0.0
        sample_score = 0.70 * (ratio or 0.0)
        completeness_factor = 1.0 - 0.5 * null_ratio
        score = round(min(1.0, (header_score + sample_score) * completeness_factor), 3)
        profiles.append(
            AddressColumnProfile(
                name=name,
                kind=kind or "address",
                status=status,
                quality_score=score,
                valid_sample_ratio=round(ratio, 3) if ratio is not None else None,
                valid_samples=valid_count,
                sampled_values=len(samples),
                null_ratio=null_ratio,
                format_counts=counts,
                evidence=evidence,
            )
        )
    return profiles


profile_address_columns = detect_address_columns


def _detect_value_kind(value: str) -> Optional[str]:
    compact = value.strip()
    if POSTAL_CODE_RE.fullmatch(compact):
        return "postal"
    if ROAD_ADDRESS_RE.search(compact):
        return "road"
    if JIBUN_ADDRESS_RE.search(compact):
        return "jibun"
    return None


def _header_kind(name: str) -> Optional[str]:
    lowered = re.sub(r"\s+", " ", name.strip().lower())
    compact = re.sub(r"[\s_-]+", "", lowered)
    if any(token.replace(" ", "").replace("_", "") in compact for token in _POSTAL_NAMES):
        return "postal"
    if any(token.replace(" ", "").replace("_", "") in compact for token in _ROAD_NAMES):
        return "road"
    if any(token.replace(" ", "").replace("_", "") in compact for token in _JIBUN_NAMES):
        return "jibun"
    if any(token.replace(" ", "").replace("_", "") in compact for token in _GENERIC_NAMES):
        return "address"
    return None


def _schema_columns(schema: Any) -> Iterable[Any]:
    if isinstance(schema, Mapping):
        return schema.get("columns", [])
    columns = getattr(schema, "columns", None)
    if columns is not None:
        return columns
    if isinstance(schema, Sequence) and not isinstance(schema, (str, bytes, bytearray)):
        return schema
    raise TypeError("schema must be a SchemaInference, column sequence, or mapping")


def _field(value: Any, name: str, default: Any) -> Any:
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _bounded_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
