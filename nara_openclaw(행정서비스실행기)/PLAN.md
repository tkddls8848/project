# Nara OpenClaw Execution Plan

작성일: 2026-05-25

## 목표

`nara_openclaw(행정서비스실행기)`는 API 문서 조합기가 만든 실행 계획을 받아 실제 행정 처리 흐름으로 연결하는 서비스다. 핵심 책임은 승인, dry-run, 실행 어댑터, 결과 기록, 감사 로그다.

## 경계

- `nara_combiner(API문서조합기)`: API 문서 조합과 `ExecutionPlan` 생성
- `nara_openclaw(행정서비스실행기)`: `ExecutionPlan` 검증, 사용자 승인, 실행, 로그 저장

OpenClaw는 조합 아이디어나 LLM 응답을 생성하지 않는다.

## 현재 구현

- `GET /demo/plan`: 테스트용 행정 실행 계획 반환
- `POST /execute/dry-run`: 누락 입력값, 승인 필요 여부, 전송 예정 payload 확인
- `POST /execute`: 승인된 계획만 더미 정부 실행 어댑터로 실행
- `GET /runs/{run_id}`: 실행 결과와 감사 로그 조회

## 실행 어댑터

현재는 `DummyGovernmentExecutor`만 구현되어 있다.

- `api`: 실제 API 제출을 흉내 내고 더미 접수번호를 생성
- `linkout`: 정부24/기관 페이지 링크를 사용자에게 넘길 준비
- `manual`: 자동화 불가 단계의 체크리스트 생성

실제 정부24 또는 기관 시스템 연동은 같은 인터페이스를 유지하면서 새 어댑터로 추가한다.

## 승인 원칙

- `dry-run`은 외부 실행을 하지 않는다.
- `execute`는 승인 정보가 없으면 403으로 차단한다.
- 민감 입력값은 실행 로그에서 마스킹한다.
- 모든 실행은 `runs/{run_id}.json`으로 저장한다.

## 다음 단계

1. 실제 정부24 링크 매핑 데이터를 `nara_gov24_link_resolver` 산출물에서 읽기
2. `ExecutionPlan` 입력을 `nara_combiner` 출력 스키마와 고정
3. 실제 HTTP API 어댑터를 dry-run 우선으로 추가
4. 사용자 승인 화면 또는 CLI 승인 흐름 추가
5. 실행 로그 암호화 또는 민감정보 완전 배제 정책 강화
