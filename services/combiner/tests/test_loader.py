"""loader.py 단위 테스트."""
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clear_cache():
    from app.loader import reset_cache
    reset_cache()
    yield
    reset_cache()


def test_load_all_from_fixtures():
    from app.loader import load_all
    catalog = load_all(data_dir=FIXTURES)
    assert len(catalog) == 3
    assert "15000827" in catalog
    assert "15000863" in catalog
    assert "15000881" in catalog


def test_parse_fields():
    from app.loader import load_all
    catalog = load_all(data_dir=FIXTURES)
    svc = catalog["15000827"]
    assert svc["name"] == "외교부_여행경보제도"
    assert svc["agency"] == "외교부"
    assert "해외안전정보" in svc["keywords"]


def test_get_services_found():
    from app.loader import load_all, get_services
    load_all(data_dir=FIXTURES)
    found, missing = get_services(["15000827", "15000863"])
    assert len(found) == 2
    assert missing == []


def test_get_services_missing():
    from app.loader import load_all, get_services
    load_all(data_dir=FIXTURES)
    found, missing = get_services(["15000827", "99999999"])
    assert len(found) == 1
    assert "99999999" in missing


def test_get_services_all_missing():
    from app.loader import load_all, get_services
    load_all(data_dir=FIXTURES)
    found, missing = get_services(["00000001"])
    assert found == []
    assert "00000001" in missing


def test_load_empty_dir(tmp_path):
    from app.loader import load_all
    catalog = load_all(data_dir=tmp_path)
    assert catalog == {}


def test_load_missing_dir(tmp_path):
    from app.loader import load_all
    catalog = load_all(data_dir=tmp_path / "nonexistent")
    assert catalog == {}
