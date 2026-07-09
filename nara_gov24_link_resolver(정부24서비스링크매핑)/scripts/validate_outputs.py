"""validate_outputs.py

1. link_candidates.jsonl → gov24_link_candidate.schema.json 검증
2. gov24_service_metadata.jsonl → gov24_service_metadata.schema.json 검증
3. URL 형식 유효성 검사
4. link_resolution_report.json 생성
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("jsonschema 패키지가 필요합니다: pip install jsonschema")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
WORKING = ROOT / "data" / "working"
OUTPUT = ROOT / "data" / "output"

KST = timezone(timedelta(hours=9))

URL_RE = re.compile(r"^https?://.+")


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [ERROR] {path.name} 줄 {i}: {e}")
    return records


def validate_schema(records: list[dict], schema: dict, label: str) -> list[str]:
    errors = []
    validator = jsonschema.Draft7Validator(schema)
    for rec in records:
        for err in validator.iter_errors(rec):
            errors.append(f"{label} [{rec.get('candidate_id') or rec.get('link_id')}]: {err.message}")
    return errors


def check_urls(records: list[dict], url_field: str = "url") -> list[str]:
    broken = []
    for rec in records:
        url = rec.get(url_field, "")
        if not URL_RE.match(url):
            broken.append(f"{rec.get('candidate_id') or rec.get('link_id')}: 형식 불량 — {url!r}")
    return broken


def run_validation(
    working_dir: Path = WORKING,
    output_dir: Path = OUTPUT,
    schemas_dir: Path = SCHEMAS,
    verbose: bool = True,
) -> dict:
    """검증을 수행하고 리포트를 output_dir에 저장한 뒤 dict로 반환한다.

    테스트는 output_dir에 임시 경로를 넘겨 작업 트리를 오염시키지 않는다.
    """
    def log(message: str) -> None:
        if verbose:
            print(message)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 스키마 로드
    candidate_schema = json.loads((schemas_dir / "gov24_link_candidate.schema.json").read_text(encoding="utf-8"))
    metadata_schema = json.loads((schemas_dir / "gov24_service_metadata.schema.json").read_text(encoding="utf-8"))

    # 후보 파일
    candidates_path = working_dir / "link_candidates.jsonl"
    metadata_path = output_dir / "gov24_service_metadata.jsonl"

    candidates = load_jsonl(candidates_path) if candidates_path.exists() else []
    metadata = load_jsonl(metadata_path) if metadata_path.exists() else []

    log(f"link_candidates.jsonl : {len(candidates)}건")
    log(f"gov24_service_metadata.jsonl : {len(metadata)}건")

    # 스키마 검증
    schema_errors: list[str] = []
    schema_errors += validate_schema(candidates, candidate_schema, "candidate")
    schema_errors += validate_schema(metadata, metadata_schema, "metadata")

    # URL 형식 검사
    broken_urls: list[str] = []
    broken_urls += check_urls(candidates)
    broken_urls += check_urls(metadata)

    # 중복 URL 검사
    candidate_urls = [r.get("url", "") for r in candidates]
    dup_urls = [url for url, cnt in Counter(candidate_urls).items() if cnt > 1]

    # 상태 통계
    status_counts = Counter(r.get("review_status") for r in candidates)
    meta_status = Counter(r.get("review_status") for r in metadata)

    # 도메인 분포
    domain_counter: Counter = Counter()
    for r in metadata:
        for d in r.get("domain_ids", []):
            domain_counter[d] += 1

    # 보고서 출력
    log("\n── 검증 결과 ────────────────────────────")
    if schema_errors:
        log(f"  스키마 오류 {len(schema_errors)}건:")
        for e in schema_errors:
            log(f"    {e}")
    else:
        log("  스키마 검증: 모두 통과")

    if broken_urls:
        log(f"  URL 형식 불량 {len(broken_urls)}건:")
        for e in broken_urls:
            log(f"    {e}")
    else:
        log("  URL 형식 검사: 모두 통과")

    if dup_urls:
        log(f"  중복 URL {len(dup_urls)}건: {dup_urls}")
    else:
        log("  중복 URL: 없음")

    valid_url_count = len(candidates) - len(broken_urls)
    validity_rate = valid_url_count / len(candidates) if candidates else 0.0
    log(f"\n  URL 유효율: {validity_rate:.0%} ({valid_url_count}/{len(candidates)})")

    # 리포트 저장
    report = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "total_candidates": len(candidates),
        "reviewed": status_counts.get("reviewed", 0),
        "pending": status_counts.get("pending", 0),
        "rejected": status_counts.get("rejected", 0),
        "metadata_total": len(metadata),
        "metadata_reviewed": meta_status.get("reviewed", 0),
        "metadata_pending": meta_status.get("pending", 0),
        "broken_links": len(broken_urls),
        "duplicate_urls": len(dup_urls),
        "schema_errors": len(schema_errors),
        "url_validity_rate": round(validity_rate, 4),
        "top_domains": domain_counter.most_common(10),
        "schema_error_details": schema_errors,
        "broken_link_details": broken_urls,
    }

    report_path = output_dir / "link_resolution_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"\n리포트 저장: {report_path}")
    return report


def main() -> None:
    report = run_validation()

    # 종료 코드
    if report["schema_errors"] or report["url_validity_rate"] < 0.9:
        print("\n[FAIL] 완료 기준 미충족")
        sys.exit(1)
    print("\n[PASS] 모든 완료 기준 충족")


if __name__ == "__main__":
    main()
