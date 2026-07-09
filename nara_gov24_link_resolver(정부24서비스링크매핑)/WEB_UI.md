# Gov24 Link Resolver Web UI

브라우저에서 후보 링크를 추가하고, 검토 상태를 바꾸고, 기존 처리 스크립트를 실행할 수 있는 로컬 UI입니다.

```powershell
cd "C:\project\nara_gov24_link_resolver(정부24서비스링크매핑)"
python web_app.py --port 8765
```

브라우저에서 `http://127.0.0.1:8765/`를 엽니다.

## 제공 기능

- `data/working/link_candidates.jsonl` 후보 목록 조회, 검색, 상태 변경
- 후보 링크 수동 추가
- `normalize_links.py`, `match_services.py`, `validate_outputs.py` 개별 또는 전체 실행
- `data/output/gov24_service_metadata.jsonl` 메타데이터 조회
- `data/output/link_resolution_report.json` 검증 리포트 조회
