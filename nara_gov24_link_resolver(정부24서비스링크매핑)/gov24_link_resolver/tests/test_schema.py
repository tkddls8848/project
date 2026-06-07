"""test_schema.py — JSON Schema 유효성 단위 테스트."""
import json
from pathlib import Path

import pytest
import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
WORKING = ROOT / "data" / "working"
OUTPUT = ROOT / "data" / "output"


@pytest.fixture(scope="module")
def candidate_schema():
    return json.loads((SCHEMAS / "gov24_link_candidate.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def metadata_schema():
    return json.loads((SCHEMAS / "gov24_service_metadata.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def candidates(candidate_schema):
    path = WORKING / "link_candidates.jsonl"
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


@pytest.fixture(scope="module")
def metadata_records(metadata_schema):
    path = OUTPUT / "gov24_service_metadata.jsonl"
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def test_candidate_schema_is_valid_json_schema(candidate_schema):
    jsonschema.Draft7Validator.check_schema(candidate_schema)


def test_metadata_schema_is_valid_json_schema(metadata_schema):
    jsonschema.Draft7Validator.check_schema(metadata_schema)


def test_all_candidates_pass_schema(candidates, candidate_schema):
    validator = jsonschema.Draft7Validator(candidate_schema)
    errors = []
    for rec in candidates:
        for err in validator.iter_errors(rec):
            errors.append(f"{rec.get('candidate_id')}: {err.message}")
    assert not errors, f"스키마 오류 {len(errors)}건:\n" + "\n".join(errors)


def test_all_metadata_pass_schema(metadata_records, metadata_schema):
    if not metadata_records:
        pytest.skip("gov24_service_metadata.jsonl 없음 — match_services.py 먼저 실행")
    validator = jsonschema.Draft7Validator(metadata_schema)
    errors = []
    for rec in metadata_records:
        for err in validator.iter_errors(rec):
            errors.append(f"{rec.get('link_id')}: {err.message}")
    assert not errors, f"스키마 오류 {len(errors)}건:\n" + "\n".join(errors)


def test_candidate_count_minimum(candidates):
    assert len(candidates) >= 20, f"seed 20개 이상 필요, 현재 {len(candidates)}건"


def test_no_duplicate_candidate_ids(candidates):
    ids = [r["candidate_id"] for r in candidates]
    duplicates = [cid for cid in set(ids) if ids.count(cid) > 1]
    assert not duplicates, f"중복 candidate_id: {duplicates}"


def test_reviewed_count_minimum(candidates):
    reviewed = [r for r in candidates if r.get("review_status") == "reviewed"]
    assert len(reviewed) >= 10, f"reviewed 10개 이상 필요, 현재 {len(reviewed)}건"
