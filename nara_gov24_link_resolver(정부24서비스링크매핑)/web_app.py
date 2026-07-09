"""Local browser UI for the Gov24 link resolver.

Run:
    python web_app.py --port 8765
"""
from __future__ import annotations

import argparse
import json
import locale
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
WORKING = ROOT / "data" / "working"
OUTPUT = ROOT / "data" / "output"
CANDIDATES_FILE = WORKING / "link_candidates.jsonl"
METADATA_FILE = OUTPUT / "gov24_service_metadata.jsonl"
REPORT_FILE = OUTPUT / "link_resolution_report.json"

VALID_SOURCES = {"manual", "search", "crawler", "api"}
VALID_STATUSES = {"pending", "reviewed", "rejected"}
OPTIONAL_CANDIDATE_FIELDS = (
    "matched_query",
    "matched_service_name",
    "match_reason",
    "notes",
)
SCRIPT_STEPS = {
    "normalize": ROOT / "scripts" / "normalize_links.py",
    "match": ROOT / "scripts" / "match_services.py",
    "validate": ROOT / "scripts" / "validate_outputs.py",
}
UTF8_ENV = {
    **os.environ,
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}
UTF8_STATIC_TYPES = {
    "text/html",
    "text/css",
    "text/javascript",
    "application/javascript",
}

class ApiError(Exception):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def read_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    if not path.exists():
        return records, errors

    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path.name}:{line_no} {exc.msg}")
                continue
            if isinstance(value, dict):
                records.append(value)
            else:
                errors.append(f"{path.name}:{line_no} object expected")
    return records, errors


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": f"{path.name} could not be parsed"}


def file_info(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path.relative_to(ROOT)), "exists": False}
    stat = path.stat()
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": True,
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def next_candidate_id(records: list[dict]) -> str:
    highest = 0
    for record in records:
        match = re.match(r"^candidate:gov24:(\d+)$", str(record.get("candidate_id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"candidate:gov24:{highest + 1:03d}"


def clean_string(value: object) -> str:
    return str(value or "").strip()


def parse_confidence(value: object, default: float = 0.7) -> float:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ApiError("confidence must be a number from 0 to 1") from exc
    if not 0 <= parsed <= 1:
        raise ApiError("confidence must be a number from 0 to 1")
    return round(parsed, 3)


def assert_url(url: str) -> None:
    if not re.match(r"^https?://.+", url):
        raise ApiError("url must start with http:// or https://")


def make_candidate(payload: dict, existing: list[dict]) -> dict:
    title = clean_string(payload.get("title"))
    url = clean_string(payload.get("url"))
    source = clean_string(payload.get("source") or "manual")
    review_status = clean_string(payload.get("review_status") or "pending")

    if not title:
        raise ApiError("title is required")
    assert_url(url)
    if source not in VALID_SOURCES:
        raise ApiError(f"source must be one of {sorted(VALID_SOURCES)}")
    if review_status not in VALID_STATUSES:
        raise ApiError(f"review_status must be one of {sorted(VALID_STATUSES)}")

    candidate_id = clean_string(payload.get("candidate_id")) or next_candidate_id(existing)
    if not re.match(r"^candidate:[a-z0-9_]+:[0-9]+$", candidate_id):
        raise ApiError("candidate_id must match candidate:<source>:<number>")
    if any(record.get("candidate_id") == candidate_id for record in existing):
        raise ApiError(f"{candidate_id} already exists", HTTPStatus.CONFLICT)

    record: dict = {
        "candidate_id": candidate_id,
        "title": title,
        "url": url,
        "source": source,
        "confidence": parse_confidence(payload.get("confidence")),
        "review_status": review_status,
    }
    for field in OPTIONAL_CANDIDATE_FIELDS:
        value = clean_string(payload.get(field))
        if value:
            record[field] = value
    return record


def update_candidate(candidate_id: str, payload: dict) -> dict:
    records, errors = read_jsonl(CANDIDATES_FILE)
    if errors:
        raise ApiError("candidate file has JSONL parse errors")

    index = next((i for i, item in enumerate(records) if item.get("candidate_id") == candidate_id), -1)
    if index < 0:
        raise ApiError(f"{candidate_id} was not found", HTTPStatus.NOT_FOUND)

    record = dict(records[index])
    allowed = {
        "title",
        "url",
        "source",
        "confidence",
        "review_status",
        *OPTIONAL_CANDIDATE_FIELDS,
    }
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "confidence":
            record[key] = parse_confidence(value, default=record.get("confidence", 0.7))
        else:
            record[key] = clean_string(value)

    if not clean_string(record.get("title")):
        raise ApiError("title is required")
    assert_url(clean_string(record.get("url")))
    if record.get("source") not in VALID_SOURCES:
        raise ApiError(f"source must be one of {sorted(VALID_SOURCES)}")
    if record.get("review_status") not in VALID_STATUSES:
        raise ApiError(f"review_status must be one of {sorted(VALID_STATUSES)}")

    records[index] = record
    write_jsonl(CANDIDATES_FILE, records)
    return record


def add_candidate(payload: dict) -> dict:
    records, errors = read_jsonl(CANDIDATES_FILE)
    if errors:
        raise ApiError("candidate file has JSONL parse errors")
    record = make_candidate(payload, records)
    records.append(record)
    write_jsonl(CANDIDATES_FILE, records)
    return record


def decode_process_output(data: bytes) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", locale.getpreferredencoding(False), "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def run_pipeline(steps: list[str]) -> dict:
    if not steps:
        steps = ["normalize", "match", "validate"]

    unknown = [step for step in steps if step not in SCRIPT_STEPS]
    if unknown:
        raise ApiError(f"unknown pipeline step: {', '.join(unknown)}")

    results = []
    for step in steps:
        script_path = SCRIPT_STEPS[step]
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=UTF8_ENV,
        )
        results.append(
            {
                "step": step,
                "returncode": completed.returncode,
                "stdout": decode_process_output(completed.stdout),
                "stderr": decode_process_output(completed.stderr),
            }
        )
        if completed.returncode != 0:
            break
    return {"ok": all(item["returncode"] == 0 for item in results), "results": results}


def build_summary() -> dict:
    candidates, candidate_errors = read_jsonl(CANDIDATES_FILE)
    metadata, metadata_errors = read_jsonl(METADATA_FILE)
    report = read_json(REPORT_FILE)

    candidate_status = Counter(item.get("review_status", "unknown") for item in candidates)
    source_counts = Counter(item.get("source", "unknown") for item in candidates)
    metadata_status = Counter(item.get("review_status", "unknown") for item in metadata)
    domain_counts: Counter[str] = Counter()
    for item in metadata:
        for domain_id in item.get("domain_ids", []):
            domain_counts[domain_id] += 1

    return {
        "counts": {
            "candidates": len(candidates),
            "metadata": len(metadata),
            "reviewed": candidate_status.get("reviewed", 0),
            "pending": candidate_status.get("pending", 0),
            "rejected": candidate_status.get("rejected", 0),
            "broken_links": report.get("broken_links", 0),
            "schema_errors": report.get("schema_errors", 0),
            "duplicate_urls": report.get("duplicate_urls", 0),
            "url_validity_rate": report.get("url_validity_rate", 0),
        },
        "candidate_status": dict(candidate_status),
        "source_counts": dict(source_counts),
        "metadata_status": dict(metadata_status),
        "domain_counts": dict(domain_counts),
        "candidates": candidates,
        "metadata": metadata,
        "report": report,
        "parse_errors": candidate_errors + metadata_errors,
        "files": {
            "candidates": file_info(CANDIDATES_FILE),
            "metadata": file_info(METADATA_FILE),
            "report": file_info(REPORT_FILE),
        },
    }


class Gov24Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def guess_type(self, path: str) -> str:
        content_type = super().guess_type(path)
        base_type = content_type.split(";", 1)[0]
        if base_type in UTF8_STATIC_TYPES and "charset=" not in content_type.lower():
            return f"{content_type}; charset=utf-8"
        return content_type

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError("request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ApiError("request body must be a JSON object")
        return payload

    def handle_api_error(self, exc: Exception) -> None:
        if isinstance(exc, ApiError):
            self.send_json({"ok": False, "error": exc.message}, exc.status)
            return
        self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/summary":
                self.send_json({"ok": True, "summary": build_summary()})
                return
            if path == "/api/candidates":
                records, errors = read_jsonl(CANDIDATES_FILE)
                self.send_json({"ok": not errors, "records": records, "errors": errors})
                return
            if path == "/api/metadata":
                records, errors = read_jsonl(METADATA_FILE)
                self.send_json({"ok": not errors, "records": records, "errors": errors})
                return
            if path == "/api/report":
                self.send_json({"ok": True, "report": read_json(REPORT_FILE)})
                return
        except Exception as exc:
            self.handle_api_error(exc)
            return

        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.read_body_json()
            if path == "/api/candidates":
                record = add_candidate(payload)
                self.send_json({"ok": True, "record": record, "summary": build_summary()}, HTTPStatus.CREATED)
                return
            if path == "/api/run":
                steps = payload.get("steps") or []
                if not isinstance(steps, list):
                    raise ApiError("steps must be a list")
                result = run_pipeline([clean_string(step) for step in steps])
                self.send_json({"ok": result["ok"], "pipeline": result, "summary": build_summary()})
                return
            self.send_json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.handle_api_error(exc)

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        try:
            if not path.startswith("/api/candidates/"):
                self.send_json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            candidate_id = unquote(path.removeprefix("/api/candidates/"))
            record = update_candidate(candidate_id, self.read_body_json())
            self.send_json({"ok": True, "record": record, "summary": build_summary()})
        except Exception as exc:
            self.handle_api_error(exc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gov24 link resolver web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Gov24Handler)
    print(f"Gov24 Link Resolver UI: http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server")


if __name__ == "__main__":
    main()
