# Nara Combiner

Nara Combiner는 여러 공공 API 문서의 메타데이터를 조합해 행정 서비스 계획 초안을 만드는 프로젝트다. 실제 정부24 또는 기관 시스템 실행은 하지 않는다. 실행, 승인, dry-run, 감사 로그는 범위 밖이다 (실행기 프로젝트는 archive/에 보류).

## 역할

- API 문서 로딩
- 서비스 ID 기반 API 조합
- 조합 가능성, 필요 입력값, 후속 실행 후보 설명
- LLM 기반 조합 제안 생성
- 조합 결과 계획 초안 작성

하지 않는 일:

- 정부24/기관 페이지 자동 제출
- 사용자 승인 처리
- dry-run 실행
- 실행 로그 또는 감사 로그 저장

## 실행

```powershell
cd "D:\project\nara_combiner(API문서조합기)"
pip install -r requirements.txt
python .\app\main.py
```

기본 서버:

```text
http://127.0.0.1:8003
```

## API

### `GET /health`

로드된 API 문서 수와 사용 모델을 확인한다.

### `POST /compose`

```json
{
  "service_ids": ["15000827", "15080662", "15051043"],
  "question": "이 API들을 조합하면 어떤 행정 서비스 계획을 만들 수 있나?"
}
```

- `service_ids`: 1~10개. 순수 api_id(`15000827`)와 Search 정식 ID(`openapi_new:15000827`)
  모두 허용 (경계에서 내부 ID로 변환만 하고 재해석하지 않음)
- `question`: 최대 500자

성공 응답(200) 필수 필드:

| 필드 | 의미 |
| --- | --- |
| `service_ids` | 요청한 ID 원본 목록 |
| `domains` | 선택된 서비스의 분류체계 집합 |
| `warning` | 같은 도메인 조합 등 주의 문구 (없으면 null) |
| `missing` | 카탈로그에서 찾지 못한 ID (일부 누락은 200 + 이 필드로 보고) |
| `suggestion` | LLM 조합 제안 본문 |
| `truncated` | 길이 예산(`COMBINER_MAX_SUGGESTION_CHARS`, 기본 4000자) 초과로 잘렸는지 |
| `elapsed_ms`, `model` | 진단 정보 |

오류 응답 계약:

| 상황 | 상태 | `error_code` |
| --- | --- | --- |
| 전체 ID 누락 | 404 | `NO_SERVICES_FOUND` |
| Ollama 연결 실패·시간 초과·오류 응답 | 503 | `UPSTREAM_UNAVAILABLE` |
| 빈 `service_ids`, 10개 초과, 질문 500자 초과 | 422 | (FastAPI validation) |

오류 본문은 `{ok: false, error_code, message}` 형식이며 기존 UI 호환을 위해 `error` 키도 함께 담는다.

응답은 조합 아이디어와 계획 초안이다. 실행·승인 기능은 이 서비스에 포함하지 않는다 (실행기 프로젝트는 archive/에 보류).

### `GET /compose-stream`

SSE 스트리밍 응답을 반환한다.

```text
/compose-stream?ids=15000827,15080662&q=복지와 교통 지원을 조합해줘
```

## 환경 변수

```text
NARA_DATA_DIR=..\nara_storage\openapi_new   # 기본값 (미설정 시)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b
```

## 테스트

```powershell
python -m pytest tests -v
```
