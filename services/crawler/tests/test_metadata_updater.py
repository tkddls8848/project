"""목록 CSV 자동 갱신기가 기존 크롤러 입력을 망가뜨리지 않는지 확인한다.

이 갱신기는 일반 크롤 시작 전에 자동으로 돈다. 여기서 대상 CSV가 조용히 비면
크롤러는 아무 대상도 없이 "성공"으로 끝나고, 다음 실행은 date.json을 보고
최신이라고 판단해 같은 상태를 유지한다.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from utils.metadata_updater import OUTPUT_ENCODING, TYPE_TARGET_MAP, MetadataUpdater

HEADER = ["목록번호", "목록명", "목록유형"]
PREVIOUS = "이전 회차가 남긴 정상 CSV\n"


def _master_csv(csv_dir: Path, rows: list[list[str]]) -> Path:
    path = csv_dir / "master.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def _seed_previous_targets(csv_dir: Path) -> None:
    for name in TYPE_TARGET_MAP.values():
        (csv_dir / name).write_text(PREVIOUS, encoding=OUTPUT_ENCODING)


def _assert_previous_targets_intact(csv_dir: Path) -> None:
    for name in TYPE_TARGET_MAP.values():
        assert (csv_dir / name).read_text(encoding=OUTPUT_ENCODING) == PREVIOUS


def _assert_no_staging_left(csv_dir: Path) -> None:
    assert list(csv_dir.glob("*.tmp")) == []


def test_split_replaces_every_target_and_cleans_up(tmp_path):
    _seed_previous_targets(tmp_path)
    source = _master_csv(
        tmp_path,
        [
            ["1", "가", "API"],
            ["2", "나", "FILE"],
            ["3", "다", "STD"],
            ["4", "라", "API"],
            ["5", "마", "기타"],
        ],
    )

    counts = MetadataUpdater(str(tmp_path))._split_by_type(source)

    assert counts == {"API": 2, "FILE": 1, "STD": 1, "_unknown": 1}
    api_rows = (tmp_path / "metadata_api.csv").read_text(encoding=OUTPUT_ENCODING).splitlines()
    assert api_rows[0].lstrip("﻿").split(",") == HEADER
    assert len(api_rows) == 3
    _assert_no_staging_left(tmp_path)


def test_unclassifiable_master_keeps_the_previous_csvs(tmp_path):
    """포털이 '목록유형' 값을 바꾸면 갱신을 포기하고 기존 CSV를 남긴다.

    헤더만 남은 CSV로 교체하면 이후 크롤이 조용히 빈 대상으로 돈다.
    """
    _seed_previous_targets(tmp_path)
    source = _master_csv(tmp_path, [["1", "가", "OPENAPI"], ["2", "나", "DOWNLOAD"]])

    with pytest.raises(ValueError, match="분류 결과가 비어"):
        MetadataUpdater(str(tmp_path))._split_by_type(source)

    _assert_previous_targets_intact(tmp_path)
    _assert_no_staging_left(tmp_path)


def test_partially_classified_master_keeps_the_previous_csvs(tmp_path):
    """세 유형 중 하나라도 비면 교체하지 않는다."""
    _seed_previous_targets(tmp_path)
    source = _master_csv(tmp_path, [["1", "가", "API"], ["2", "나", "FILE"]])

    with pytest.raises(ValueError, match="metadata_std.csv"):
        MetadataUpdater(str(tmp_path))._split_by_type(source)

    _assert_previous_targets_intact(tmp_path)
    _assert_no_staging_left(tmp_path)


def test_missing_type_column_keeps_the_previous_csvs(tmp_path):
    _seed_previous_targets(tmp_path)
    path = tmp_path / "master.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["목록번호", "목록명"])
        writer.writerow(["1", "가"])

    with pytest.raises(ValueError, match="column not found"):
        MetadataUpdater(str(tmp_path))._split_by_type(path)

    _assert_previous_targets_intact(tmp_path)
    _assert_no_staging_left(tmp_path)


def test_empty_master_keeps_the_previous_csvs(tmp_path):
    """0바이트 다운로드를 성공으로 처리하면 대상 CSV가 통째로 사라진다."""
    _seed_previous_targets(tmp_path)
    path = tmp_path / "master.csv"
    path.write_text("", encoding="utf-8-sig")

    with pytest.raises(ValueError, match="empty"):
        MetadataUpdater(str(tmp_path))._split_by_type(path)

    _assert_previous_targets_intact(tmp_path)
    _assert_no_staging_left(tmp_path)


def test_write_failure_midway_keeps_the_previous_csvs(tmp_path, monkeypatch):
    """분류 도중 끊겨도 기존 CSV는 그대로 남는다.

    호출부는 갱신 실패를 "기존 CSV로 계속 진행"으로 처리한다. 대상을 바로 열어
    쓰면 그 보고가 거짓이 된다.
    """
    _seed_previous_targets(tmp_path)
    source = _master_csv(
        tmp_path, [["1", "가", "API"], ["2", "나", "FILE"], ["3", "다", "STD"]]
    )
    updater = MetadataUpdater(str(tmp_path))

    def _boom(_counts):
        raise OSError("디스크 공간이 없습니다")

    monkeypatch.setattr(updater, "_verify_counts", _boom)

    with pytest.raises(OSError):
        updater._split_by_type(source)

    _assert_previous_targets_intact(tmp_path)
    _assert_no_staging_left(tmp_path)
