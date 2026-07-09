"""collect_manual_seed.py

새 링크 후보를 link_candidates.jsonl 에 대화형으로 추가하는 헬퍼.
실행 후 입력값이 없으면 종료합니다.
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_FILE = ROOT / "data" / "working" / "link_candidates.jsonl"
KST = timezone(timedelta(hours=9))


def next_seq(existing: list[dict]) -> int:
    ids = [r.get("candidate_id", "") for r in existing]
    nums = []
    for cid in ids:
        parts = cid.split(":")
        if parts and parts[-1].isdigit():
            nums.append(int(parts[-1]))
    return max(nums, default=0) + 1


def load_existing() -> list[dict]:
    if not CANDIDATES_FILE.exists():
        return []
    records = []
    with CANDIDATES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def prompt(label: str, default: str = "") -> str:
    val = input(f"  {label}{f' [{default}]' if default else ''}: ").strip()
    return val or default


def main() -> None:
    existing = load_existing()
    print(f"현재 후보 수: {len(existing)}건")
    print("새 링크 후보 추가 (빈 입력으로 종료)\n")

    seq = next_seq(existing)
    added = 0

    while True:
        print(f"── 후보 #{seq} ──")
        title = prompt("제목")
        if not title:
            break
        url = prompt("URL (https://...)")
        if not url.startswith("http"):
            print("  URL은 http:// 또는 https:// 로 시작해야 합니다.")
            continue

        source = prompt("출처", "manual")
        matched_query = prompt("검색 쿼리")
        matched_service_name = prompt("매핑 서비스명")
        match_reason = prompt("매핑 이유", "title_keyword_overlap")
        confidence_str = prompt("신뢰도 (0~1)", "0.70")
        try:
            confidence = float(confidence_str)
        except ValueError:
            confidence = 0.70
        review_status = prompt("검수 상태 (pending/reviewed/rejected)", "pending")
        notes = prompt("비고")

        record = {
            "candidate_id": f"candidate:gov24:{seq:03d}",
            "title": title,
            "url": url,
            "source": source,
            "matched_query": matched_query,
            "matched_service_name": matched_service_name,
            "match_reason": match_reason,
            "confidence": confidence,
            "review_status": review_status,
        }
        if notes:
            record["notes"] = notes

        with CANDIDATES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        print(f"  저장됨: {record['candidate_id']}\n")
        seq += 1
        added += 1

    print(f"\n추가 완료: {added}건 → 총 {len(existing) + added}건")


if __name__ == "__main__":
    main()
