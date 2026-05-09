"""
Stage 3: 02_catalog -> 03_semantic.

Loads the administrative standard term/word CSVs, then creates the minimum
rule-based semantic layer needed by the MVP plan.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

KST = timezone(timedelta(hours=9))
CATALOG_DIR_NAME = "02_catalog"
SEMANTIC_DIR_NAME = "03_semantic"

DOMAIN_ID_BY_LABEL = {
    "공공행정": "public_admin",
    "일반공공행정": "public_admin",
    "과학기술": "science_tech",
    "교육": "education",
    "교통물류": "transport_logistics",
    "교통및물류": "transport_logistics",
    "국토관리": "land_management",
    "농축수산": "agriculture_fisheries",
    "농림축산식품": "agriculture_fisheries",
    "문화관광": "culture_tourism",
    "문화체육관광": "culture_tourism",
    "법률": "law",
    "보건의료": "healthcare",
    "사회복지": "social_welfare",
    "산업고용": "industry",
    "산업통상중소기업": "industry",
    "식품건강": "food_health",
    "재난안전": "safety",
    "공공질서및안전": "safety",
    "재정금융": "finance",
    "통일외교안보": "diplomacy_security",
    "통일외교": "diplomacy_security",
    "환경기상": "environment_weather",
}

RULE_CONCEPTS = [
    {
        "concept_id": "industry.energy",
        "canonical_name": "에너지",
        "domain_ids": ["industry"],
        "keywords": ["연료", "LNG", "석탄", "발전", "에너지", "소비", "도입", "가스"],
        "match_any": ["연료", "LNG", "석탄", "발전", "에너지", "가스"],
    },
    {
        "concept_id": "industry.fuel_import",
        "canonical_name": "연료 도입 실적",
        "domain_ids": ["industry"],
        "keywords": ["연료도입", "도입실적", "연료 도입", "도입량"],
        "match_any": ["연료도입", "연료 도입", "도입실적", "도입량"],
    },
    {
        "concept_id": "industry.fuel_consumption",
        "canonical_name": "연료 소비량",
        "domain_ids": ["industry"],
        "keywords": ["연료소비", "소비량", "연료 사용량", "소비실적"],
        "match_any": ["연료소비", "연료 소비", "연료 사용량", "소비실적", "소비량"],
    },
    {
        "concept_id": "transport.bus_stop",
        "canonical_name": "버스 정류소",
        "domain_ids": ["transport_logistics"],
        "keywords": ["버스", "정류소", "정류장", "노선", "교통"],
        "match_any": ["버스", "정류소", "정류장", "노선"],
    },
    {
        "concept_id": "culture.facility",
        "canonical_name": "문화시설",
        "domain_ids": ["culture_tourism"],
        "keywords": ["문화시설", "문화", "관광", "시설", "여행지"],
        "match_any": ["문화시설", "관광", "여행지"],
    },
    {
        "concept_id": "culture.restaurant",
        "canonical_name": "식당",
        "domain_ids": ["culture_tourism"],
        "keywords": ["식당", "음식", "맛집", "음식점"],
        "match_any": ["식당", "맛집", "음식점"],
    },
    {
        "concept_id": "diplomacy.travel_warning",
        "canonical_name": "여행경보",
        "domain_ids": ["diplomacy_security"],
        "keywords": ["여행경보", "해외안전", "여행", "출국", "경보", "국가정보"],
        "match_any": ["여행경보", "해외안전", "출국권고", "여행금지"],
    },
    {
        "concept_id": "public_admin.identifier",
        "canonical_name": "행정 식별자",
        "domain_ids": ["public_admin"],
        "keywords": ["사업자등록번호", "법인등록번호", "기관코드", "행정동코드", "등록번호"],
        "match_any": ["사업자등록번호", "법인등록번호", "기관코드", "행정동코드"],
    },
]

SAMPLE_QUERY_EXAMPLES = [
    "연료 도입 실적",
    "연료 소비량",
    "버스 정류소 위치",
    "문화시설 식당 정보",
    "여행경보 목록",
    "사업자등록번호",
    "법인등록번호",
    "endpoint path",
    "응답 필드",
]


def now_iso() -> str:
    return datetime.now(KST).isoformat()


def clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).replace("\ufeff", "").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def atomic_write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    os.replace(tmp_path, path)


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def split_aliases(value) -> list[str]:
    aliases = []
    seen = set()
    for part in re.split(r"[,;/|]", clean_text(value)):
        alias = part.strip()
        if alias and alias not in seen:
            seen.add(alias)
            aliases.append(alias)
    return aliases


def normalize_identifier(value) -> str:
    text = clean_text(value).lower()
    cond_match = re.search(r"cond\[([^:\]]+)", text)
    if cond_match:
        text = cond_match.group(1)
    text = re.sub(r"[^0-9a-z가-힣]+", "", text)
    return text


def identifier_tokens(value) -> list[str]:
    text = clean_text(value)
    cond_match = re.search(r"cond\[([^:\]]+)", text, re.IGNORECASE)
    if cond_match:
        text = cond_match.group(1)
    return [part.upper() for part in re.split(r"[^0-9A-Za-z가-힣]+", text) if part]


def parse_allowed_values(value) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,;/|]", text) if part.strip()]


def infer_field_type(storage_format: str, domain: str = "") -> str:
    text = f"{storage_format} {domain}"
    if "여부" in text:
        return "boolean"
    if "일시" in text:
        return "datetime"
    if "일자" in text or "날짜" in text:
        return "date"
    if "숫자" in text or "정수" in text or re.search(r"[NC]\d", text):
        return "number"
    if "문자" in text or "명" in text:
        return "char"
    return ""


def normalize_domain_id(label: str) -> str | None:
    text = clean_text(label)
    if not text:
        return None
    primary = re.split(r"[-/>]", text)[0]
    normalized = re.sub(r"[^0-9A-Za-z가-힣]", "", primary)
    for key, domain_id in sorted(DOMAIN_ID_BY_LABEL.items(), key=lambda item: len(item[0]), reverse=True):
        if key in normalized or normalized in key:
            return domain_id
    return None


def parse_category_markdown(path: Path) -> list[str]:
    if not path.exists():
        return []
    categories = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or not cells[0].isdigit():
            continue
        categories.append(cells[1])
    return categories


def load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_taxonomy(stage0_dir: Path) -> dict:
    ui_categories = parse_category_markdown(stage0_dir / "category.md")
    if not ui_categories:
        ui_categories = [
            "공공행정",
            "과학기술",
            "교육",
            "교통물류",
            "국토관리",
            "농축수산",
            "문화관광",
            "법률",
            "보건의료",
            "사회복지",
            "산업고용",
            "식품건강",
            "재난안전",
            "재정금융",
            "통일외교안보",
            "환경기상",
        ]
    return {
        "generated_at": now_iso(),
        "ui_categories": ui_categories,
        "ui_to_domain": {category: normalize_domain_id(category) for category in ui_categories},
        "term_domain_to_id": {
            label: domain_id
            for label, domain_id in DOMAIN_ID_BY_LABEL.items()
            if label in ui_categories or domain_id in {"public_admin", "industry", "food_health"}
        },
        "allowed_domain_ids": sorted(set(DOMAIN_ID_BY_LABEL.values())),
    }


def build_term_dictionary(word_rows: list[dict]) -> tuple[list[dict], dict[str, dict], list[dict]]:
    records = []
    suffix_words = []
    by_abbr = {}
    for row in word_rows:
        abbr = clean_text(row.get("공통표준단어영문약어명"))
        name_ko = clean_text(row.get("공통표준단어명"))
        if not abbr or not name_ko:
            continue
        record = {
            "word_id": f"word:{abbr}",
            "name_ko": name_ko,
            "abbr_en": abbr,
            "name_en": clean_text(row.get("공통표준단어 영문명")),
            "description": clean_text(row.get("공통표준단어 설명")),
            "domain_class": clean_text(row.get("공통표준도메인분류명")),
            "is_format_word": clean_text(row.get("형식단어여부")).upper() == "Y",
            "aliases": split_aliases(row.get("이음동의어 목록")),
        }
        records.append(record)
        by_abbr[abbr.upper()] = record
        if record["is_format_word"]:
            suffix_words.append(record)
    return records, by_abbr, suffix_words


def build_term_definitions(term_rows: list[dict], word_by_abbr: dict[str, dict]) -> list[dict]:
    records = []
    for row in term_rows:
        abbr = clean_text(row.get("공통표준용어영문약어명"))
        name_ko = clean_text(row.get("공통표준용어명"))
        if not abbr or not name_ko:
            continue
        storage_format = clean_text(row.get("저장 형식"))
        display_format = clean_text(row.get("표현 형식")) or None
        constituent_words = [
            word_by_abbr[token]["word_id"]
            for token in abbr.split("_")
            if token.upper() in word_by_abbr
        ]
        records.append(
            {
                "term_id": f"term:{abbr}",
                "name_ko": name_ko,
                "abbr_en": abbr,
                "description": clean_text(row.get("공통표준용어설명")),
                "domain": clean_text(row.get("공통표준도메인명")),
                "field_type": infer_field_type(storage_format, clean_text(row.get("공통표준도메인명"))),
                "field_format": storage_format,
                "display_format": display_format,
                "allowed_values": parse_allowed_values(row.get("허용값")),
                "code_link": clean_text(row.get("행정표준코드명")) or None,
                "owner_agency": clean_text(row.get("소관기관명")) or None,
                "aliases": split_aliases(row.get("용어 이음동의어 목록")),
                "constituent_words": constituent_words,
            }
        )
    return records


def add_alias(alias_records: list[dict], seen: set[tuple[str, str]], concept_id: str, alias: str, source: str) -> None:
    alias = clean_text(alias)
    if not alias:
        return
    key = (concept_id, alias.lower())
    if key in seen:
        return
    seen.add(key)
    alias_records.append(
        {
            "alias_id": stable_id("alias", concept_id, alias),
            "concept_id": concept_id,
            "alias": alias,
            "source": source,
            "confidence": 0.9 if source.startswith("term_") else 0.6,
            "review_status": "rule_accepted" if source.startswith("term_") else "pending",
            "evidence": [source],
            "match_source": source,
        }
    )


def build_term_indexes(term_definitions: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    by_abbr = {}
    for term in term_definitions:
        by_abbr.setdefault(normalize_identifier(term.get("abbr_en")), term)
    return by_abbr, term_definitions


def match_field(field: dict, term_by_abbr: dict[str, dict], terms: list[dict], word_by_abbr: dict[str, dict]) -> dict:
    field_name = clean_text(field.get("field_name"))
    description = clean_text(field.get("description"))
    field_key = normalize_identifier(field_name)
    term = term_by_abbr.get(field_key)
    if term:
        return {
            "concept_id": term["term_id"],
            "term_canonical_ko": term["name_ko"],
            "aliases": [term["name_ko"], term.get("abbr_en"), field_name, *term.get("aliases", [])],
            "field_type": term.get("field_type") or field.get("field_type", ""),
            "field_format": term.get("field_format", ""),
            "display_format": term.get("display_format"),
            "allowed_values": term.get("allowed_values", []),
            "code_link": term.get("code_link"),
            "owner_agency": term.get("owner_agency"),
            "match_source": "term_definitions.abbr_en",
            "confidence": 0.95,
            "review_status": "rule_accepted",
            "evidence": ["field_name", "term_definitions.abbr_en"],
        }

    if description:
        for candidate in terms:
            names = [candidate.get("name_ko"), *candidate.get("aliases", [])]
            if any(name and name in description for name in names):
                return {
                    "concept_id": candidate["term_id"],
                    "term_canonical_ko": candidate["name_ko"],
                    "aliases": [candidate["name_ko"], candidate.get("abbr_en"), field_name, *candidate.get("aliases", [])],
                    "field_type": candidate.get("field_type") or field.get("field_type", ""),
                    "field_format": candidate.get("field_format", ""),
                    "display_format": candidate.get("display_format"),
                    "allowed_values": candidate.get("allowed_values", []),
                    "code_link": candidate.get("code_link"),
                    "owner_agency": candidate.get("owner_agency"),
                    "match_source": "term_definitions.alias",
                    "confidence": 0.85,
                    "review_status": "rule_accepted",
                    "evidence": ["field_description", "term_definitions.alias"],
                }

    tokens = identifier_tokens(field_name)
    word_matches = [word_by_abbr[token] for token in tokens if token in word_by_abbr]
    if tokens and word_matches and len(word_matches) == len(tokens):
        concept_id = "compound:" + "_".join(token.lower() for token in tokens)
        return {
            "concept_id": concept_id,
            "term_canonical_ko": "".join(word["name_ko"] for word in word_matches),
            "aliases": [field_name, description, *[word["name_ko"] for word in word_matches]],
            "field_type": field.get("field_type", ""),
            "field_format": "",
            "display_format": None,
            "allowed_values": [],
            "code_link": None,
            "owner_agency": None,
            "match_source": "term_dictionary.compose",
            "confidence": 0.75,
            "review_status": "rule_accepted",
            "evidence": ["field_name", "term_dictionary"],
        }

    concept_key = re.sub(r"[^0-9a-z가-힣]+", "_", field_name.lower()).strip("_") or field_key or "unknown"
    return {
        "concept_id": f"field.{concept_key}",
        "term_canonical_ko": description or field_name,
        "aliases": [field_name, description],
        "field_type": field.get("field_type", ""),
        "field_format": "",
        "display_format": None,
        "allowed_values": [],
        "code_link": None,
        "owner_agency": None,
        "match_source": "rule_only",
        "confidence": 0.45,
        "review_status": "pending",
        "evidence": ["field_name", "field_description"],
    }


class Stage3SemanticBuilder:
    def __init__(self, base_dir: str | Path, data_type: str | None = None):
        self.base_dir = Path(base_dir)
        self.data_type = data_type
        self.catalog_dir = self.base_dir / "data" / CATALOG_DIR_NAME
        self.output_dir = self.base_dir / "data" / SEMANTIC_DIR_NAME
        self.stage0_dir = self.base_dir / "stage0_term_definition" / "data"

    def build(self) -> None:
        if not self.catalog_dir.exists():
            print(f"[error] 카탈로그 디렉터리 없음: {self.catalog_dir}")
            print("  먼저 stage2_catalog/main.py 를 실행하세요.")
            sys.exit(1)

        services = self._filter_by_data_type(read_jsonl(self.catalog_dir / "services.jsonl"))
        documents = self._filter_by_data_type(read_jsonl(self.catalog_dir / "documents.jsonl"))
        endpoints = self._filter_by_data_type(read_jsonl(self.catalog_dir / "endpoints.jsonl"))
        fields = self._filter_by_data_type(read_jsonl(self.catalog_dir / "fields.jsonl"))

        taxonomy = build_taxonomy(self.stage0_dir)
        word_records, word_by_abbr, suffix_words = build_term_dictionary(
            load_csv_rows(self.stage0_dir / "공통표준단어_점검.csv")
        )
        term_definitions = build_term_definitions(
            load_csv_rows(self.stage0_dir / "공통표준용어_최종.csv"),
            word_by_abbr,
        )
        term_by_abbr, terms = build_term_indexes(term_definitions)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.output_dir / "category_taxonomy.json", taxonomy)
        atomic_write_json(self.output_dir / "taxonomy.json", taxonomy)
        atomic_write_jsonl(self.output_dir / "term_dictionary.jsonl", word_records)
        atomic_write_jsonl(self.output_dir / "term_definitions.jsonl", term_definitions)
        atomic_write_json(
            self.output_dir / "suffix_words.json",
            {"generated_at": now_iso(), "suffix_words": suffix_words},
        )

        field_mappings, field_concepts, alias_records = self._build_field_mappings(
            fields, term_by_abbr, terms, word_by_abbr
        )
        concepts = self._build_concepts(taxonomy, term_definitions, field_concepts)
        service_tags = self._build_service_tags(services, documents, fields, field_mappings)
        aliases = self._build_aliases(term_definitions, word_records, field_mappings, alias_records)
        concept_relations = self._build_concept_relations(concepts)
        agency_glossary = self._build_agency_glossary(services)
        query_examples = [
            {
                "query": query,
                "source": "semantic_mvp_plan",
                "confidence": 1.0,
                "review_status": "rule_accepted",
                "evidence": ["docs/02_semantic_mvp_plan.md"],
                "match_source": "manual_seed",
            }
            for query in SAMPLE_QUERY_EXAMPLES
        ]

        atomic_write_jsonl(self.output_dir / "concepts.jsonl", concepts)
        atomic_write_jsonl(self.output_dir / "service_tags.jsonl", service_tags)
        atomic_write_jsonl(self.output_dir / "aliases.jsonl", aliases)
        atomic_write_jsonl(self.output_dir / "field_mappings.jsonl", field_mappings)
        atomic_write_jsonl(self.output_dir / "concept_relations.jsonl", concept_relations)
        atomic_write_jsonl(self.output_dir / "agency_glossary.jsonl", agency_glossary)
        atomic_write_jsonl(self.output_dir / "query_examples.jsonl", query_examples)

        print("Stage 3 complete")
        print(f"  services:          {len(services)}")
        print(f"  fields:            {len(fields)}")
        print(f"  term_dictionary:   {len(word_records)}")
        print(f"  term_definitions:  {len(term_definitions)}")
        print(f"  concepts:          {len(concepts)}")
        print(f"  service_tags:      {len(service_tags)}")
        print(f"  field_mappings:    {len(field_mappings)}")
        print(f"  output:            {self.output_dir}")

    def _filter_by_data_type(self, records: list[dict]) -> list[dict]:
        if not self.data_type:
            return records
        return [record for record in records if record.get("data_type") == self.data_type]

    def _build_field_mappings(
        self,
        fields: list[dict],
        term_by_abbr: dict[str, dict],
        terms: list[dict],
        word_by_abbr: dict[str, dict],
    ) -> tuple[list[dict], dict[str, dict], list[dict]]:
        mappings = []
        concepts = {}
        aliases = []
        alias_seen: set[tuple[str, str]] = set()
        for field in fields:
            match = match_field(field, term_by_abbr, terms, word_by_abbr)
            mapping = {
                "field_id": field.get("field_id"),
                "service_id": field.get("service_id"),
                "endpoint_id": field.get("endpoint_id"),
                "field_name": field.get("field_name"),
                "field_role": field.get("field_role"),
                "field_path": field.get("field_path"),
                "concept_id": match["concept_id"],
                "term_canonical_ko": match["term_canonical_ko"],
                "aliases": [alias for alias in match["aliases"] if alias],
                "field_type": match["field_type"],
                "field_format": match["field_format"],
                "display_format": match["display_format"],
                "allowed_values": match["allowed_values"],
                "code_link": match["code_link"],
                "owner_agency": match["owner_agency"],
                "match_source": match["match_source"],
                "confidence": match["confidence"],
                "review_status": match["review_status"],
                "evidence": match["evidence"],
            }
            mappings.append(mapping)
            if not match["concept_id"].startswith("term:"):
                concepts.setdefault(
                    match["concept_id"],
                    {
                        "concept_id": match["concept_id"],
                        "canonical_name": match["term_canonical_ko"],
                        "description": field.get("description", ""),
                        "domain_ids": [],
                        "concept_type": "field_candidate",
                        "confidence": match["confidence"],
                        "review_status": match["review_status"],
                        "evidence": match["evidence"],
                        "match_source": match["match_source"],
                    },
                )
            for alias in mapping["aliases"]:
                add_alias(aliases, alias_seen, mapping["concept_id"], alias, mapping["match_source"])
        return mappings, concepts, aliases

    def _build_concepts(self, taxonomy: dict, term_definitions: list[dict], field_concepts: dict[str, dict]) -> list[dict]:
        concepts: dict[str, dict] = {}
        label_by_domain = {domain_id: label for label, domain_id in DOMAIN_ID_BY_LABEL.items()}
        for domain_id in taxonomy.get("allowed_domain_ids", []):
            concepts[f"domain:{domain_id}"] = {
                "concept_id": f"domain:{domain_id}",
                "canonical_name": label_by_domain.get(domain_id, domain_id),
                "description": "data.go.kr category domain",
                "domain_ids": [domain_id],
                "concept_type": "domain",
                "confidence": 1.0,
                "review_status": "rule_accepted",
                "evidence": ["category_taxonomy"],
                "match_source": "category_taxonomy",
            }

        for rule in RULE_CONCEPTS:
            concepts[rule["concept_id"]] = {
                "concept_id": rule["concept_id"],
                "canonical_name": rule["canonical_name"],
                "description": "Rule-based MVP concept",
                "domain_ids": rule["domain_ids"],
                "concept_type": "rule",
                "keywords": rule["keywords"],
                "confidence": 0.85,
                "review_status": "rule_accepted",
                "evidence": ["semantic_rule"],
                "match_source": "rule_only",
            }

        for term in term_definitions:
            concepts[term["term_id"]] = {
                "concept_id": term["term_id"],
                "canonical_name": term["name_ko"],
                "abbr_en": term["abbr_en"],
                "description": term.get("description", ""),
                "domain_ids": [],
                "concept_type": "term",
                "confidence": 1.0,
                "review_status": "rule_accepted",
                "evidence": ["term_definitions"],
                "match_source": "term_definitions",
            }

        concepts.update(field_concepts)
        return list(concepts.values())

    def _build_service_tags(
        self,
        services: list[dict],
        documents: list[dict],
        fields: list[dict],
        field_mappings: list[dict],
    ) -> list[dict]:
        document_by_service = {document.get("service_id"): document for document in documents}
        fields_by_service: dict[str, list[dict]] = defaultdict(list)
        mappings_by_service: dict[str, list[dict]] = defaultdict(list)
        for field in fields:
            fields_by_service[field.get("service_id")].append(field)
        for mapping in field_mappings:
            mappings_by_service[mapping.get("service_id")].append(mapping)

        tags = []
        for service in services:
            service_id = service.get("service_id")
            document = document_by_service.get(service_id, {})
            service_fields = fields_by_service.get(service_id, [])
            text = " ".join(
                [
                    clean_text(service.get("name")),
                    clean_text(service.get("description")),
                    " ".join(service.get("keywords") or []),
                    clean_text(service.get("category")),
                    clean_text(document.get("body")),
                    " ".join(clean_text(field.get("description")) for field in service_fields),
                ]
            )
            domain_id = normalize_domain_id(service.get("category", ""))
            domain_ids = [domain_id] if domain_id else []
            concept_ids = []
            evidence = []
            for rule in RULE_CONCEPTS:
                match_terms = rule.get("match_any") or rule["keywords"]
                if any(keyword and keyword.lower() in text.lower() for keyword in match_terms):
                    concept_ids.append(rule["concept_id"])
                    evidence.append("semantic_rule")
            for mapping in mappings_by_service.get(service_id, [])[:20]:
                if mapping.get("concept_id"):
                    concept_ids.append(mapping["concept_id"])
                    evidence.append("field_mappings")
            if domain_id:
                evidence.append("category")
            if not concept_ids and domain_id:
                concept_ids.append(f"domain:{domain_id}")
            deduped_concepts = []
            for concept_id in concept_ids:
                if concept_id not in deduped_concepts:
                    deduped_concepts.append(concept_id)
            evidence_set = sorted(set(evidence)) or ["service_metadata"]
            if "semantic_rule" in evidence_set:
                match_source = "rule_only"
                confidence = 0.85
            elif "field_mappings" in evidence_set:
                match_source = "field_mappings"
                confidence = 0.75
            elif domain_id:
                match_source = "taxonomy.category"
                confidence = 0.65
            else:
                match_source = "rule_only"
                confidence = 0.4

            tags.append(
                {
                    "service_id": service_id,
                    "domain_ids": domain_ids,
                    "concept_ids": deduped_concepts,
                    "evidence": evidence_set,
                    "confidence": confidence,
                    "review_status": "rule_accepted" if domain_ids or deduped_concepts else "pending",
                    "match_source": match_source,
                }
            )
        return tags

    def _build_aliases(
        self,
        term_definitions: list[dict],
        word_records: list[dict],
        field_mappings: list[dict],
        prebuilt: list[dict],
    ) -> list[dict]:
        aliases = list(prebuilt)
        seen = {(record["concept_id"], record["alias"].lower()) for record in aliases}
        for term in term_definitions:
            add_alias(aliases, seen, term["term_id"], term["name_ko"], "term_definitions.name_ko")
            add_alias(aliases, seen, term["term_id"], term["abbr_en"], "term_definitions.abbr_en")
            for alias in term.get("aliases", []):
                add_alias(aliases, seen, term["term_id"], alias, "term_definitions.alias")
        for word in word_records:
            add_alias(aliases, seen, word["word_id"], word["name_ko"], "term_dictionary.name_ko")
            add_alias(aliases, seen, word["word_id"], word["abbr_en"], "term_dictionary.abbr_en")
            for alias in word.get("aliases", []):
                add_alias(aliases, seen, word["word_id"], alias, "term_dictionary.alias")
        for mapping in field_mappings:
            for alias in mapping.get("aliases", []):
                add_alias(aliases, seen, mapping["concept_id"], alias, "field_mappings")
        return aliases

    def _build_concept_relations(self, concepts: list[dict]) -> list[dict]:
        relations = []
        for concept in concepts:
            for domain_id in concept.get("domain_ids") or []:
                if concept["concept_id"] == f"domain:{domain_id}":
                    continue
                relations.append(
                    {
                        "relation_id": stable_id("rel", f"domain:{domain_id}", concept["concept_id"]),
                        "source_concept_id": f"domain:{domain_id}",
                        "target_concept_id": concept["concept_id"],
                        "relation_type": "contains",
                        "confidence": concept.get("confidence", 0.8),
                        "review_status": concept.get("review_status", "rule_accepted"),
                        "evidence": concept.get("evidence", []),
                        "match_source": concept.get("match_source", "rule_only"),
                    }
                )
        return relations

    def _build_agency_glossary(self, services: list[dict]) -> list[dict]:
        records = []
        seen = set()
        for service in services:
            agency_id = service.get("provider_agency_id")
            agency_name = service.get("provider_agency_name")
            if not agency_id or not agency_name or agency_id in seen:
                continue
            seen.add(agency_id)
            records.append(
                {
                    "agency_id": agency_id,
                    "canonical_name": agency_name,
                    "aliases": [agency_name],
                    "confidence": 0.8,
                    "review_status": "rule_accepted",
                    "evidence": ["services.provider_agency_name"],
                    "match_source": "service_metadata",
                }
            )
        return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 3: catalog -> semantic layer")
    parser.add_argument(
        "--data-type",
        choices=["openapi", "fileData", "standard"],
        help="특정 데이터 타입만 처리 (미지정 시 전체)",
    )
    args = parser.parse_args()
    Stage3SemanticBuilder(BASE_DIR, data_type=args.data_type).build()


if __name__ == "__main__":
    main()
