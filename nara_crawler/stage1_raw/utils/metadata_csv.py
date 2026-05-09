import csv
import re
from pathlib import Path
from typing import Callable, ClassVar, Dict, List, Optional, Tuple


class MetadataCsvReader:
    """Read Nara metadata CSV files with encoding and id-column fallback logic."""

    ENCODINGS = ("euc-kr", "cp949", "utf-8-sig", "utf-8")
    ID_COLUMN_MARKERS = (
        "\ubaa9\ub85d\ud0a4",
        "\ubb38\uc11c\ubc88\ud638",
        "\ud0a4",
        "key",
        "id",
    )
    _CACHE: ClassVar[Dict[str, Tuple[int, int, Tuple[Tuple[str, List[str], List[Dict]], ...]]]] = {}

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)

    def get_range(self) -> Tuple[Optional[int], Optional[int]]:
        for encoding, headers, rows in self._read_candidates():
            id_col = self._find_id_column(headers)
            all_nums = [
                doc_num
                for row in rows
                if (doc_num := self._extract_doc_num(row, id_col)) is not None
            ]
            if all_nums:
                return min(all_nums), max(all_nums)
        return None, None

    def get_numbers_in_range(
        self,
        start: int,
        end: int,
        row_filter: Optional[Callable[[Dict], bool]] = None,
    ) -> Tuple[List[int], Dict[int, Dict]]:
        for encoding, headers, rows in self._read_candidates():
            header_preview = [str(header).lstrip("\ufeff") for header in headers[:3]]
            print(f"Trying encoding {encoding}. Headers: {header_preview}...")

            id_col = self._find_id_column(headers)
            display_id_col = str(id_col).lstrip("\ufeff") if id_col is not None else None
            print(f"Using ID column: {display_id_col}")

            valid_numbers = []
            csv_data = {}
            for row in rows:
                doc_num = self._extract_doc_num(row, id_col)
                if doc_num is not None and start <= doc_num <= end:
                    if row_filter and not row_filter(row):
                        continue
                    valid_numbers.append(doc_num)
                    csv_data[doc_num] = self._clean_row(row)

            if valid_numbers:
                print(f"Successfully read CSV with encoding: {encoding}")
                return valid_numbers, csv_data

        return [], {}

    def _read_candidates(self):
        cache_key = str(self.csv_path.resolve())
        try:
            stat = self.csv_path.stat()
            cache_meta = (stat.st_mtime_ns, stat.st_size)
        except OSError:
            cache_meta = (0, 0)

        cached = self._CACHE.get(cache_key)
        if cached and cached[:2] == cache_meta:
            for candidate in cached[2]:
                yield candidate
            return

        candidates = []
        for encoding in self.ENCODINGS:
            try:
                with self.csv_path.open("r", encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames or []
                    if not headers:
                        continue
                    candidates.append((encoding, headers, list(reader)))
            except UnicodeDecodeError:
                continue
            except Exception as exc:
                print(f"Error reading CSV with {encoding}: {exc}")
                continue

        self._CACHE[cache_key] = (*cache_meta, tuple(candidates))
        for candidate in candidates:
            yield candidate

    def _find_id_column(self, headers: List[str]) -> Optional[str]:
        for header in headers:
            header_text = str(header).lstrip("\ufeff")
            header_lower = header_text.lower()
            for marker in self.ID_COLUMN_MARKERS:
                if marker in header_text or marker in header_lower:
                    return header
        return headers[0] if headers else None

    def _extract_doc_num(self, row: Dict, id_col: Optional[str]) -> Optional[int]:
        if id_col and row.get(id_col):
            try:
                return int(str(row[id_col]).strip())
            except (TypeError, ValueError):
                pass

        for value in row.values():
            value_text = str(value).strip() if value is not None else ""
            if value_text.isdigit() and len(value_text) > 5:
                return int(value_text)
        return None

    def _clean_row(self, row: Dict) -> Dict:
        cleaned_row = {}
        for key, value in row.items():
            if isinstance(value, str):
                value = re.sub(r"`\s*var\s+.*$", "", value, flags=re.DOTALL).strip()
                value = re.sub(r"`$", "", value).strip()
            cleaned_row[key] = value
        return cleaned_row
