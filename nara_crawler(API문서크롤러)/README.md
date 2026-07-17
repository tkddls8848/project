# Nara Crawler - Korean Public API Documentation Crawler

Crawler for Korean public-API documentation from data.go.kr.

## 산출물 경로

크롤링 결과는 저장소 공통 데이터 루트 `../nara_storage/`에 저장된다 (run 폴더 없음).

- `../nara_storage/openapi_new/{api_id}.json` — OpenAPI(신형) 문서
- `../nara_storage/openapi_link/{api_id}.json` — LINK형 문서
- `../nara_storage/fileData/{api_id}.json`, `../nara_storage/standard/{api_id}.json`
- `../nara_storage/manifests/{run_id}.json` — 실행별 manifest (수집 파일 목록·체크섬)
- `../nara_storage/manifests/{run_id}_{type}_summary.json` — 실행별 요약

같은 api_id를 다시 크롤링하면 해당 파일을 덮어쓴다 (최신 1파일 유지).
`-o/--output-dir`로 다른 경로를 지정할 수 있다.
