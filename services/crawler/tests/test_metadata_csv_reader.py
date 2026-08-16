"""목록 CSV 읽기가 파일을 몇 벌이나 메모리에 올리는지 확인한다.

metadata_file.csv는 100MB대다. 인코딩 후보를 미리 전부 파싱하면 같은 파일이
여러 벌 상주하고, 클래스 캐시가 그 전부를 계속 들고 있는다.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from utils.metadata_csv import MetadataCsvReader


@pytest.fixture(autouse=True)
def _clear_reader_cache():
    MetadataCsvReader._CACHE.clear()
    yield
    MetadataCsvReader._CACHE.clear()


@pytest.fixture
def counted_opens(monkeypatch):
    """`Path.open` 호출을 세어 전체 파싱 횟수를 관찰한다."""
    calls: list[str] = []
    real_open = Path.open

    def counting_open(self, *args, **kwargs):
        calls.append(str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    return calls


def _csv_in(directory: Path, encoding: str) -> Path:
    path = directory / "metadata_api.csv"
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["목록키", "목록명"])
        writer.writerow(["15012345", "가나다"])
        writer.writerow(["15012346", "라마바"])
    return path


def test_only_the_first_usable_encoding_is_parsed(tmp_path, counted_opens):
    """첫 번째로 읽히는 인코딩에서 멈춘다. 나머지 후보는 열지도 않는다."""
    path = _csv_in(tmp_path, "euc-kr")
    counted_opens.clear()

    assert MetadataCsvReader(str(path)).get_range() == (15012345, 15012346)

    assert counted_opens == [str(path)]


def test_cached_read_does_not_reopen_the_file(tmp_path, counted_opens):
    reader = MetadataCsvReader(str(_csv_in(tmp_path, "euc-kr")))
    reader.get_range()
    counted_opens.clear()

    assert reader.get_range() == (15012345, 15012346)

    assert counted_opens == []


def test_cache_holds_a_single_parsed_copy(tmp_path):
    path = _csv_in(tmp_path, "euc-kr")
    MetadataCsvReader(str(path)).get_range()

    _mtime, _size, encoding, headers, rows = MetadataCsvReader._CACHE[str(path.resolve())]

    assert encoding == "euc-kr"
    assert headers[0].lstrip("﻿") == "목록키"
    assert len(rows) == 2


def test_utf8_bom_file_is_read(tmp_path):
    """갱신기의 출력 인코딩(utf-8-sig)으로 쓴 파일도 그대로 읽힌다."""
    path = _csv_in(tmp_path, "utf-8-sig")

    numbers, data = MetadataCsvReader(str(path)).get_numbers_in_range(15012345, 15012346)

    assert numbers == [15012345, 15012346]
    assert data[15012345]["목록명"] == "가나다"


def test_cache_is_invalidated_when_the_file_changes(tmp_path):
    path = _csv_in(tmp_path, "euc-kr")
    reader = MetadataCsvReader(str(path))
    assert reader.get_range() == (15012345, 15012346)

    with path.open("w", encoding="euc-kr", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["목록키", "목록명"])
        writer.writerow(["15099999", "사아자"])

    assert MetadataCsvReader(str(path)).get_range() == (15099999, 15099999)
