"""test_link_format.py — URL 형식·링크 품질 단위 테스트."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKING = ROOT / "data" / "working"
OUTPUT = ROOT / "data" / "output"

URL_RE = re.compile(r"^https://.+")  # HTTPS 권장


@pytest.fixture(scope="module")
def candidates():
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
def metadata_records():
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


def test_candidate_urls_https(candidates):
    non_https = [r["candidate_id"] for r in candidates if not URL_RE.match(r.get("url", ""))]
    # HTTP 허용하되 경고 수준 — 90% 이상 HTTPS 권장
    https_rate = (len(candidates) - len(non_https)) / len(candidates) if candidates else 1.0
    assert https_rate >= 0.9, f"HTTPS 비율 {https_rate:.0%} — 90% 미만: {non_https}"


def test_candidate_titles_nonempty(candidates):
    empty = [r["candidate_id"] for r in candidates if not r.get("title", "").strip()]
    assert not empty, f"제목 없는 레코드: {empty}"


def test_confidence_range(candidates):
    out_of_range = [
        r["candidate_id"] for r in candidates
        if not (0.0 <= r.get("confidence", -1) <= 1.0)
    ]
    assert not out_of_range, f"confidence 범위 초과: {out_of_range}"


def test_review_status_values(candidates):
    valid = {"pending", "reviewed", "rejected"}
    invalid = [r["candidate_id"] for r in candidates if r.get("review_status") not in valid]
    assert not invalid, f"유효하지 않은 review_status: {invalid}"


def test_metadata_link_ids_unique(metadata_records):
    if not metadata_records:
        pytest.skip("gov24_service_metadata.jsonl 없음")
    ids = [r["link_id"] for r in metadata_records]
    duplicates = [lid for lid in set(ids) if ids.count(lid) > 1]
    assert not duplicates, f"중복 link_id: {duplicates}"


def test_metadata_domain_ids_nonempty(metadata_records):
    if not metadata_records:
        pytest.skip("gov24_service_metadata.jsonl 없음")
    empty = [r["link_id"] for r in metadata_records if not r.get("domain_ids")]
    assert not empty, f"domain_ids 없는 레코드: {empty}"


def _load_validate_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_outputs", ROOT / "scripts" / "validate_outputs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validation_report_reproducible(tmp_path):
    """커밋된 후보 데이터에서 리포트가 재생성되고 완료 기준을 충족한다.

    작업 트리를 오염시키지 않도록 리포트는 임시 디렉터리에 생성한다.
    """
    validate_outputs = _load_validate_module()
    report = validate_outputs.run_validation(output_dir=tmp_path, verbose=False)

    report_path = tmp_path / "link_resolution_report.json"
    assert report_path.exists()
    assert report["total_candidates"] > 0
    assert report["schema_errors"] == 0, report["schema_error_details"]
    assert report["url_validity_rate"] >= 0.9, \
        f"URL 유효율 {report['url_validity_rate']:.0%} — 90% 미만"


def test_committed_report_meets_threshold():
    """data/output에 생성된 실제 리포트가 있으면 기준 충족을 확인한다."""
    report_path = OUTPUT / "link_resolution_report.json"
    if not report_path.exists():
        pytest.skip("link_resolution_report.json 없음 — scripts/validate_outputs.py로 생성")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report.get("url_validity_rate", 0) >= 0.9, \
        f"URL 유효율 {report.get('url_validity_rate'):.0%} — 90% 미만"
