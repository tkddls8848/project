# -*- coding: utf-8 -*-
"""
2026-08 data.go.kr 리뉴얼로 /catalog/{num}/{type}.json 응답이 schema.org Dataset
스키마로 바뀐 뒤의 메타데이터 스캐너 회귀 테스트.

아래 픽스처는 전부 라이브 실측 응답을 그대로 박아 넣은 것이다 (네트워크 접근 없음):
    openapi  → https://www.data.go.kr/catalog/15000017/openapi.json
    fileData → https://www.data.go.kr/catalog/15000249/fileData.json
    standard → https://www.data.go.kr/catalog/15072622/standard.json
"""

import json

import pytest

from scanner.base_scanner import is_metadata_document
from scanner.metadata_fileData import fileDataMetadataScanner
from scanner.metadata_openapi import OpenAPIMetadataScanner
from scanner.metadata_standard import standardMetadataScanner


# --------------------------------------------------------------------------
# 실측 픽스처
# --------------------------------------------------------------------------

RENEWED_OPENAPI = {
    "name": "한국문화관광연구원_관광실태조사서비스",
    "description": "관광실태 정보를 조회하기 위한 서비스로서 국내여행조사, 외래관광객조사, 관광사업체조사의 주요정보를 조회할 수 있다.",
    "url": "https://www.data.go.kr/data/15000017/openapi.do",
    "keywords": "조사통계,국민여행조사,외래관광객조사",
    "license": "제3자 권리 포함 : 저작권 표시, 공공저작물 : 출처표시 (제 1유형)",
    "dateCreated": "2012-12-06",
    "dateModified": "2022-09-30",
    "datePublished": "2012-12-06",
    "creator": {
        "name": "한국문화관광연구원",
        "contactPoint": {
            "contactType": "데이터전략실",
            "telephone": "02-2669-8959",
            "@type": "ContactPoint",
        },
        "@type": "Organization",
    },
    "additionalType": "일반공공행정 - 정부자원관리",
    "encodingFormat": "XML",
    "@context": "https://schema.org",
    "@type": "Dataset",
}

RENEWED_FILEDATA = {
    "name": "법제처_법제업무편람",
    "alternateName": "법제처_법제업무편람_20250115",
    "description": (
        "본 자료는 법령의 제정·개정·폐지 및 행정규칙 작성에 필요한 절차, 기준, 역할 분담 등의 내용을 "
        "체계적으로 정리한 편람입니다. 구체적으로 안건 접수, 담당 검토, 의견수렴, 법제심사, "
        "확정·공포까지의 전 과정을 단계별로 안내합니다. 또한 각 단계별 심사항목과 관련 사례를 제시하여 "
        "실무자의 이해를 돕고 일관된 법제 운영을 지원합니다. 조직 내부에서 법적 안정성을 확보하고 "
        "효율적인 법령 관리를 추진하는 데 기초 자료로 활용됩니다. 아울러 권한 주체 간 협업 구조를 "
        "명확히 설명하여 법무·행정 부서의 실무 역량을 제고합니다."
    ),
    "url": "https://www.data.go.kr/data/15000249/fileData.do",
    "keywords": "입법절차,법령심사,국회심의,내부지침,적용사례,심사기준,행정절차,절차안내",
    "license": "공공저작물 : 출처표시, 상업적 이용금지, 변경금지 (제 4유형)",
    "dateCreated": "2025-09-22",
    "dateModified": "2025-11-07",
    "datePublished": "2025-09-22",
    "creator": {
        "name": "법제처",
        "contactPoint": {
            "contactType": "국가법령정보센터",
            "telephone": "044-200-6784",
            "@type": "ContactPoint",
        },
        "@type": "Organization",
    },
    "spatialCoverage": "대한민국",
    "temporalCoverage": "2024년",
    "additionalType": "일반공공행정 - 법제",
    "datasetTimeInterval": "연간",
    "encodingFormat": "PDF",
    "legislation": "",
    "@context": "https://schema.org",
    "@type": "Dataset",
}

RENEWED_STANDARD = {
    "name": "전국지진겸용임시주거시설표준데이터",
    "description": "임시주거시설 중 지진겸용 임시주거시설에 대한 정보",
    "url": "https://www.data.go.kr/data/15072622/standard.do",
    "keywords": "임시주거,지진겸용시설,지진",
    "dateModified": "2021-06-11",
    "datePublished": "2020-12-22",
    "creator": {"name": "행정안전부", "@type": "Organization"},
    "additionalType": "공공질서및안전 - 안전관리",
    "legislation": "재해구호법",
    "@context": "https://schema.org",
    "@type": "Dataset",
}

NOT_FOUND = {
    "description": "해당 데이터는 존재하지 않습니다.",
    "@context": "https://schema.org",
    "@type": "Dataset",
}

# 리뉴얼 전 스키마 (기존 저장분 호환 확인용)
LEGACY_OPENAPI = {
    "title": "한국문화관광연구원_관광실태조사서비스",
    "organization": "한국문화관광연구원",
    "description": "관광실태 정보를 조회하기 위한 서비스",
    "apiType": "REST",
    "url": "https://www.data.go.kr/data/15000017/openapi.do",
    "updateDate": "2022-09-30",
    "license": "제 1유형",
}


class FakeResponse:
    """requests.Response 대역 - 리뉴얼된 포털은 JSON 본문에 text/html 헤더를 붙인다."""

    def __init__(self, payload, status_code=200, content_type="text/html;charset=UTF-8",
                 url="https://www.data.go.kr/catalog/15000017/openapi.json", text=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.url = url
        self.text = text if text is not None else json.dumps(payload, ensure_ascii=False)

    def json(self):
        if self._payload is None:
            raise json.JSONDecodeError("Expecting value", self.text, 0)
        return self._payload


@pytest.fixture
def openapi_scanner():
    return OpenAPIMetadataScanner(15000017, 15000017, max_workers=1)


@pytest.fixture
def filedata_scanner():
    return fileDataMetadataScanner(15000249, 15000249, max_workers=1)


@pytest.fixture
def standard_scanner():
    return standardMetadataScanner(15072622, 15072622, max_workers=1)


# --------------------------------------------------------------------------
# 1. 타입별 extract_data_info - 리뉴얼 스키마 매핑
# --------------------------------------------------------------------------

def test_openapi_maps_renewed_schema(openapi_scanner):
    info = openapi_scanner.extract_data_info(RENEWED_OPENAPI, 15000017, True, 0)

    assert info["title"] == "한국문화관광연구원_관광실태조사서비스"
    assert info["organization"] == "한국문화관광연구원"
    assert info["url"] == "https://www.data.go.kr/data/15000017/openapi.do"
    assert info["api_url"] == info["url"]
    assert info["update_date"] == "2022-09-30"
    assert info["license"].startswith("제3자 권리 포함")
    assert info["classification"] == "일반공공행정 - 정부자원관리"
    assert info["data_format"] == "XML"
    assert info["description"].startswith("관광실태 정보를")
    assert info["status"] == "success"


def test_openapi_extracts_contact_point(openapi_scanner):
    info = openapi_scanner.extract_data_info(RENEWED_OPENAPI, 15000017, True, 0)

    assert info["department"] == "데이터전략실"
    assert info["tel_no"] == "02-2669-8959"


def test_openapi_preserves_raw_metadata(openapi_scanner):
    info = openapi_scanner.extract_data_info(RENEWED_OPENAPI, 15000017, True, 0)

    assert info["metadata"] is RENEWED_OPENAPI
    assert info["metadata"]["@type"] == "Dataset"


def test_filedata_maps_renewed_schema(filedata_scanner):
    info = filedata_scanner.extract_data_info(RENEWED_FILEDATA, 15000249, True, 0)

    assert info["title"] == "법제처_법제업무편람"
    assert info["organization"] == "법제처"
    assert info["url"] == "https://www.data.go.kr/data/15000249/fileData.do"
    assert info["download_url"] == info["url"]
    assert info["update_date"] == "2025-11-07"
    # 상세페이지 "확장자"와 일치하는 값 (실측 확인)
    assert info["file_type"] == "PDF"
    assert info["alternate_name"] == "법제처_법제업무편람_20250115"
    assert info["spatial_coverage"] == "대한민국"
    # 리뉴얼 응답에 fileSize 대응 필드가 없다 - 추정하지 않고 공란
    assert info["file_size"] == ""


def test_standard_maps_renewed_schema(standard_scanner):
    info = standard_scanner.extract_data_info(RENEWED_STANDARD, 15072622, True, 0)

    assert info["title"] == "전국지진겸용임시주거시설표준데이터"
    assert info["organization"] == "행정안전부"
    assert info["url"] == "https://www.data.go.kr/data/15072622/standard.do"
    assert info["standard_url"] == info["url"]
    assert info["update_date"] == "2021-06-11"
    assert info["legislation"] == "재해구호법"
    assert info["classification"] == "공공질서및안전 - 안전관리"


def test_update_date_falls_back_to_date_published(openapi_scanner):
    payload = dict(RENEWED_OPENAPI)
    payload.pop("dateModified")

    info = openapi_scanner.extract_data_info(payload, 15000017, True, 0)

    assert info["update_date"] == "2012-12-06"


# --------------------------------------------------------------------------
# 2. api_type / standard_type - 근거 없으면 채우지 않는다
# --------------------------------------------------------------------------

def test_renewed_openapi_leaves_api_type_unverified(openapi_scanner):
    """리뉴얼 JSON에는 REST/LINK 구분 필드가 없다. encodingFormat으로 추정하지 않는다."""
    info = openapi_scanner.extract_data_info(RENEWED_OPENAPI, 15000017, True, 0)

    assert info["api_type"] == ""
    assert info["openapi_type"] == ""
    assert info["api_type_source"] == "unverified"
    # 포맷 값이 api_type으로 새어 들어가지 않아야 한다
    assert info["data_format"] == "XML"


def test_renewed_standard_leaves_standard_type_unverified(standard_scanner):
    info = standard_scanner.extract_data_info(RENEWED_STANDARD, 15072622, True, 0)

    assert info["standard_type"] == ""
    assert info["standard_type_source"] == "unverified"
    # '@type'(항상 Dataset)이 standard_type으로 새어 들어가면 안 된다
    assert info["standard_type"] != "Dataset"


# --------------------------------------------------------------------------
# 3. 리뉴얼 전 저장분 호환 (옛 키 폴백)
# --------------------------------------------------------------------------

def test_legacy_openapi_schema_still_parses(openapi_scanner):
    info = openapi_scanner.extract_data_info(LEGACY_OPENAPI, 15000017, True, 0)

    assert info["title"] == "한국문화관광연구원_관광실태조사서비스"
    assert info["organization"] == "한국문화관광연구원"
    assert info["api_type"] == "REST"
    assert info["openapi_type"] == "REST"
    assert info["api_type_source"] == "metadata"
    assert info["update_date"] == "2022-09-30"


def test_legacy_filedata_schema_still_parses(filedata_scanner):
    legacy = {
        "title": "법제처_법제업무편람",
        "organization": "법제처",
        "format": "CSV",
        "fileSize": "1024",
        "url": "https://www.data.go.kr/data/15000249/fileData.do",
        "modified": "2020-01-01",
    }

    info = filedata_scanner.extract_data_info(legacy, 15000249, True, 0)

    assert info["title"] == "법제처_법제업무편람"
    assert info["file_type"] == "CSV"
    assert info["fileData_type"] == "CSV"
    assert info["file_size"] == "1024"
    assert info["update_date"] == "2020-01-01"


def test_legacy_standard_schema_still_parses(standard_scanner):
    legacy = {
        "title": "표준데이터",
        "organization": "행정안전부",
        "standardType": "공공시설",
        "standardCode": "STD-001",
        "url": "https://www.data.go.kr/data/1/standard.do",
        "updateDate": "2021-06-11",
    }

    info = standard_scanner.extract_data_info(legacy, 1, True, 0)

    assert info["standard_type"] == "공공시설"
    assert info["standard_type_source"] == "metadata"
    assert info["standard_code"] == "STD-001"


# --------------------------------------------------------------------------
# 4. is_waiting_room_response - 새 스키마에서도 정상 응답으로 판정돼야 한다
# --------------------------------------------------------------------------

def test_renewed_json_with_html_content_type_is_not_waiting_room(openapi_scanner):
    """본문은 JSON인데 Content-Type이 text/html인 함정 - 대기실로 오인하면 안 된다."""
    assert openapi_scanner.is_waiting_room_response(FakeResponse(RENEWED_OPENAPI)) is False


def test_legacy_json_is_not_waiting_room(openapi_scanner):
    assert openapi_scanner.is_waiting_room_response(FakeResponse(LEGACY_OPENAPI)) is False


def test_not_found_json_is_not_waiting_room(openapi_scanner):
    assert openapi_scanner.is_waiting_room_response(FakeResponse(NOT_FOUND)) is False


def test_waiting_room_html_is_detected(openapi_scanner):
    html = "<html><body>접속 대기 중입니다. waitingroom/main.html 로 이동합니다.</body></html>"
    response = FakeResponse(None, text=html)

    assert openapi_scanner.is_waiting_room_response(response) is True


def test_waiting_room_redirect_url_is_detected(openapi_scanner):
    response = FakeResponse(
        None,
        text="<html></html>",
        url="https://www.data.go.kr/waitingroom/main.html",
    )

    assert openapi_scanner.is_waiting_room_response(response) is True


def test_plain_html_error_page_is_not_waiting_room(openapi_scanner):
    response = FakeResponse(None, text="<html><body>페이지를 찾을 수 없습니다.</body></html>")

    assert openapi_scanner.is_waiting_room_response(response) is False


@pytest.mark.parametrize(
    "payload",
    [RENEWED_OPENAPI, RENEWED_FILEDATA, RENEWED_STANDARD, LEGACY_OPENAPI],
)
def test_is_metadata_document_accepts_both_schemas(payload):
    assert is_metadata_document(payload) is True


def test_is_metadata_document_rejects_non_dataset_json():
    assert is_metadata_document({"status": "queued"}) is False
    assert is_metadata_document([]) is False


# --------------------------------------------------------------------------
# 5. check_metadata 통합 - 네트워크는 전부 대역으로 대체
# --------------------------------------------------------------------------

def _patch_get(monkeypatch, response):
    import scanner.base_scanner as base_scanner

    monkeypatch.setattr(base_scanner.requests, "get", lambda *a, **kw: response)


def test_check_metadata_success_records_number(monkeypatch, openapi_scanner):
    _patch_get(monkeypatch, FakeResponse(RENEWED_OPENAPI))

    result = openapi_scanner.check_metadata(15000017)

    assert result["status"] == "success"
    assert result["has_data"] is True
    assert result["title"] == "한국문화관광연구원_관광실태조사서비스"
    assert openapi_scanner.results["data_numbers"] == [15000017]


def test_check_metadata_not_found(monkeypatch, openapi_scanner):
    _patch_get(monkeypatch, FakeResponse(NOT_FOUND))

    result = openapi_scanner.check_metadata(15000017)

    assert result["status"] == "not_found"
    assert result["has_data"] is False
    assert openapi_scanner.results["data_numbers"] == []


def test_check_metadata_http_404(monkeypatch, standard_scanner):
    _patch_get(monkeypatch, FakeResponse(None, status_code=404, text="<html>404</html>"))

    result = standard_scanner.check_metadata(15072618)

    assert result["status"] == "not_found"


def test_check_metadata_non_json_body_reports_json_error(monkeypatch, openapi_scanner):
    _patch_get(monkeypatch, FakeResponse(None, text="<html><body>정상 페이지</body></html>"))

    result = openapi_scanner.check_metadata(15000017)

    assert result["status"] == "error"
    assert result["error"] == "잘못된 JSON 형식"


def test_filedata_type_distribution_is_aggregated(monkeypatch, filedata_scanner):
    """data_types 집계 키는 f'{scan_type}_type' 이다 - 별칭이 없으면 통계가 비어버린다."""
    _patch_get(monkeypatch, FakeResponse(RENEWED_FILEDATA))

    filedata_scanner.check_metadata(15000249)

    assert filedata_scanner.results["data_types"] == {"PDF": 1}


def test_openapi_type_distribution_stays_empty_without_evidence(monkeypatch, openapi_scanner):
    _patch_get(monkeypatch, FakeResponse(RENEWED_OPENAPI))

    openapi_scanner.check_metadata(15000017)

    assert openapi_scanner.results["data_types"] == {}


def test_legacy_openapi_type_distribution_is_aggregated(monkeypatch, openapi_scanner):
    _patch_get(monkeypatch, FakeResponse(LEGACY_OPENAPI))

    openapi_scanner.check_metadata(15000017)

    assert openapi_scanner.results["data_types"] == {"REST": 1}


def test_save_results_writes_type_files(monkeypatch, tmp_path, filedata_scanner):
    _patch_get(monkeypatch, FakeResponse(RENEWED_FILEDATA))

    filedata_scanner.results["details"][15000249] = filedata_scanner.check_metadata(15000249)
    filedata_scanner.results["total"] = 1
    filedata_scanner.results["with_data"] = 1
    paths = filedata_scanner.save_results(output_dir=str(tmp_path))

    type_file = tmp_path / "fileData" / "fileData_type_PDF.json"
    assert type_file.exists()
    payload = json.loads(type_file.read_text(encoding="utf-8"))
    assert payload["numbers"] == [15000249]

    metadata = json.loads((tmp_path / "fileData" / "fileData_metadata.json").read_text(encoding="utf-8"))
    assert metadata["15000249"]["organization"] == "법제처"
    assert paths["summary_file"].endswith("summary.json")
