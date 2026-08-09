"""심화 단계가 profiling/portals API를 **실제 시그니처대로** 부르는지 검사한다.

`--deep`은 `fetch_download_urls(download_urls, full_download=...)`로 불리고 있었다.
그런 키워드는 없어서 크롤이 다 끝난 뒤 TypeError로 죽었고, 샘플링·전량 수신 양쪽
모두 한 번도 성공한 적이 없었다 (2026-08-09). 파일을 실제로 받는 단계라 유닛
테스트가 없었던 것이 원인이므로, 네트워크는 스텁으로 막고 **호출 계약만** 고정한다.
"""

import asyncio
import inspect
import json
from argparse import Namespace

import profiling
from managers.crawl_run_manager import CrawlRunManager

import main


def _storage_with_file_data(tmp_path):
    """`fileData` 문서 하나를 가진 저장소와 그 run manager."""
    (tmp_path / ".nara-root").write_text("", encoding="utf-8")
    module_dir = tmp_path / "services" / "crawler"
    module_dir.mkdir(parents=True)
    manager = CrawlRunManager(module_dir)
    file_data = manager.storage_dir / "fileData"
    file_data.mkdir(parents=True)
    (file_data / "15000001.json").write_text(
        json.dumps({"download_urls": {"본문.csv": "https://example.invalid/a.csv"}}),
        encoding="utf-8",
    )
    return manager


def _args(**overrides):
    base = dict(deep=False, full_download=False, harvest=False, harvest_max_hosts=4)
    base.update(overrides)
    return Namespace(**base)


def _run_deep(tmp_path, monkeypatch, *, full_download):
    manager = _storage_with_file_data(tmp_path)
    recorded = {}

    async def fake_fetch(download_urls, **kwargs):
        recorded["download_urls"] = download_urls
        recorded["kwargs"] = kwargs
        return {}

    monkeypatch.setattr(profiling, "fetch_download_urls", fake_fetch)
    monkeypatch.setattr(profiling, "infer_fetched_files", lambda fetched: {})
    asyncio.run(
        main.run_depth_stages(
            _args(deep=True, full_download=full_download), manager, "run-1"
        )
    )
    return manager, recorded


def test_deep_calls_the_fetcher_the_way_the_fetcher_declares(tmp_path, monkeypatch):
    _, recorded = _run_deep(tmp_path, monkeypatch, full_download=False)

    assert recorded["download_urls"] == {"본문.csv": "https://example.invalid/a.csv"}
    # 예전에 TypeError를 낸 지점: 실제 함수가 이 인자들을 받아야 한다.
    inspect.signature(profiling.fetcher.fetch_download_urls).bind(
        recorded["download_urls"], **recorded["kwargs"]
    )


def test_sampling_asks_for_no_output_dir(tmp_path, monkeypatch):
    manager, recorded = _run_deep(tmp_path, monkeypatch, full_download=False)

    assert recorded["kwargs"]["policy"].full_download is False
    # 샘플은 메모리에만 남는다 — 디렉터리를 만들 이유가 없다.
    assert recorded["kwargs"]["output_dir"] is None
    assert not (manager.storage_dir / "files").exists()


def test_full_download_supplies_the_directory_the_fetcher_requires(tmp_path, monkeypatch):
    manager, recorded = _run_deep(tmp_path, monkeypatch, full_download=True)

    # full_download=True인데 output_dir이 없으면 fetcher가 ValueError를 낸다.
    assert recorded["kwargs"]["policy"].full_download is True
    assert recorded["kwargs"]["output_dir"] == manager.storage_dir / "files" / "run-1"


def test_reports_are_produced_and_keyed_by_file(tmp_path, monkeypatch):
    """네트워크만 막고 스키마·품질·주소 단계를 실제 함수로 통과시킨다.

    호출 계약이 어긋나 있어도 스텁으로 다 가리면 드러나지 않는다. 여기서는 진짜
    구현이 돌기 때문에 `generate_quality_report(schema)`처럼 인자가 모자란 호출은
    바로 실패한다.
    """
    manager = _storage_with_file_data(tmp_path)
    sample = "id,주소,값\n1,서울특별시 중구 세종대로 110,10\n2,부산광역시 중구 중앙대로 11,20\n"

    async def fake_fetch(download_urls, **_kwargs):
        return {
            name: profiling.FetchResult(
                name=name,
                url=url,
                status="ok",
                sample=sample.encode("utf-8"),
                filename="a.csv",
                content_type="text/csv",
            )
            for name, url in download_urls.items()
        }

    monkeypatch.setattr(profiling, "fetch_download_urls", fake_fetch)
    outputs = asyncio.run(main.run_depth_stages(_args(deep=True), manager, "run-1"))

    assert set(outputs) == {"file_schemas", "quality", "address_geo"}
    for key in ("file_schemas", "quality", "address_geo"):
        payload = json.loads(open(outputs[key], encoding="utf-8").read())
        assert list(payload) == ["본문.csv"], f"{key}가 파일명으로 색인되지 않았다"

    address = json.loads(open(outputs["address_geo"], encoding="utf-8").read())
    assert address["본문.csv"]["address_columns"], "주소 컬럼을 찾지 못했다"


def test_missing_file_data_skips_the_stage(tmp_path, monkeypatch):
    (tmp_path / ".nara-root").write_text("", encoding="utf-8")
    module_dir = tmp_path / "services" / "crawler"
    module_dir.mkdir(parents=True)
    manager = CrawlRunManager(module_dir)

    def explode(*_args, **_kwargs):
        raise AssertionError("fileData가 없으면 네트워크를 쓰면 안 된다")

    monkeypatch.setattr(profiling, "fetch_download_urls", explode)

    assert asyncio.run(main.run_depth_stages(_args(deep=True), manager, "run-1")) == {}
