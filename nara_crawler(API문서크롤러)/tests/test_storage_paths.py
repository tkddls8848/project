import json
import os

from managers.crawl_run_manager import CrawlRunManager
from managers.file_storage import DataExporter


def test_storage_root_is_sibling_nara_storage(tmp_path):
    manager = CrawlRunManager(tmp_path / "nara_crawler")
    assert manager.storage_dir == tmp_path / "nara_storage"
    assert manager.manifests_dir == tmp_path / "nara_storage" / "manifests"


def test_raw_output_dir_is_flat_type_dir(tmp_path):
    manager = CrawlRunManager(tmp_path / "nara_crawler")
    # run_id 계층 없이 데이터타입 폴더 직행
    assert manager.get_raw_output_dir("fileData") == tmp_path / "nara_storage" / "fileData"
    assert manager.get_raw_output_dir("standard") == tmp_path / "nara_storage" / "standard"


def test_save_manifest_goes_to_manifests_dir(tmp_path):
    manager = CrawlRunManager(tmp_path / "nara_crawler")
    run_id = "2026-07-17T10-00-00"
    path = manager.save_manifest(run_id, {"crawl_run_id": run_id, "runs": []})
    assert path == tmp_path / "nara_storage" / "manifests" / f"{run_id}.json"
    assert json.loads(path.read_text(encoding="utf-8"))["crawl_run_id"] == run_id


def test_openapi_recrawl_overwrites_single_file(tmp_path):
    storage = tmp_path / "nara_storage"
    data = {
        "api_id": "15000001",
        "api_type": "openapi_new",
        "info": {"제공기관": "한국환경공단", "수정일": "2026-01-01"},
    }
    saved, errors = DataExporter.save_crawling_result(data, str(storage), "15000001")
    assert errors == []
    assert saved == [os.path.join(str(storage), "openapi_new", "15000001.json")]

    # 수정일이 달라져도 같은 파일을 덮어쓴다 (파일 1개 유지)
    data_recrawled = {**data, "info": {"제공기관": "한국환경공단", "수정일": "2026-02-02"}}
    saved2, errors2 = DataExporter.save_crawling_result(data_recrawled, str(storage), "15000001")
    assert errors2 == []
    assert saved2 == saved
    files = list((storage / "openapi_new").glob("*.json"))
    assert len(files) == 1
    stored = json.loads(files[0].read_text(encoding="utf-8"))
    assert stored["info"]["수정일"] == "2026-02-02"


def test_non_openapi_saves_flat_in_given_dir(tmp_path):
    # 비 openapi 타입은 main이 이미 {storage}/{data_type}을 output_dir로 넘긴다
    type_dir = tmp_path / "nara_storage" / "fileData"
    data = {"api_id": "20000001", "api_type": "fileData", "info": {}}
    saved, errors = DataExporter.save_crawling_result(data, str(type_dir), "20000001")
    assert errors == []
    assert saved == [os.path.join(str(type_dir), "20000001.json")]
