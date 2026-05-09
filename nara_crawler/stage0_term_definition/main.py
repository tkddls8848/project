import argparse
import asyncio
import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
CURRENT_DIR = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))

DEFAULT_DATA_DIR = CURRENT_DIR / "data"
DEFAULT_OUTPUT_CSV = DEFAULT_DATA_DIR / "definition_fileData.csv"

METADATA_HEADERS = [
    "목록키",
    "목록유형",
    "목록명",
    "파일데이터명",
    "분류체계",
    "제공기관코드",
    "제공기관",
    "관리 부서명",
    "관리부서 전화번호",
    "보유근거",
    "수집방법",
    "업데이트 주기",
    "차기 등록 예정일",
    "매체유형",
    "전체행",
    "확장자(데이터포맷)",
    "키워드",
    "다운로드_활용신청건수",
    "등록일",
    "수정일",
    "데이터 한계",
    "제공형태",
    "설명",
    "기타 유의사항",
    "공간범위",
    "시간범위",
    "비용부과유무",
    "비용부과기준 및 단위",
    "이용허락범위",
    "API 유형",
    "신청가능 트래픽",
    "심의 유형",
    "조회수",
    "목록 URL",
    "국가중점여부",
    "표준데이터여부",
]

TERM_FILEDATA_RESOURCES = [
    {"data_id": "15062804", "item_no": "2", "title": "목록개방현황", "note": "분류체계, 키워드 포함", "source_link": "https://www.data.go.kr/data/15062804/fileData.do"},
    {"data_id": "15121937", "item_no": "2-보강", "title": "목록 메타정보", "note": "요청변수, 출력결과 포함", "source_link": "https://www.data.go.kr/data/15121937/fileData.do"},
    {"data_id": "15156379", "item_no": "3a", "title": "공통표준용어", "note": "표준 용어 기준", "source_link": "https://www.data.go.kr/data/15156379/fileData.do"},
    {"data_id": "15156439", "item_no": "3b", "title": "공통표준단어", "note": "표준 단어 기준", "source_link": "https://www.data.go.kr/data/15156439/fileData.do"},
    {"data_id": "15092039", "item_no": "4", "title": "행정표준코드 전체", "note": "240종 코드", "source_link": "https://www.data.go.kr/data/15092039/fileData.do"},
]

@dataclass
class CrawlResult:
    url: str
    success: bool
    data: Optional[dict] = None
    errors: list[str] = field(default_factory=list)
    crawled_at: str = field(default_factory=lambda: now_iso())


def now_iso() -> str:
    return datetime.now(KST).isoformat()

def clean_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_metadata_row(item: dict) -> dict:
    row = {header: "" for header in METADATA_HEADERS}
    row.update(
        {
            "목록키": item["data_id"],
            "목록유형": "FILE",
            "목록명": item["title"],
            "파일데이터명": item["title"],
            "분류체계": "공공행정 - 데이터표준",
            "키워드": "표준,분류,공통표준,행정표준코드",
            "제공형태": "파일",
            "설명": item["note"],
            "목록 URL": filedata_url(item["data_id"]),
            "국가중점여부": "N",
            "표준데이터여부": "N",
        }
    )
    return row


def write_metadata_csv(output_csv: Path) -> tuple[list[int], dict[int, dict]]:
    items = TERM_FILEDATA_RESOURCES
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    csv_data: dict[int, dict] = {}
    with output_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=METADATA_HEADERS)
        writer.writeheader()
        for item in items:
            row = build_metadata_row(item)
            writer.writerow(row)
            csv_data[int(item["data_id"])] = row

    return [int(item["data_id"]) for item in items], csv_data


def filedata_url(data_id: str | int) -> str:
    return f"https://www.data.go.kr/data/{data_id}/fileData.do"


def extract_api_id(url: str) -> str:
    match = re.search(r"/data/(\d+)/", url)
    return match.group(1) if match else ""


def safe_filename_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\r\n\t]', "_", value or "")
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    return cleaned or "unknown"


def filename_from_content_disposition(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"filename\*=UTF-8''([^;]+)", value, re.IGNORECASE)
    if match:
        try:
            from urllib.parse import unquote

            return unquote(match.group(1)).strip('"')
        except Exception:
            return match.group(1).strip('"')
    match = re.search(r'filename="?([^";]+)"?', value, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def summarize_downloads(results: list[CrawlResult], output_dir: Path) -> dict:
    downloaded_files = [
        Path(path)
        for result in results
        if result.data
        for path in result.data.get("saved_files", [])
    ]
    return {
        "generated_at": now_iso(),
        "data_role": "metadata_standard_for_data_refinement",
        "output_dir": str(output_dir),
        "total_targets": len(results),
        "downloaded_files": len(downloaded_files),
        "failed_targets": sum(1 for result in results if result.errors),
        "files": [
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
            for path in downloaded_files
        ],
        "failures": [
            {
                "url": result.url,
                "errors": result.errors,
            }
            for result in results
            if result.errors
        ],
    }


class TermDefinitionCrawler:
    DOWNLOAD_INFO_URL = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"

    def __init__(self, output_dir: Path, max_workers: int):
        self.output_dir = output_dir
        self.max_workers = max(1, max_workers)
        self.semaphore = asyncio.Semaphore(self.max_workers)
        self.file_info_semaphore = asyncio.Semaphore(self.max_workers)

    async def crawl(self, numbers: list[int], csv_data: dict[int, dict]) -> list[CrawlResult]:
        import aiohttp

        urls = [filedata_url(number) for number in numbers]
        timeout = aiohttp.ClientTimeout(total=20, connect=5, sock_read=15)
        connector = aiohttp.TCPConnector(
            limit=max(20, self.max_workers * 2),
            limit_per_host=max(5, self.max_workers),
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
            tasks = [self._crawl_one(session, url, csv_data.get(int(extract_api_id(url)), {})) for url in urls]
            return await asyncio.gather(*tasks)

    async def _crawl_one(self, session: Any, url: str, csv_row: dict) -> CrawlResult:
        from bs4 import BeautifulSoup

        async with self.semaphore:
            api_id = extract_api_id(url)
            if not api_id:
                return CrawlResult(url=url, success=False, errors=["Could not extract data ID"])

            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        return CrawlResult(url=url, success=False, errors=[f"HTTP {response.status}"])
                    html = await response.text()
            except Exception as exc:
                return CrawlResult(url=url, success=False, errors=[f"HTML metadata fetch failed: {exc}"])

            soup = BeautifulSoup(html, "html.parser")
            html_info = self._extract_detail_tables(soup)
            operation_ids = self._extract_public_data_detail_pks(soup)
            if not operation_ids:
                operation_ids = await self._extract_operation_ids(session, api_id)

            download_urls = await self._extract_download_urls(session, api_id, operation_ids)
            saved_files = await self._download_files(session, api_id, download_urls)

            data = {
                "api_id": api_id,
                "api_type": "term_definition_fileData",
                "crawled_url": url,
                "crawled_time": now_iso(),
                "title": html_info.get("파일데이터명") or html_info.get("목록명") or csv_row.get("목록명", ""),
                "operation_ids": operation_ids,
                "download_urls": download_urls,
                "saved_files": [str(path) for path in saved_files],
            }

            success = bool(saved_files)
            if not success:
                return CrawlResult(url=url, success=False, data=data, errors=["No CSV files downloaded"])
            return CrawlResult(url=url, success=True, data=data)

    def _extract_detail_tables(self, soup: Any) -> dict:
        info = {}
        selectors = [
            "table.fileDataDetail",
            "table.dataset-table",
            "table",
        ]
        for selector in selectors:
            for table in soup.select(selector):
                for row in table.find_all("tr"):
                    th = row.find("th")
                    td = row.find("td")
                    if not th or not td:
                        continue
                    key = clean_text(th.get_text())
                    if not key:
                        continue
                    for script in td.find_all("script"):
                        script.decompose()
                    value = clean_text(td.get_text())
                    if value:
                        info[key] = value
                if info:
                    return info
        return info

    def _extract_public_data_detail_pks(self, soup: Any) -> list[str]:
        ids = []
        for input_tag in soup.select("input#publicDataDetailPk"):
            value = input_tag.get("value", "").strip()
            if value and value not in ids:
                ids.append(value)
        return ids

    async def _extract_operation_ids(self, session: Any, data_id: str) -> list[str]:
        url = f"https://infuser.odcloud.kr/oas/docs?namespace={data_id}/v1"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return []
                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    return []
                payload = await response.json()
        except Exception:
            return []

        ids = []
        paths = payload.get("paths", {})
        if isinstance(paths, dict):
            for path_value in paths.values():
                if not isinstance(path_value, dict):
                    continue
                for method_details in path_value.values():
                    if isinstance(method_details, dict) and method_details.get("operationId"):
                        op_id = re.sub(r"get", "", str(method_details["operationId"]), flags=re.IGNORECASE)
                        if op_id and op_id not in ids:
                            ids.append(op_id)
        return ids

    async def _extract_download_urls(
        self,
        session: Any,
        data_id: str,
        operation_ids: list[str],
    ) -> dict[str, str]:
        download_urls = {}
        for operation_id in operation_ids:
            info = await self._extract_file_info(session, data_id, operation_id)
            for data_name, attach_id in info.items():
                download_urls[data_name] = (
                    f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={attach_id}&fileDetailSn=1"
                )
        return download_urls

    async def _download_files(self, session: Any, data_id: str, download_urls: dict[str, str]) -> list[Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = []
        for data_name, url in download_urls.items():
            saved_path = await self._download_one_file(session, data_id, data_name, url)
            if saved_path:
                saved_files.append(saved_path)
        return saved_files

    async def _download_one_file(self, session: Any, data_id: str, data_name: str, url: str) -> Optional[Path]:
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                content = await response.read()
                disposition = response.headers.get("Content-Disposition", "")
        except Exception:
            return None

        filename = filename_from_content_disposition(disposition)
        if not filename:
            filename = f"{data_id}_{safe_filename_part(data_name)}.csv"
        if not filename.lower().endswith(".csv"):
            filename = f"{Path(filename).stem}.csv"

        file_path = self.output_dir / safe_filename_part(filename)
        with file_path.open("wb") as f:
            f.write(content)
        return file_path

    async def _extract_file_info(self, session: Any, data_id: str, operation_id: str) -> dict[str, str]:
        params = {
            "publicDataPk": data_id,
            "publicDataDetailPk": operation_id,
        }
        async with self.file_info_semaphore:
            try:
                async with session.get(self.DOWNLOAD_INFO_URL, params=params) as response:
                    if response.status != 200:
                        return {}
                    text = await response.text()
            except Exception:
                return {}

        payload = self._parse_json_or_html_body(text)
        file_info: dict[str, str] = {}
        self._find_file_info_recursive(payload, file_info)
        return file_info

    def _parse_json_or_html_body(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"<body[^>]*>(.*?)</body>", text, re.DOTALL | re.IGNORECASE)
            if not match:
                return {}
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                return {}

    def _find_file_info_recursive(self, obj: Any, file_info: dict[str, str]) -> None:
        if isinstance(obj, dict):
            if obj.get("dataNm") and obj.get("atchFileId"):
                name = str(obj["dataNm"]).strip()
                attach_id = str(obj["atchFileId"]).strip()
                if name and attach_id:
                    file_info[name] = attach_id
                return
            for value in obj.values():
                self._find_file_info_recursive(value, file_info)
        elif isinstance(obj, list):
            for item in obj:
                self._find_file_info_recursive(item, file_info)

async def crawl_term_definition_filedata(
    output_csv: Path,
    workers: int,
    dry_run: bool,
) -> None:
    numbers, csv_data = write_metadata_csv(output_csv)
    print(f"Metadata CSV saved: {output_csv}")
    print(f"Targets: {', '.join(str(number) for number in numbers)}")

    if dry_run:
        print("Dry run complete. Crawling was not executed.")
        return

    if not numbers:
        print("No fileData targets found.")
        return

    run_dir = DEFAULT_DATA_DIR
    output_dir = run_dir
    crawler = TermDefinitionCrawler(output_dir=output_dir, max_workers=workers)
    results = await crawler.crawl(numbers, csv_data)
    saved_files = [
        path
        for result in results
        if result.data
        for path in result.data.get("saved_files", [])
    ]
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "term_definition_fileData_summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summarize_downloads(results, output_dir), f, ensure_ascii=False, indent=2)

    print("Term/definition fileData crawling complete.")
    print(f"  output: {output_dir}")
    print(f"  summary: {summary_path}")
    print(f"  csv_files: {len(saved_files)}")
    for result in results:
        if result.errors:
            print(f"  failed: {result.url} - {', '.join(result.errors)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl fileData resources for crawler-wide term and definition metadata standards"
    )
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV), help="Generated metadata CSV path")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers")
    parser.add_argument("--dry-run", action="store_true", help="Only generate the metadata CSV")
    args = parser.parse_args()

    asyncio.run(
        crawl_term_definition_filedata(
            output_csv=Path(args.output_csv),
            workers=args.workers,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
