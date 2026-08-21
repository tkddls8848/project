import pytest

from backend.core.service_id import (
    ServiceIdError,
    normalize_service_id,
    split_service_id,
    to_canonical,
)


def test_canonical_id_passes_through():
    assert normalize_service_id("openapi_new:15000827") == "openapi_new:15000827"


def test_pure_numeric_api_id_is_normalized():
    assert normalize_service_id("15000827") == "openapi_new:15000827"


def test_whitespace_is_stripped():
    assert normalize_service_id("  openapi_new:15000827  ") == "openapi_new:15000827"


def test_unsupported_source_prefix():
    with pytest.raises(ServiceIdError) as exc_info:
        normalize_service_id("filedata:15000827")
    assert exc_info.value.error_code == "UNSUPPORTED_SOURCE"


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "abc", ":15000827", "openapi_new:", "openapi new:123", "openapi_new:abc def"],
)
def test_invalid_format(raw):
    with pytest.raises(ServiceIdError) as exc_info:
        normalize_service_id(raw)
    assert exc_info.value.error_code == "INVALID_SERVICE_ID"


def test_to_canonical_and_split_roundtrip():
    canonical = to_canonical("15000827")
    assert canonical == "openapi_new:15000827"
    assert split_service_id(canonical) == ("openapi_new", "15000827")
