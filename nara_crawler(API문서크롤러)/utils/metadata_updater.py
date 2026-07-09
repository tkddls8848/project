# -*- coding: utf-8 -*-
"""
==============================================================================
메타데이터 목록 CSV 자동 갱신기 (Metadata List CSV Auto-Updater)
==============================================================================

목적 (Purpose):
    공공데이터포털의 "목록관리현황" 데이터셋(15062804)을 방문하여, 페이지에
    표시된 등록일/수정일을 로컬 ``date.json`` 과 비교합니다. 포털이 더 최신이거나
    대상 CSV가 없으면 전체 목록 CSV를 내려받아 "목록유형" 열(API/FILE/STD)로
    분류해 각각의 크롤러 입력 파일로 저장합니다.

동작 (Flow):
    1. 15062804 fileData 상세 페이지 조회
    2. FileDataCrawler 의 표 파싱(_extract_table_bs)으로 등록일/수정일 추출
    3. scanner/database/date.json 의 날짜와 비교
    4. 신규(또는 대상 CSV 누락)이면 JSON-LD 다운로드 URL(_extract_jsonld_download_urls)로
       마스터 CSV(약 128MB)를 스트리밍 다운로드
    5. "목록유형" 열로 행을 분류하여
         API  -> metadata_api.csv
         FILE -> metadata_file.csv
         STD  -> metadata_std.csv
       로 각각 저장 (헤더 유지)
    6. date.json 갱신

메모:
    - 페이지 파싱은 기존 FileDataCrawler 로직을 그대로 재사용합니다.
    - 대용량(수백 MB) 다운로드를 위해 전용 세션(넉넉한 타임아웃)을 사용합니다.
==============================================================================
"""

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, TextIO

import aiohttp

from crawler.file_data_crawler import FileDataCrawler
from domain.schemas import CrawlerConfig

# "공공데이터활용지원센터_공공데이터포털 목록관리현황" — 전체 개방 목록(API/파일/표준) 마스터 CSV
CATALOG_ID = "15062804"
CATALOG_URL = f"https://www.data.go.kr/data/{CATALOG_ID}/fileData.do"

# 상세 표에서 신규 여부 판단에 쓰는 날짜 키 (우선순위 순)
DATE_FIELDS = ("수정일", "등록일")

# 마스터 CSV의 "목록유형" 열 값 -> 저장 대상 파일 매핑
TYPE_COLUMN = "목록유형"
TYPE_TARGET_MAP = {
    "API": "metadata_api.csv",
    "FILE": "metadata_file.csv",
    "STD": "metadata_std.csv",
}
DEFAULT_TARGETS = tuple(TYPE_TARGET_MAP.values())

# 마스터 CSV 읽기 시 시도할 인코딩 (utf-8-sig 우선 — 포털 CSV 실제 인코딩)
CSV_ENCODINGS = ("utf-8-sig", "cp949", "euc-kr", "utf-8")
# 분류 저장 시 출력 인코딩 (MetadataCsvReader 가 utf-8-sig 를 인식)
OUTPUT_ENCODING = "utf-8-sig"

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class MetadataUpdater:
    """15062804 목록 CSV의 신규 여부를 확인하고 필요 시 다운로드/분류 저장한다."""

    def __init__(self, csv_dir: str, catalog_url: str = CATALOG_URL):
        self.csv_dir = Path(csv_dir)
        self.catalog_url = catalog_url
        self.date_path = self.csv_dir / "date.json"
        self.type_map = dict(TYPE_TARGET_MAP)
        self.targets = list(TYPE_TARGET_MAP.values())
        # 파싱 헬퍼(_extract_table_bs 등)만 빌려 쓰기 위한 인스턴스. 네트워크는 자체 세션 사용.
        self._parser = FileDataCrawler(
            CrawlerConfig(start_num=0, end_num=0, output_dir=str(self.csv_dir), max_workers=4)
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _parse_date(text: Optional[str]):
        if not text:
            return None
        try:
            return datetime.strptime(str(text)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    def _load_stored_date_raw(self) -> Optional[str]:
        try:
            with self.date_path.open("r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        for key in DATE_FIELDS:
            if data.get(key):
                return data[key]
        return None

    def _targets_exist(self) -> bool:
        return all((self.csv_dir / name).exists() for name in self.targets)

    def _save_state(self, info: Dict[str, str], page_date_raw: Optional[str],
                    atch_url: str, byte_count: int, counts: Dict[str, int]) -> None:
        payload = {
            "등록일": info.get("등록일") or page_date_raw or "",
            "수정일": info.get("수정일") or page_date_raw or "",
            "catalog_id": CATALOG_ID,
            "source_url": self.catalog_url,
            "download_url": atch_url,
            "bytes": byte_count,
            "row_counts": counts,
            "downloaded_at": datetime.now().isoformat(timespec="seconds"),
        }
        with self.date_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _session() -> aiohttp.ClientSession:
        """대용량 다운로드용 세션. total 타임아웃 없음, 정체 시 sock_read 로 중단."""
        timeout = aiohttp.ClientTimeout(total=None, connect=15, sock_connect=15, sock_read=120)
        connector = aiohttp.TCPConnector(limit=8, ttl_dns_cache=300, enable_cleanup_closed=True)
        return aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers={"User-Agent": _USER_AGENT}
        )

    # -------------------------------------------------------------- csv 분류
    @staticmethod
    def _detect_encoding(path: Path) -> str:
        """헤더에 '목록유형' 이 보이는 인코딩을 선택. 없으면 첫 성공 인코딩."""
        first_ok = None
        for enc in CSV_ENCODINGS:
            try:
                with path.open("r", encoding=enc, newline="") as f:
                    header = f.readline()
            except (UnicodeDecodeError, OSError):
                continue
            if first_ok is None:
                first_ok = enc
            if TYPE_COLUMN in header:
                return enc
        return first_ok or CSV_ENCODINGS[0]

    def _split_by_type(self, source: Path) -> Dict[str, int]:
        """마스터 CSV를 '목록유형' 열로 분류하여 대상 파일들로 저장. 유형별 행 수 반환."""
        encoding = self._detect_encoding(source)
        counts: Dict[str, int] = {key: 0 for key in self.type_map}
        counts["_unknown"] = 0

        with source.open("r", encoding=encoding, newline="") as src:
            reader = csv.reader(src)
            try:
                header = next(reader)
            except StopIteration:
                return counts

            # BOM 잔재 제거 후 '목록유형' 열 위치 탐색 (정확 일치 우선, 없으면 '유형' 포함)
            clean_header = [cell.lstrip("﻿").strip() for cell in header]
            type_idx = next((i for i, h in enumerate(clean_header) if h == TYPE_COLUMN), None)
            if type_idx is None:
                type_idx = next((i for i, h in enumerate(clean_header) if "유형" in h), None)
            if type_idx is None:
                raise ValueError(f"'{TYPE_COLUMN}' column not found in master CSV header")

            # 대상별 writer 준비 (헤더 먼저 기록)
            files: Dict[str, TextIO] = {}
            writers: Dict[str, "csv._writer"] = {}
            try:
                for key, name in self.type_map.items():
                    fh = (self.csv_dir / name).open("w", encoding=OUTPUT_ENCODING, newline="")
                    files[key] = fh
                    writers[key] = csv.writer(fh)
                    writers[key].writerow(header)

                for row in reader:
                    value = row[type_idx].strip().upper() if type_idx < len(row) else ""
                    if value in writers:
                        writers[value].writerow(row)
                        counts[value] += 1
                    else:
                        counts["_unknown"] += 1
            finally:
                for fh in files.values():
                    fh.close()

        return counts

    # -------------------------------------------------------------------- main
    async def check_and_update(self, force: bool = False) -> Dict:
        """신규면 다운로드/분류 저장, 아니면 그대로 둔다. 결과 dict를 반환."""
        async with self._session() as session:
            # 1) 상세 페이지에서 등록일/수정일과 다운로드 URL 추출 (기존 파싱 로직 재사용)
            async with session.get(self.catalog_url) as resp:
                if resp.status != 200:
                    return {"updated": False, "reason": f"page-http-{resp.status}"}
                html = await resp.text()

            soup = self._parser.make_soup(html, ["table", "input"])
            info = self._parser._extract_table_bs(soup)
            page_date_raw = next((info[k] for k in DATE_FIELDS if info.get(k)), None)

            page_date = self._parse_date(page_date_raw)
            stored_raw = self._load_stored_date_raw()
            stored_date = self._parse_date(stored_raw)

            targets_missing = not self._targets_exist()
            is_newer = bool(page_date) and (stored_date is None or page_date > stored_date)

            if not force and not targets_missing and not is_newer:
                return {
                    "updated": False,
                    "reason": "up-to-date",
                    "page_date": page_date_raw,
                    "stored_date": stored_raw,
                }

            reason = "forced" if force else ("targets-missing" if targets_missing else "newer")

            # 2) 다운로드 URL 확보
            file_name = info.get("파일데이터명") or info.get("목록명") or CATALOG_ID
            download_urls = self._parser._extract_jsonld_download_urls(html, file_name)
            if not download_urls:
                return {
                    "updated": False,
                    "reason": "no-download-url",
                    "page_date": page_date_raw,
                    "stored_date": stored_raw,
                }
            download_url = next(iter(download_urls.values()))

            # 3) 임시 파일로 스트리밍 다운로드 (약 128MB)
            self.csv_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self.csv_dir / ".metadata_download.tmp"
            byte_count = 0
            try:
                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        return {"updated": False, "reason": f"download-http-{resp.status}"}
                    with tmp_path.open("wb") as f:
                        async for chunk in resp.content.iter_chunked(1 << 20):
                            f.write(chunk)
                            byte_count += len(chunk)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

        # 4) '목록유형' 열로 분류하여 대상 CSV들로 저장
        try:
            counts = self._split_by_type(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        # 5) 상태 기록
        self._save_state(info, page_date_raw, download_url, byte_count, counts)

        return {
            "updated": True,
            "reason": reason,
            "page_date": page_date_raw,
            "stored_date": stored_raw,
            "bytes": byte_count,
            "download_url": download_url,
            "counts": counts,
        }


async def maybe_update_metadata(csv_dir: str, force: bool = False) -> Dict:
    """크롤 시작 전 자동 호출용 래퍼. 네트워크 실패는 경고만 하고 크롤을 계속 진행한다."""
    print("\n" + "=" * 80)
    print(f"Metadata list check: {CATALOG_URL}")
    print("=" * 80)
    updater = MetadataUpdater(csv_dir)
    try:
        result = await updater.check_and_update(force=force)
    except Exception as exc:  # 오프라인 등 — 기존 CSV가 있으면 그대로 크롤 진행
        print(f"Metadata update skipped (error): {exc}")
        return {"updated": False, "reason": "error", "error": str(exc)}

    if result.get("updated"):
        mb = result.get("bytes", 0) / (1024 * 1024)
        counts = result.get("counts", {})
        print(f"Updated ({result['reason']}): stored {result.get('stored_date')} -> "
              f"page {result.get('page_date')}")
        print(f"Downloaded {mb:.1f} MB, split by '{TYPE_COLUMN}':")
        for key, name in TYPE_TARGET_MAP.items():
            print(f"  {key:4s} -> {name}: {counts.get(key, 0):,} rows")
        if counts.get("_unknown"):
            print(f"  (unclassified rows skipped: {counts['_unknown']:,})")
    else:
        print(f"No update ({result.get('reason')}): "
              f"stored={result.get('stored_date')}, page={result.get('page_date')}")
    print("=" * 80 + "\n")
    return result


def run_metadata_update(csv_dir: str, force: bool = False) -> Dict:
    """동기 진입점(단독 실행/테스트용)."""
    return asyncio.run(MetadataUpdater(csv_dir).check_and_update(force=force))
