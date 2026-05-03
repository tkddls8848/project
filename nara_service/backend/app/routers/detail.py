"""Detail Data Router - /detail/* endpoints"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
import json
import logging

from app.auth import verify_api_key
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detail", tags=["detail"])


@router.get("/{data_type}/{doc_id}/{endpoint}")
async def get_detail_dynamic_endpoint(
    data_type: str,
    doc_id: str,
    endpoint: str,
    request: Request,
    _: bool = Depends(verify_api_key)
) -> JSONResponse:
    """
    유동적 엔드포인트 처리
    - 모든 타입(fileData, OpenAPI_link, Standard 등)과 엔드포인트(getAll, getEach, getUrl 등)를 처리

    **인증 필요:** X-API-Key 헤더
    """
    # Path Traversal 방지
    if ".." in doc_id or "/" in doc_id or "\\" in doc_id:
        raise HTTPException(status_code=400, detail="Invalid doc_id")

    if ".." in data_type or "/" in data_type or "\\" in data_type:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    try:
        # 타입 매핑 (대소문자 처리)
        type_map = {
            "standard": {"dir": "standard", "prefix": "standard"},
            "fileData": {"dir": "filedata", "prefix": "fileData"},
            "openapi_link": {"dir": "openapi_link", "prefix": "openapi_link"},
            "openapi_new": {"dir": "openapi_new", "prefix": "openapi_new"},
            "openapi_old": {"dir": "openapi_old", "prefix": "openapi_old"}
        }

        type_info = type_map.get(data_type, {"dir": data_type.lower(), "prefix": data_type})
        dir_name = type_info["dir"]
        file_prefix = type_info["prefix"]

        filename = f"{file_prefix}_{doc_id}_refined.json"
        detail_file_path = settings.storage_path / "data" / dir_name / filename

        if not detail_file_path.exists():
            logger.error(f"File not found: {detail_file_path}")
            raise HTTPException(status_code=404, detail="File not found")

        with open(detail_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # endpoint별 처리
        if endpoint == "getAll":
            # 타입별 전체 조회
            if data_type.lower() in ["standard"]:
                grid_table = data.get("grid_table", [])
                return JSONResponse(content={"grid_table": grid_table})
            elif data_type.lower() == "filedata":
                download_urls = data.get("content", {}).get("download_urls", {})
                return JSONResponse(content={"download_urls": download_urls})
            elif data_type.lower() == "openapi_link":
                target_url = data.get("content", {}).get("target_url")
                if not target_url:
                    raise HTTPException(status_code=404, detail="Target URL not found")
                return JSONResponse(content={"target_url": target_url})
            else:
                # 기본: 전체 데이터 반환
                return JSONResponse(content=data)

        elif endpoint == "getEach":
            # 타입별 개별 조회/필터링
            if data_type.lower() in ["standard"]:
                # Standard: 쿼리 파라미터로 필터링
                grid_table = data.get("grid_table", [])
                query_params = dict(request.query_params)

                if not query_params:
                    return JSONResponse(content={"grid_table": grid_table})

                # mappings.json 로드 (영문 → 한글 역매핑)
                mappings_path = settings.storage_path / "data" / "standard" / "mappings.json"
                reverse_mappings = {}

                if mappings_path.exists():
                    with open(mappings_path, "r", encoding="utf-8") as f:
                        mappings = json.load(f)
                        reverse_mappings = {v: k for k, v in mappings.items()}

                # 필터링
                filtered_data = []
                for row in grid_table:
                    match = True
                    for eng_key, value in query_params.items():
                        kor_key = reverse_mappings.get(eng_key, eng_key)

                        if kor_key in row:
                            if value.lower() not in str(row[kor_key]).lower():
                                match = False
                                break
                        else:
                            match = False
                            break

                    if match:
                        filtered_data.append(row)

                return JSONResponse(content={"grid_table": filtered_data})

            elif data_type.lower() == "filedata":
                # FileData: keys 파라미터로 특정 키 조회
                keys = request.query_params.get("keys")
                if not keys:
                    raise HTTPException(status_code=400, detail="Missing 'keys' parameter")

                download_urls = data.get("content", {}).get("download_urls", {})

                if keys not in download_urls:
                    raise HTTPException(status_code=404, detail=f"Key '{keys}' not found")

                return JSONResponse(content={keys: download_urls[keys]})
            else:
                # 기본: 쿼리 파라미터로 필터링 시도
                return JSONResponse(content=data)

        else:
            # 알 수 없는 엔드포인트
            raise HTTPException(status_code=404, detail="Unknown endpoint")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in dynamic endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{data_type}/{doc_id}")
async def get_detail_data(
    data_type: str,
    doc_id: str,
    _: bool = Depends(verify_api_key)
) -> JSONResponse:
    """
    상세 데이터 조회 (data 디렉토리에서 JSON 파일 읽기)

    **인증 필요:** X-API-Key 헤더

    Args:
        data_type: 데이터 타입 (fileData, openapi_link, openapi_new, openapi_old, standard)
        doc_id: 문서 번호

    Returns:
        JSON: 상세 데이터
    """
    # Path Traversal 방지
    if ".." in doc_id or "/" in doc_id or "\\" in doc_id:
        raise HTTPException(status_code=400, detail="Invalid doc_id")

    if ".." in data_type or "/" in data_type or "\\" in data_type:
        raise HTTPException(status_code=400, detail="Invalid data_type")

    try:
        # 디버그 로그
        logger.debug(f"Fetching detail data - data_type: {data_type}, doc_id: {doc_id}")

        # 디렉토리명 및 파일명 prefix 매핑
        # 타입 매핑 (대소문자 처리)
        type_map = {
            "standard": {"dir": "standard", "prefix": "standard"},
            "fileData": {"dir": "filedata", "prefix": "fileData"},
            "openapi_link": {"dir": "openapi_link", "prefix": "openapi_link"},
            "openapi_new": {"dir": "openapi_new", "prefix": "openapi_new"},
            "openapi_old": {"dir": "openapi_old", "prefix": "openapi_old"}
        }

        # 타입이 매핑에 없으면 소문자로 변환
        type_info = type_map.get(data_type, {"dir": data_type.lower(), "prefix": data_type.lower()})
        dir_name = type_info["dir"]
        file_prefix = type_info["prefix"]

        logger.debug(f"Type mapped - data_type: {data_type} -> dir: {dir_name}, file_prefix: {file_prefix}")

        # 파일명 생성: 타입_문서번호_refined.json
        filename = f"{file_prefix}_{doc_id}_refined.json"
        detail_file_path = settings.storage_path / "data" / dir_name / filename

        logger.debug(f"File path: {detail_file_path}")

        if not detail_file_path.exists():
            logger.error(f"File not found: {detail_file_path}")
            raise HTTPException(
                status_code=404,
                detail="Detail data file not found"
            )

        with open(detail_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return JSONResponse(content=data)

    except json.JSONDecodeError as e:
        logger.error(f"JSON Parse Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File Read Error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )
