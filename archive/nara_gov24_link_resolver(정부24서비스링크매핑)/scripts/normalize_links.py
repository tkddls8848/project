"""normalize_links.py

data/working/link_candidates.jsonl 을 읽어 URL 정규화·중복 제거 후 덮어씁니다.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

ROOT = Path(__file__).resolve().parent.parent
WORKING = ROOT / "data" / "working"
CANDIDATES_FILE = WORKING / "link_candidates.jsonl"


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    # 소문자 scheme/host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    # 불필요한 trailing slash 제거 (경로가 단순 '/' 이면 유지)
    path = parsed.path.rstrip("/") or "/"
    # 쿼리 파라미터 정렬
    qs = parse_qs(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(qs.items()), doseq=True)
    return urlunparse((scheme, netloc, path, "", sorted_query, ""))


def is_valid_url(url: str) -> bool:
    return bool(re.match(r"^https?://.+", url))


def load_candidates(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [WARN] 줄 {i} JSON 파싱 실패: {e}", file=sys.stderr)
    return records


def deduplicate(records: list[dict]) -> tuple[list[dict], int]:
    seen: dict[str, str] = {}  # canonical_url -> candidate_id
    unique = []
    dup_count = 0
    for rec in records:
        canon = canonicalize_url(rec.get("url", ""))
        if canon in seen:
            print(f"  [DUP] {rec['candidate_id']} 중복 ({seen[canon]}와 동일 URL)")
            dup_count += 1
        else:
            seen[canon] = rec["candidate_id"]
            rec["url"] = canonicalize_url(rec["url"])
            unique.append(rec)
    return unique, dup_count


def main() -> None:
    if not CANDIDATES_FILE.exists():
        print(f"파일 없음: {CANDIDATES_FILE}")
        sys.exit(1)

    print(f"읽는 중: {CANDIDATES_FILE}")
    records = load_candidates(CANDIDATES_FILE)
    print(f"  로드: {len(records)}건")

    # URL 유효성
    invalid = [r for r in records if not is_valid_url(r.get("url", ""))]
    if invalid:
        print(f"  [WARN] URL 형식 불량 {len(invalid)}건:")
        for r in invalid:
            print(f"    - {r['candidate_id']}: {r.get('url')}")

    # 정규화 및 중복 제거
    unique, dup_count = deduplicate(records)
    print(f"  중복 제거: {dup_count}건 → 최종 {len(unique)}건")

    # 정렬 (candidate_id)
    unique.sort(key=lambda x: x["candidate_id"])

    # 덮어쓰기
    with CANDIDATES_FILE.open("w", encoding="utf-8") as f:
        for rec in unique:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"저장 완료: {CANDIDATES_FILE}")


if __name__ == "__main__":
    main()
