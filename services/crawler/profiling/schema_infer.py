"""Dependency-free schema inference for bounded public-data file samples."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


NULL_TOKENS = {"", "null", "none", "nil", "na", "n/a", "nan", "-"}


@dataclass
class ColumnSchema:
    name: str
    inferred_type: str
    null_ratio: float
    sample_values: List[str] = field(default_factory=list)


@dataclass
class SchemaInference:
    status: str
    format: str
    columns: List[ColumnSchema] = field(default_factory=list)
    encoding: Optional[str] = None
    delimiter: Optional[str] = None
    sampled_rows: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "format": self.format,
            "columns": [asdict(column) for column in self.columns],
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "sampled_rows": self.sampled_rows,
            "error": self.error,
        }


def infer_schema(
    sample: bytes,
    *,
    filename: str = "sample.csv",
    content_type: Optional[str] = None,
    truncated: bool = False,
    max_sample_values: int = 5,
) -> SchemaInference:
    """Infer columns from a CSV/TSV or JSON sample.

    ZIP and XLSX are explicitly reported as unsupported. The implementation is
    intentionally standard-library-only so profiling adds no runtime package;
    unlike frictionless it also gives us deterministic handling of partial byte
    samples and Korean legacy encodings.
    """
    file_format = detect_format(sample, filename, content_type)
    if file_format in {"zip", "xlsx"}:
        return SchemaInference(
            status="unsupported",
            format=file_format,
            error=f"{file_format} profiling is not implemented",
        )
    if file_format == "json":
        return _infer_json(sample, max_sample_values)
    if file_format not in {"csv", "tsv", "text"}:
        return SchemaInference(
            status="unsupported",
            format=file_format,
            error=f"unsupported file format: {file_format}",
        )

    text, encoding, verified = decode_text(sample)
    if truncated:
        text = _drop_partial_last_line(text)
    if not text.strip():
        return SchemaInference(status="error", format=file_format, encoding=encoding, error="empty sample")
    delimiter = "\t" if file_format == "tsv" else _sniff_delimiter(text)
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
        rows = list(reader)
    except csv.Error as exc:
        return SchemaInference(status="error", format=file_format, encoding=encoding, error=str(exc))
    if not rows:
        return SchemaInference(status="error", format=file_format, encoding=encoding, error="no rows")

    header = _deduplicate_headers(rows[0])
    width = len(header)
    data_rows = [_normalize_width(row, width) for row in rows[1:] if any(cell.strip() for cell in row)]
    columns = _columns_from_rows(header, data_rows, max_sample_values)
    return SchemaInference(
        status="ok" if verified else "unverified",
        format="tsv" if delimiter == "\t" else "csv",
        columns=columns,
        encoding=encoding,
        delimiter=delimiter,
        sampled_rows=len(data_rows),
        error=None if verified else "encoding required a permissive fallback",
    )


def infer_fetched_files(fetch_results: Mapping[str, Any]) -> Dict[str, SchemaInference]:
    """Infer schemas directly from results returned by ``fetch_download_urls``."""
    output: Dict[str, SchemaInference] = {}
    for name, fetched in fetch_results.items():
        if getattr(fetched, "status", None) != "ok":
            output[name] = SchemaInference(
                status=getattr(fetched, "status", "error"),
                format="unknown",
                error=getattr(fetched, "error", "fetch failed"),
            )
            continue
        output[name] = infer_schema(
            fetched.sample,
            filename=fetched.filename or name,
            content_type=fetched.content_type,
            truncated=fetched.truncated,
        )
    return output


def detect_format(sample: bytes, filename: str, content_type: Optional[str]) -> str:
    suffix = Path(filename.lower()).suffix
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if suffix == ".xlsx" or (sample.startswith(b"PK\x03\x04") and b"[Content_Types].xml" in sample):
        return "xlsx"
    if suffix == ".zip" or sample.startswith(b"PK\x03\x04"):
        return "zip"
    if suffix in {".json", ".geojson"} or "json" in mime:
        return "json"
    if suffix == ".tsv" or "tab-separated-values" in mime:
        return "tsv"
    if suffix in {".csv", ".txt"} or mime.startswith("text/") or "csv" in mime:
        return "csv" if suffix != ".txt" else "text"
    return "unknown"


def decode_text(sample: bytes) -> tuple[str, str, bool]:
    if sample.startswith(b"\xef\xbb\xbf"):
        return sample.decode("utf-8-sig"), "utf-8-sig", True
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return sample.decode("utf-16"), "utf-16", True
    for encoding in ("utf-8", "euc-kr", "cp949"):
        try:
            return sample.decode(encoding), encoding, True
        except UnicodeDecodeError:
            continue
    return sample.decode("latin-1", errors="replace"), "latin-1", False


def _infer_json(sample: bytes, max_sample_values: int) -> SchemaInference:
    text, encoding, verified = decode_text(sample)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return SchemaInference(status="error", format="json", encoding=encoding, error=str(exc))
    if isinstance(value, dict):
        records = value.get("data") or value.get("items") or value.get("records") or [value]
    else:
        records = value
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        return SchemaInference(status="unsupported", format="json", encoding=encoding, error="JSON is not tabular")
    headers: List[str] = []
    for record in records:
        for key in record:
            if str(key) not in headers:
                headers.append(str(key))
    rows = [[_json_cell(record.get(key)) for key in headers] for record in records]
    return SchemaInference(
        status="ok" if verified else "unverified",
        format="json",
        columns=_columns_from_rows(headers, rows, max_sample_values),
        encoding=encoding,
        sampled_rows=len(rows),
    )


def _columns_from_rows(
    headers: Sequence[str], rows: Sequence[Sequence[str]], max_samples: int
) -> List[ColumnSchema]:
    columns: List[ColumnSchema] = []
    denominator = len(rows)
    for index, name in enumerate(headers):
        values = [row[index].strip() for row in rows]
        non_null = [value for value in values if value.lower() not in NULL_TOKENS]
        samples = list(dict.fromkeys(non_null))[:max_samples]
        inferred = _merge_types(_infer_scalar(value) for value in non_null)
        columns.append(
            ColumnSchema(
                name=name,
                inferred_type=inferred,
                null_ratio=(denominator - len(non_null)) / denominator if denominator else 0.0,
                sample_values=samples,
            )
        )
    return columns


def _infer_scalar(value: str) -> str:
    lowered = value.lower()
    if lowered in {"true", "false", "yes", "no", "y", "n"}:
        return "boolean"
    normalized = value.replace(",", "")
    if re.fullmatch(r"[+-]?\d+", normalized):
        digits = normalized.lstrip("+-")
        if len(digits) > 1 and digits.startswith("0"):
            return "string"
        return "integer"
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", normalized):
        return "number"
    iso = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(iso)
        return "datetime" if "T" in iso or " " in iso else "date"
    except ValueError:
        try:
            date.fromisoformat(iso)
            return "date"
        except ValueError:
            return "string"


def _merge_types(types: Iterable[str]) -> str:
    unique = set(types)
    if not unique:
        return "null"
    if unique <= {"integer", "number"}:
        return "number" if "number" in unique else "integer"
    if unique <= {"date", "datetime"}:
        return "datetime" if "datetime" in unique else "date"
    return unique.pop() if len(unique) == 1 else "string"


def _deduplicate_headers(raw: Sequence[str]) -> List[str]:
    counts: Dict[str, int] = {}
    output: List[str] = []
    for index, value in enumerate(raw, 1):
        base = value.strip().lstrip("\ufeff") or f"column_{index}"
        counts[base] = counts.get(base, 0) + 1
        output.append(base if counts[base] == 1 else f"{base}_{counts[base]}")
    return output


def _normalize_width(row: Sequence[str], width: int) -> List[str]:
    values = list(row[:width])
    return values + [""] * (width - len(values))


def _sniff_delimiter(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:16_384], delimiters=",\t;|").delimiter
    except csv.Error:
        return ","


def _drop_partial_last_line(text: str) -> str:
    if text.endswith(("\n", "\r")):
        return text
    return text.rsplit("\n", 1)[0] if "\n" in text else text


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
