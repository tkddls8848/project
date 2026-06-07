"""match_services.py

link_candidates.jsonl 을 읽어 gov24_service_metadata.jsonl 을 생성합니다.
- 도메인 키워드 매핑으로 domain_ids 자동 부여
- review_status 'rejected' 레코드는 제외
"""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKING = ROOT / "data" / "working"
OUTPUT = ROOT / "data" / "output"
CANDIDATES_FILE = WORKING / "link_candidates.jsonl"
METADATA_FILE = OUTPUT / "gov24_service_metadata.jsonl"

KST = timezone(timedelta(hours=9))

# 도메인 키워드 매핑
DOMAIN_MAP: list[tuple[list[str], str]] = [
    (["사업자등록", "사업자", "폐업", "법인설립", "법인등기"], "business_registration"),
    (["통신판매", "전자상거래", "쇼핑몰", "온라인판매"], "ecommerce"),
    (["식품", "위생교육", "영업신고", "식품제조", "음식점"], "food_business"),
    (["건강보험", "국민연금", "고용보험", "산재보험", "4대보험", "근로"], "social_insurance"),
    (["부가가치세", "종합소득세", "지방소득세", "세금", "납세", "납부"], "tax"),
    (["창업", "소상공인", "정책자금", "스타트업"], "startup_support"),
    (["영업허가", "영업신고", "허가", "신고"], "business_permit"),
]

# 링크 유형 키워드
LINK_TYPE_MAP: list[tuple[list[str], str]] = [
    (["신청", "신고", "등록", "제출", "납부", "취득", "성립"], "application"),
    (["안내", "포털", "정보", "지원", "교육"], "guide"),
    (["조회", "상태", "확인", "발급"], "info"),
    (["홈페이지", "공단", "위원회", "공사", "진흥", "협회"], "agency"),
]

# 기관 ID 매핑
AGENCY_MAP: list[tuple[list[str], str]] = [
    (["홈택스", "국세청"], "agency:nts"),
    (["공정거래위원회", "공정위", "ftc"], "agency:ftc"),
    (["식품의약품안전처", "식약처", "식품안전나라", "mfds", "foodsafety"], "agency:mfds"),
    (["국민건강보험", "건강보험", "nhis"], "agency:nhis"),
    (["국민연금", "nps"], "agency:nps"),
    (["근로복지공단", "고용보험", "산재보험", "comwel"], "agency:comwel"),
    (["위택스", "지방세"], "agency:wetax"),
    (["소상공인시장진흥공단", "소진공", "semas"], "agency:semas"),
    (["중소벤처기업부", "k-startup", "창업지원"], "agency:msit"),
    (["대법원", "인터넷등기소", "iros"], "agency:scourt"),
    (["고용노동부", "moel"], "agency:moel"),
    (["정부24", "gov.kr"], "agency:gov24"),
]


def detect_domains(text: str) -> list[str]:
    text_l = text.lower()
    domains = []
    for keywords, domain in DOMAIN_MAP:
        if any(k in text_l for k in keywords):
            domains.append(domain)
    return domains or ["general"]


def detect_link_type(text: str) -> str:
    text_l = text.lower()
    for keywords, ltype in LINK_TYPE_MAP:
        if any(k in text_l for k in keywords):
            return ltype
    return "info"


def detect_agencies(text: str, url: str) -> list[str]:
    combined = (text + " " + url).lower()
    agencies = []
    for keywords, agency_id in AGENCY_MAP:
        if any(k in combined for k in keywords):
            agencies.append(agency_id)
    return agencies


def make_link_id(domain_ids: list[str], seq: int) -> str:
    domain = domain_ids[0] if domain_ids else "general"
    return f"gov24:service:{domain}_{seq:03d}"


def main() -> None:
    if not CANDIDATES_FILE.exists():
        print(f"파일 없음: {CANDIDATES_FILE}")
        sys.exit(1)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(KST).isoformat(timespec="seconds")

    records: list[dict] = []
    with CANDIDATES_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"읽은 후보: {len(records)}건")

    metadata: list[dict] = []
    for i, rec in enumerate(records, 1):
        if rec.get("review_status") == "rejected":
            continue

        title = rec.get("title", "")
        url = rec.get("url", "")
        combined_text = f"{title} {rec.get('matched_query', '')} {rec.get('matched_service_name', '')}"

        domain_ids = detect_domains(combined_text)
        link_type = detect_link_type(combined_text)
        related_agency_ids = detect_agencies(combined_text, url)

        keywords = list({
            k.strip()
            for k in re.split(r"[\s,·/]+", combined_text)
            if len(k.strip()) >= 2
        })[:10]

        metadata.append({
            "link_id": make_link_id(domain_ids, i),
            "source": "gov24" if "gov.kr" in url else "agency",
            "external_id": rec.get("candidate_id", ""),
            "title": title,
            "url": url,
            "link_type": link_type,
            "domain_ids": domain_ids,
            "related_service_ids": [],
            "related_agency_ids": related_agency_ids,
            "keywords": keywords,
            "confidence": rec.get("confidence", 0.5),
            "review_status": rec.get("review_status", "pending"),
            "collected_at": collected_at,
            "source_url": rec.get("url", ""),
            "notes": rec.get("notes", ""),
        })

    with METADATA_FILE.open("w", encoding="utf-8") as f:
        for m in metadata:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    reviewed = sum(1 for m in metadata if m["review_status"] == "reviewed")
    print(f"생성: {len(metadata)}건 (reviewed={reviewed}, pending={len(metadata)-reviewed})")
    print(f"저장: {METADATA_FILE}")


if __name__ == "__main__":
    main()
