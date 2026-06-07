# Nara Combiner 계획

작성일: 2026-05-25

## 목표

`nara_combiner(API문서조합기)`는 공공 API 문서 여러 개를 읽고, 단일 API로는 만들 수 없는 행정 서비스 계획 초안을 생성한다.

최종 실행은 담당하지 않는다. 실행 책임은 `nara_openclaw(행정서비스실행기)`로 분리한다.

## 책임

- API 문서 메타데이터 로딩
- 서비스 ID 기반 API 선택
- API 간 조합 가능성 분석
- 필요한 사용자 입력값과 조건 추정
- 실행기에게 넘길 수 있는 계획 초안 작성

## 비책임

- 정부24 또는 기관 시스템 호출
- 신청서 제출
- 사용자 승인 처리
- dry-run 실행
- 실행 이력 저장
- 감사 로그 저장

## 현재 엔드포인트

```text
GET /health
POST /compose
GET /compose-stream
```

## 출력 방향

현재 `/compose`는 자연어 조합 제안을 반환한다. 다음 단계에서는 아래 형태의 구조화된 계획 초안을 반환하도록 확장한다.

```json
{
  "goal": "부모님 병원 이동 지원과 복지 신청 준비",
  "candidate_services": ["15080662", "15051043"],
  "required_inputs": ["region", "birth_date", "income_type"],
  "handoff_target": "nara_openclaw",
  "notes": ["실제 제출은 실행기 승인 흐름에서 처리"]
}
```

## OpenClaw와의 경계

```text
nara_combiner
  API 문서 -> 조합 후보 -> 계획 초안

nara_openclaw
  계획 초안 -> dry-run -> 사용자 승인 -> 실행 어댑터 -> 실행 로그
```

## 다음 작업

1. `/compose` 응답을 구조화된 계획 초안으로 확장
2. `nara_openclaw` 입력 스키마와 호환되는 handoff JSON 정의
3. 조합 결과에 실행 가능/수동 처리/링크 이동 후보를 구분해 표시
4. 조합기 UI에서 "OpenClaw로 넘기기"용 JSON 보기 추가
