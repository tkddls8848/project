# Nara Combiner

Nara Combiner는 여러 공공 API 문서의 메타데이터를 조합해 행정 서비스 계획 초안을 만드는 프로젝트다. 실제 정부24 또는 기관 시스템 실행은 하지 않는다. 실행, 승인, dry-run, 감사 로그는 `nara_openclaw(행정서비스실행기)`의 책임이다.

## 역할

- API 문서 로딩
- 서비스 ID 기반 API 조합
- 조합 가능성, 필요 입력값, 후속 실행 후보 설명
- LLM 기반 조합 제안 생성
- `nara_openclaw`로 넘길 수 있는 계획 초안 작성

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

응답은 조합 아이디어와 계획 초안이다. 실제 실행은 이 응답을 구조화한 뒤 `nara_openclaw(행정서비스실행기)`에 전달한다.

### `GET /compose-stream`

SSE 스트리밍 응답을 반환한다.

```text
/compose-stream?ids=15000827,15080662&q=복지와 교통 지원을 조합해줘
```

## 환경 변수

```text
NARA_DATA_DIR=.\apidata
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:e4b
```

## 테스트

```powershell
python -m pytest tests -v
```
