"""Lightweight, machine-readable data quality profiling.

The default path profiles at most 10,000 records from the bounded byte sample
produced by :mod:`profiling.fetcher`.  Callers may explicitly request ``full``
mode when they have intentionally supplied the complete dataset.
"""

from __future__ import annotations

import csv
import html
import io
import json
import math
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from profiling.schema_infer import NULL_TOKENS, SchemaInference, decode_text


DEFAULT_MAX_ROWS = 10_000


@dataclass(frozen=True)
class ProfileOptions:
    """Resource and output controls for a quality report."""

    full: bool = False
    max_rows: int = DEFAULT_MAX_ROWS
    max_top_values: int = 10
    max_outliers: int = 20

    def __post_init__(self) -> None:
        if self.max_rows < 1:
            raise ValueError("max_rows must be positive")
        if self.max_top_values < 1:
            raise ValueError("max_top_values must be positive")
        if self.max_outliers < 0:
            raise ValueError("max_outliers must be non-negative")


@dataclass
class QualityReport:
    """JSON-first result with an optional dependency-free HTML rendering."""

    status: str
    mode: str
    scope: Dict[str, Any]
    dataset: Dict[str, Any]
    columns: List[Dict[str, Any]]
    outlier_candidates: List[Dict[str, Any]]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, allow_nan=False)

    def to_html(self, *, title: str = "Data quality report") -> str:
        """Render a compact standalone view; JSON remains the canonical output."""
        column_rows = []
        for column in self.columns:
            distribution = html.escape(
                json.dumps(column["distribution"], ensure_ascii=False, allow_nan=False)
            )
            column_rows.append(
                "<tr>"
                f"<td>{html.escape(str(column['name']))}</td>"
                f"<td>{html.escape(str(column['inferred_type']))}</td>"
                f"<td>{column['missing_ratio']:.2%}</td>"
                f"<td>{column['type_consistency']['ratio']:.2%}</td>"
                f"<td><code>{distribution}</code></td>"
                "</tr>"
            )
        warning_items = "".join(f"<li>{html.escape(item)}</li>" for item in self.warnings)
        return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font:14px system-ui;margin:2rem;color:#202124}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:.5rem;text-align:left;vertical-align:top}}th{{background:#f4f6f8}}
code{{white-space:pre-wrap;word-break:break-word}}</style></head><body>
<h1>{title}</h1><p>Mode: <b>{mode}</b>; observed rows: <b>{rows}</b>; duplicate ratio: <b>{duplicates:.2%}</b></p>
<ul>{warnings}</ul><table><thead><tr><th>Column</th><th>Type</th><th>Missing</th>
<th>Type consistency</th><th>Distribution</th></tr></thead><tbody>{column_rows}</tbody></table>
</body></html>""".format(
            title=html.escape(title),
            mode=html.escape(self.mode),
            rows=self.dataset.get("observed_rows", 0),
            duplicates=self.dataset.get("duplicate_ratio", 0.0),
            warnings=warning_items,
            column_rows="".join(column_rows),
        )


def generate_quality_report(
    schema: SchemaInference | Mapping[str, Any],
    sample: bytes | str | Iterable[Mapping[str, Any] | Sequence[Any]],
    *,
    options: Optional[ProfileOptions] = None,
    truncated: bool = False,
) -> QualityReport:
    """Profile a T3 schema plus its corresponding raw sample or record iterable.

    Statistics always describe the observed records, never an extrapolated
    population.  ``full=True`` removes the row cap, but the report only calls
    itself full when the caller also says the input was not truncated.
    """
    selected = options or ProfileOptions()
    schema_data = _schema_dict(schema)
    columns = list(schema_data.get("columns") or [])
    names = [str(column.get("name", "")) for column in columns]
    source_status = str(schema_data.get("status", "unverified"))
    warnings: List[str] = []

    if not names:
        warnings.append(schema_data.get("error") or "schema contains no columns")
        return QualityReport(
            status=source_status if source_status in {"error", "unsupported"} else "unverified",
            mode="full" if selected.full else "sample",
            scope={
                "statistics_apply_to": "observed_rows_only",
                "population_estimates": "unverified",
                "input_truncated": truncated,
                "row_limit": None if selected.full else selected.max_rows,
                "row_limit_reached": False,
            },
            dataset={"observed_rows": 0, "column_count": 0, "missing_ratio": 0.0,
                     "duplicate_rows": 0, "duplicate_ratio": 0.0},
            columns=[],
            outlier_candidates=[],
            warnings=warnings,
        )

    rows, row_limit_reached = _read_rows(schema_data, sample, names, selected, truncated)
    observed_rows = len(rows)
    normalized_rows = [tuple(_normalize_cell(row.get(name)) for name in names) for row in rows]
    duplicate_rows = observed_rows - len(set(normalized_rows))
    total_cells = observed_rows * len(names)
    missing_cells = sum(_is_null(value) for row in normalized_rows for value in row)

    column_reports: List[Dict[str, Any]] = []
    all_outliers: List[Dict[str, Any]] = []
    for index, column in enumerate(columns):
        values = [row[index] for row in normalized_rows]
        report, candidates = _profile_column(column, values, selected)
        column_reports.append(report)
        all_outliers.extend(candidates)

    actual_full = selected.full and not truncated and not row_limit_reached
    if not actual_full:
        warnings.append("Population-level conclusions are unverified; statistics cover observed rows only.")
    if source_status != "ok":
        warnings.append(f"Source schema status is {source_status}.")

    return QualityReport(
        status="ok" if source_status == "ok" else "unverified",
        mode="full" if actual_full else "sample",
        scope={
            "statistics_apply_to": "observed_rows_only",
            "population_estimates": "verified" if actual_full else "unverified",
            "input_truncated": truncated,
            "row_limit": None if selected.full else selected.max_rows,
            "row_limit_reached": row_limit_reached,
        },
        dataset={
            "observed_rows": observed_rows,
            "column_count": len(names),
            "missing_cells": missing_cells,
            "missing_ratio": missing_cells / total_cells if total_cells else 0.0,
            "duplicate_rows": duplicate_rows,
            "duplicate_ratio": duplicate_rows / observed_rows if observed_rows else 0.0,
        },
        columns=column_reports,
        outlier_candidates=all_outliers,
        warnings=warnings,
    )


def write_quality_report(
    report: QualityReport,
    json_path: str | Path,
    *,
    html_path: Optional[str | Path] = None,
    title: str = "Data quality report",
) -> None:
    """Write canonical JSON and, when requested, an optional HTML view."""
    Path(json_path).write_text(report.to_json() + "\n", encoding="utf-8")
    if html_path is not None:
        Path(html_path).write_text(report.to_html(title=title), encoding="utf-8")


def _schema_dict(schema: SchemaInference | Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(schema, Mapping):
        return dict(schema)
    if hasattr(schema, "to_dict"):
        return schema.to_dict()
    if is_dataclass(schema):
        return asdict(schema)
    raise TypeError("schema must be a SchemaInference or mapping")


def _read_rows(
    schema: Mapping[str, Any],
    sample: bytes | str | Iterable[Mapping[str, Any] | Sequence[Any]],
    names: Sequence[str],
    options: ProfileOptions,
    truncated: bool,
) -> Tuple[List[Dict[str, Any]], bool]:
    limit = None if options.full else options.max_rows
    if isinstance(sample, bytes):
        text, _, _ = decode_text(sample)
        if truncated and text and not text.endswith(("\n", "\r")):
            text = text.rsplit("\n", 1)[0] if "\n" in text else ""
        raw_rows = _text_records(schema, text, names)
    elif isinstance(sample, str):
        raw_rows = _text_records(schema, sample, names)
    else:
        raw_rows = sample

    output: List[Dict[str, Any]] = []
    reached = False
    for raw in raw_rows:
        if limit is not None and len(output) >= limit:
            reached = True
            break
        if isinstance(raw, Mapping):
            output.append({name: raw.get(name) for name in names})
        else:
            values = list(raw)
            output.append({name: values[index] if index < len(values) else None for index, name in enumerate(names)})
    return output, reached


def _text_records(
    schema: Mapping[str, Any], text: str, names: Sequence[str]
) -> Iterable[Mapping[str, Any] | Sequence[Any]]:
    file_format = str(schema.get("format", "csv"))
    if file_format == "json":
        value = json.loads(text)
        if isinstance(value, Mapping):
            value = value.get("data") or value.get("items") or value.get("records") or [value]
        if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
            raise ValueError("JSON sample is not tabular")
        return value
    delimiter = schema.get("delimiter") or ("\t" if file_format == "tsv" else ",")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=str(delimiter))
    iterator = iter(reader)
    next(iterator, None)  # T3 samples include a header row.
    return iterator


def _profile_column(
    schema_column: Mapping[str, Any], values: Sequence[str], options: ProfileOptions
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    name = str(schema_column.get("name", ""))
    expected = str(schema_column.get("inferred_type", "string"))
    non_null = [(row_number, value) for row_number, value in enumerate(values, 1) if not _is_null(value)]
    observed_types = Counter(_classify(value) for _, value in non_null)
    mismatches = [
        {"row_number": row_number, "value": value, "observed_type": _classify(value)}
        for row_number, value in non_null
        if not _matches_type(value, expected)
    ]
    matching = len(non_null) - len(mismatches)
    distribution, numeric_values = _distribution(non_null, expected, options.max_top_values)
    outliers = _numeric_outliers(name, numeric_values, options.max_outliers)
    for mismatch in mismatches[: options.max_outliers]:
        outliers.append({"column": name, "kind": "type_mismatch", **mismatch})

    return {
        "name": name,
        "inferred_type": expected,
        "observed_count": len(values),
        "non_null_count": len(non_null),
        "missing_count": len(values) - len(non_null),
        "missing_ratio": (len(values) - len(non_null)) / len(values) if values else 0.0,
        "schema_sample_missing_ratio": schema_column.get("null_ratio"),
        "distinct_count": len({value for _, value in non_null}),
        "type_consistency": {
            "ratio": matching / len(non_null) if non_null else 1.0,
            "matching_count": matching,
            "mismatch_count": len(mismatches),
            "observed_types": dict(sorted(observed_types.items())),
        },
        "distribution": distribution,
        "outlier_candidate_count": len(outliers),
    }, outliers


def _distribution(
    values: Sequence[Tuple[int, str]], expected: str, max_top_values: int
) -> Tuple[Dict[str, Any], List[Tuple[int, str, float]]]:
    numeric_values: List[Tuple[int, str, float]] = []
    if expected in {"integer", "number"}:
        for row_number, value in values:
            number = _number(value)
            if number is not None:
                numeric_values.append((row_number, value, number))
    if numeric_values:
        numbers = [item[2] for item in numeric_values]
        ordered = sorted(numbers)
        return {
            "kind": "numeric",
            "count": len(numbers),
            "minimum": min(numbers),
            "maximum": max(numbers),
            "mean": statistics.fmean(numbers),
            "median": statistics.median(numbers),
            "standard_deviation": statistics.pstdev(numbers),
            "quartiles": {"q1": _quantile(ordered, 0.25), "q3": _quantile(ordered, 0.75)},
        }, numeric_values

    counts = Counter(value for _, value in values)
    top_values = [
        {"value": value, "count": count, "ratio": count / len(values)}
        for value, count in counts.most_common(max_top_values)
    ] if values else []
    lengths = [len(value) for _, value in values]
    result: Dict[str, Any] = {
        "kind": "categorical",
        "unique_count": len(counts),
        "top_values": top_values,
    }
    if lengths:
        result["length"] = {
            "minimum": min(lengths),
            "maximum": max(lengths),
            "mean": statistics.fmean(lengths),
        }
    if expected in {"date", "datetime"} and values:
        result["range"] = {"minimum": min(value for _, value in values), "maximum": max(value for _, value in values)}
    return result, numeric_values


def _numeric_outliers(
    name: str, values: Sequence[Tuple[int, str, float]], maximum: int
) -> List[Dict[str, Any]]:
    if len(values) < 4 or maximum == 0:
        return []
    ordered = sorted(item[2] for item in values)
    q1, q3 = _quantile(ordered, 0.25), _quantile(ordered, 0.75)
    iqr = q3 - q1
    if iqr <= 0:
        return []
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    candidates = [item for item in values if item[2] < lower or item[2] > upper]
    candidates.sort(key=lambda item: min(item[2] - lower, upper - item[2]))
    return [
        {
            "column": name,
            "kind": "iqr",
            "row_number": row_number,
            "value": value,
            "numeric_value": number,
            "lower_fence": lower,
            "upper_fence": upper,
        }
        for row_number, value, number in candidates[:maximum]
    ]


def _quantile(ordered: Sequence[float], probability: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _is_null(value: str) -> bool:
    return value.strip().lower() in NULL_TOKENS


def _number(value: str) -> Optional[float]:
    normalized = value.replace(",", "")
    try:
        result = float(normalized)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _classify(value: str) -> str:
    lowered = value.lower()
    if lowered in {"true", "false", "yes", "no", "y", "n"}:
        return "boolean"
    normalized = value.replace(",", "")
    if re.fullmatch(r"[+-]?\d+", normalized):
        digits = normalized.lstrip("+-")
        return "string" if len(digits) > 1 and digits.startswith("0") else "integer"
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", normalized):
        return "number"
    iso = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        return "datetime" if parsed.time() != datetime.min.time() or "T" in iso or " " in iso else "date"
    except ValueError:
        try:
            date.fromisoformat(iso)
            return "date"
        except ValueError:
            return "string"


def _matches_type(value: str, expected: str) -> bool:
    observed = _classify(value)
    if expected == "number":
        return observed in {"integer", "number"}
    if expected == "datetime":
        return observed in {"date", "datetime"}
    if expected == "null":
        return False
    return observed == expected
