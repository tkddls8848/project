# 행정서비스실행기 현행화 계획

Status: proposed · 구현: 없음 · 현재 구현의 정본은 CLAUDE.md와 system-architecture.html

## 1. 결론

행정서비스실행기는 Prometheus 내부 기능으로 편입하지 않고, 별도의 **행정 실행 통제 서비스**로 현행화한다.

현재 Prometheus 계획 문서에서 말하는 "실행 가능한 서비스"는 행정 신청·제출을 의미하지 않는다. `ScenarioDoc`은 `fetch`와 `display`만 허용하고 실제 행정 처리를 명시적으로 제외한다. 현재 코드 역시 `DesignResponse.plan`을 반환하는 설계 단계까지만 구현되어 있다.

따라서 `archive/nara_openclaw(행정서비스실행기)`는 그대로 복구할 대상이 아니다. 아카이브의 `dry-run -> 승인 -> adapter -> 감사 기록` 개념은 유지하되, 인증·인가, 승인 결속, 영속 상태 관리, 멱등성, 복구 가능한 실행 Worker를 갖춘 별도 서비스로 다시 구현한다.

## 2. 현재 상태와 경계

### Prometheus

- 공공 API 문서를 탐색하고 근거가 있는 서비스 계획을 만든다.
- LLM 결과에서 필요한 식별자만 취하고 Search·Combiner의 원본 데이터를 다시 조회한다.
- 실제 행정 처리나 외부 시스템 변경을 수행하지 않는다.
- 향후 `ScenarioDoc`과 서비스 팩토리가 구현되더라도 조회 API 호출과 화면 표시만 담당한다.

### 아카이브 행정서비스실행기

아카이브에는 다음 골격이 있다.

- `POST /execute/dry-run`
- 명시적 승인 후 `POST /execute`
- 실행 Adapter 경계
- 실행 결과 조회
- 입력값 마스킹
- 차단 요청을 포함한 JSON 감사 기록

아카이브 테스트는 현재 16개가 통과하지만, 이는 Dummy Adapter 계약만 검증한다. 실제 기관 제출에 필요한 보안·데이터 무결성·장애 복구 수준을 의미하지 않는다.

## 3. 목표 구조

```text
Prometheus - 설계 영역, 항상 읽기 전용
  `- 근거 검증된 ScenarioDoc / ActionIntent
                  |
                  v
행정서비스실행기 - 실행 통제 영역
  |- 계획 재검증
  |- 인증·권한 확인
  |- dry-run 및 영향 요약
  |- 사용자 재인증·승인
  |- 멱등성·상태 관리
  |- 감사 이벤트 저장
  `- 승인된 Adapter 호출
                  |
          +-------+--------+
          |       |        |
          v       v        v
      Refresher  기관 API  사용자 직접 처리
      Adapter    Adapter    Linkout/Manual
```

핵심 원칙은 다음과 같다.

- Prometheus는 실행 대상을 제안할 수 있지만 실행하지 않는다.
- 실행기는 Prometheus가 전달한 URL, 메서드, 승인자 정보를 그대로 신뢰하지 않는다.
- 실제 쓰기 작업은 서버에 사전 등록·검토된 `operation_id`만 실행한다.
- 인증정보와 개인정보는 계획 문서나 생성된 번들에 포함하지 않는다.
- LLM은 실제 요청 본문, 대상 URL, 승인 여부를 결정하지 않는다.
- 앱과 서비스는 구현을 직접 import하지 않고 HTTP 경계를 유지한다.

## 4. 아카이브에서 유지할 것과 폐기할 것

### 유지할 개념

- `ExecutionPlan`과 단계별 실행 결과
- dry-run과 실제 실행의 분리
- Adapter 인터페이스
- 실행 상태 조회
- 차단·실패를 포함한 감사 기록
- Dummy Adapter를 이용한 테스트

### 그대로 사용하지 않을 구현

#### 4.1 임의 대상 URL과 메서드

기존 `ExecutionStep`은 클라이언트가 `target_url`과 `method`를 전달한다. 실제 Adapter가 이를 사용하면 SSRF, 임의 기관 호출, 잘못된 엔드포인트 제출이 가능하다.

현행 구현에서는 요청에 URL을 받지 않고, 등록된 `operation_id`가 서버 측 허용 대상과 연결되어야 한다.

#### 4.2 자기 선언식 승인

기존 구현은 `approved=true`와 임의의 `approver` 문자열만 검사한다. `approval_token` 필드가 있지만 실제 검증하지 않는다.

승인자는 인증 세션에서 식별하고, 승인은 계획 hash·입력 요약·실행 ID·만료 시각에 결속해야 한다.

#### 4.3 실행 시 계획 전체 재수신

클라이언트가 승인 후 실행 단계에서 계획 전체를 다시 보내면 승인된 계획과 실제 실행 계획이 달라질 수 있다.

서버가 검증된 계획을 먼저 저장하고, 이후 API는 `plan_id`, `plan_version`, `content_hash`로만 이를 참조해야 한다.

#### 4.4 JSON 파일 기반 상태 저장

기존 저장 방식은 원자적 갱신, 동시성 보호, 중복 요청 방지, append-only 감사 기록이 없다. 실제 실행 기록은 데이터베이스와 명시적인 상태 전이로 관리한다.

#### 4.5 멱등성과 장애 복구 부재

기관이 요청을 처리한 뒤 응답 수신 전에 프로세스가 종료되면 성공 여부를 알 수 없다. 단순 재시도는 중복 신청을 만들 수 있다.

모든 실행과 단계에 멱등 키를 두고, 결과가 불명확하면 재시도하지 않고 `outcome_unknown` 상태에서 조회·조정 절차를 수행한다.

#### 4.6 잘못된 완료 의미

기존 Dummy Adapter는 `manual`과 `linkout`을 `completed`로 처리한다. 실제 사용자 조치가 남아 있으므로 `awaiting_user`로 처리해야 한다.

## 5. 새로운 실행 계약

계획된 `ScenarioDoc`에 행정 제출 단계를 추가하지 않고 별도의 `ExecutionPlan` 계약을 정의한다.

### 5.1 ExecutionPlan

최소 필드는 다음과 같다.

- `schema_version`
- `plan_id`
- `plan_version`
- `content_hash`
- `source_scenario_id`
- `created_at`
- `expires_at`
- `steps`
- `required_approval_policy`
- 근거 문서와 검증 결과 참조

단계는 임의 URL 대신 등록된 작업을 참조한다.

```json
{
  "step_id": "extend-api-key-1",
  "operation_id": "data-go-kr.api-key.extend.v1",
  "operation_version": "1.0",
  "depends_on": [],
  "input_refs": {
    "account_id": "user_input.account_id"
  },
  "risk_level": "high",
  "timeout_seconds": 120
}
```

### 5.2 OperationSpec

`operation_id`는 서버가 관리하는 승인된 작업 카탈로그와 연결한다. 각 작업 정의에는 다음을 둔다.

- 사용할 Adapter
- 허용된 기관·호스트·경로·HTTP 메서드
- 입력 및 결과 JSON Schema
- 읽기/쓰기 여부
- 위험 등급
- 필요한 사용자 권한과 승인 방식
- dry-run 지원 여부
- 멱등성 지원 여부
- 안전한 재시도 조건
- 성공 확인 방법
- 보상 또는 수동 복구 절차

계획 작성자가 임의 URL, Python 코드, 셸 명령 또는 import 경로를 지정할 수 없어야 한다.

## 6. 승인 흐름

기존 `approved: true` 방식은 폐기하고 다음 절차를 사용한다.

1. 실행 요청을 `pending_validation` 상태로 저장한다.
2. 서버가 계획, 입력 Schema, 작업 등록 상태와 근거 최신성을 재검증한다.
3. dry-run 결과와 실제 영향 범위를 사용자에게 표시한다.
4. 서버가 일회용 승인 challenge를 발급한다.
5. 로그인한 사용자가 재인증 후 승인한다.
6. 승인을 다음 값에 결속한다.
   - `run_id`
   - `plan_hash`
   - 입력값의 마스킹된 요약 hash
   - 승인자 ID
   - 승인 시각과 만료 시각
7. 실행 직전에 같은 hash를 다시 검증한다.
8. 승인 이후 계획이나 입력이 변경되면 승인을 무효화한다.

승인자 ID는 요청 본문에서 받지 않고 인증 세션에서 가져온다. 다중 사용자 환경에서는 요청자와 승인자를 분리하는 정책도 지원한다.

## 7. 실행 상태 모델

```text
draft
  -> validating
  -> blocked | awaiting_approval
  -> approved
  -> queued
  -> running
  -> succeeded
       |-> partially_succeeded
       |-> failed
       |-> outcome_unknown
       |-> awaiting_user
       `-> cancelled
```

`outcome_unknown`은 기관이 요청을 처리했지만 응답을 받지 못한 경우를 뜻한다. 이 상태에서는 자동 재시도를 금지하고 영수증·신청 목록 조회 또는 수동 확인을 먼저 수행한다.

`manual`과 `linkout`은 `succeeded`가 아니라 `awaiting_user`로 처리한다. 사용자가 완료 증빙을 제출한 후 별도 완료 상태로 전환한다.

## 8. 서비스 구성

```text
apps/epilogue/
  api/
    main.py
    auth.py
  domain/
    plans.py
    operations.py
    state_machine.py
    approvals.py
    policies.py
  adapters/
    base.py
    registry.py
    dummy.py
    refresher.py
  worker/
    runner.py
    reconciliation.py
  infra/
    database.py
    secrets.py
    audit.py
  tests/
```

실제 외부 요청을 FastAPI 요청 처리 안에서 직접 수행하지 않는다. API는 실행을 저장하고 Worker queue에 전달하며, Worker가 lease를 획득해 실행한다. 프로세스가 종료되면 만료된 lease를 안전하게 회수할 수 있어야 한다.

초기 로컬 버전은 SQLite WAL을 사용할 수 있다. 최소 테이블은 다음과 같다.

- `execution_plans`
- `execution_runs`
- `step_runs`
- `approvals`
- `audit_events`
- `idempotency_keys`
- `adapter_receipts`

상태 변경과 감사 이벤트 추가는 하나의 DB transaction으로 처리한다. 감사 이벤트는 기존 기록을 수정하지 않는 append-only 구조로 저장한다.

## 9. API 초안

| 메서드 | 경로 | 동작 |
|---|---|---|
| `POST` | `/execution-plans/validate` | 계획을 검증하고 dry-run 결과 반환 |
| `POST` | `/execution-runs` | 검증된 계획으로 실행 요청 생성; 아직 실행하지 않음 |
| `GET` | `/execution-runs/{id}` | 현재 상태와 단계 결과 조회 |
| `GET` | `/execution-runs/{id}/events` | append-only 감사·진행 이벤트 조회 |
| `POST` | `/execution-runs/{id}/approvals` | 재인증된 사용자의 승인 기록 |
| `POST` | `/execution-runs/{id}/start` | 유효한 승인이 있는 실행을 queue에 등록 |
| `POST` | `/execution-runs/{id}/cancel` | 실행 전 또는 취소 가능한 단계에서 중단 |
| `POST` | `/execution-runs/{id}/reconcile` | 결과 불명 상태를 외부 영수증과 조정 |

`POST /execution-runs`에는 `Idempotency-Key`를 필수로 요구한다. 승인과 실행을 하나의 요청으로 합치지 않는다.

## 10. 중복 실행과 재시도 정책

- 같은 사용자, 같은 계획 hash, 같은 `Idempotency-Key`의 요청은 기존 run을 반환한다.
- 단계별 key는 `run_id + plan_hash + step_id`에서 파생한다.
- 외부 기관이 멱등 키를 지원하면 해당 키를 전달한다.
- 외부 기관이 멱등성을 지원하지 않으면 쓰기 요청을 자동 재시도하지 않는다.
- timeout 후에는 영수증·신청 목록 조회 Adapter로 결과를 먼저 조정한다.
- 결과 확인이 불가능하면 `outcome_unknown`으로 전환하고 사람의 판단을 요구한다.
- 여러 기관 작업을 하나의 전역 transaction처럼 취급하지 않는다.
- 부분 성공을 정상적인 상태로 모델링하고 후속 수동 복구 절차를 제공한다.

## 11. 비밀정보와 개인정보

계획에는 실제 자격증명이나 주민정보를 넣지 않는다.

- 서비스키·OAuth token은 `secret_ref`만 저장한다.
- 실제 값은 OS 자격증명 저장소나 별도 Secret Store에서 Worker만 조회한다.
- 주민번호·문서·연락처는 가능하면 실행 시 메모리에서만 사용한다.
- 저장이 필요한 개인정보는 필드 단위 암호화와 보존 기한을 적용한다.
- 로그는 키 이름 기반 마스킹만 믿지 않고 구조화된 allowlist 방식으로 생성한다.
- Adapter 응답은 허용된 필드만 감사 기록에 투영한다.
- 에러 본문, 예외, 외부 응답 원문을 그대로 기록하지 않는다.
- 사용자 입력, 승인 token, 기관 응답에 대한 로그 누출 테스트를 둔다.

아카이브의 재귀 마스킹은 보조 수단으로 재사용할 수 있지만, 알려진 키 이름만 가리므로 단독 보호 수단으로 사용하지 않는다.

## 12. Prometheus 연동

Prometheus의 계획된 `ScenarioDoc`은 조회 전용으로 유지한다. 행정 실행을 위해서는 별도의 `ActionIntent`를 만들고 다음 조건을 모두 만족할 때만 executor로 전달한다.

- Prometheus critic 통과
- 관련 근거 문서와 기관 정보가 최신 상태
- 선택된 서비스에 대응하는 등록된 `OperationSpec` 존재
- 임의 URL이나 LLM 생성 요청 본문을 포함하지 않음
- 해당 작업이 현재 실행 정책에서 허용됨

Prometheus UI의 사용자 흐름은 다음과 같이 분리한다.

1. 계획 보기
2. 행정 실행 요청으로 변환
3. 실행 가능성 검사
4. 영향 확인 및 승인
5. 실행 상태 보기

Prometheus는 executor에 실행 요청을 생성하는 데까지만 관여한다. 실제 승인 검증, credential 조회, Adapter 호출, 상태 저장은 모두 executor가 소유한다.

## 13. Refresher를 첫 실제 Adapter로 사용

현행화의 첫 실제 Adapter는 `modules/refresher`가 적합하다. 이미 다음 안전장치를 갖고 있다.

- 기본 실행은 dry-run
- 실제 제출에 `commit` 필요
- UI 실행에는 별도의 `confirm_commit` 필요
- `127.0.0.1` 바인딩
- CORS 미사용

executor는 Refresher 코드를 직접 import하지 않고 HTTP로 연동한다.

1. read-only 목록 조회
2. 대상과 영향 범위 dry-run
3. 사용자 승인
4. executor가 Refresher에 `commit + confirm_commit` 요청
5. Refresher run 이벤트와 최종 결과 수집
6. executor 감사 이벤트에 외부 run ID와 결과 저장

Refresher의 기존 이중 확인은 executor 승인으로 대체하지 않는다. 두 계층의 확인을 유지해 우발적인 실제 제출을 막는다.

## 14. 구현 단계

### 1단계: 계약과 Dummy 실행기

- 새 `apps/epilogue` 서비스 생성
- `ExecutionPlan`, `OperationSpec`, 상태 전이 정의
- SQLite 기반 영속 저장
- Dummy Adapter 구현
- dry-run, 승인, 실행 API 분리
- 임의 URL·메서드·코드 입력 금지
- 인증된 사용자 기반 승인

### 2단계: 복구 가능한 Worker

- API와 Worker 분리
- 작업 lease와 crash recovery
- 단계별 timeout
- idempotency key
- `outcome_unknown`과 reconciliation
- append-only 감사 이벤트
- 실행 취소와 안전한 재시도

### 3단계: Refresher Adapter

- Refresher read-only 조회 연결
- dry-run 결과 비교
- 승인 후 `commit + confirm_commit`
- 중복 실행·부분 실패·프로세스 종료 테스트
- 실제 실행 기능 플래그 기본값 비활성

### 4단계: Prometheus 연동

- `ScenarioDoc`과 별도의 `ActionIntent` 정의
- 등록된 `operation_id`만 선택 가능
- 계획 hash와 근거 문서 버전 기록
- executor에서 모든 정보를 다시 검증
- Prometheus는 실행 요청 생성까지만 담당

### 5단계: 기관별 Adapter 확대

- 기관별 Adapter를 하나씩 수동 검토 후 등록
- 자동 생성된 OpenAPI client는 참고 코드로만 사용
- 검토·서명되지 않은 생성 코드는 실행 등록 금지
- OAuth·전자서명·첨부파일은 기관별 위협 모델 작성 후 지원

## 15. 필수 테스트

- 미등록 `operation_id`, 임의 URL, 임의 메서드 차단
- 인증되지 않은 실행·승인·조회 차단
- 다른 사용자의 run 조회·승인 차단
- 승인 후 계획 또는 입력 변경 시 승인 무효화
- 승인 만료 및 replay 차단
- 같은 idempotency key의 동시 요청이 한 번만 실행됨
- Worker 종료 후 안전한 복구
- timeout 후 쓰기 요청을 무조건 재시도하지 않음
- 선행 단계 실패 시 후속 단계 차단
- 부분 성공과 수동 복구 표시
- 비밀정보·개인정보 로그 누출 검사
- 감사 이벤트의 누락·수정 방지
- SSRF, path traversal, command injection 입력 차단
- Refresher `commit` 실행에 이중 승인 유지
- `linkout`과 `manual` 단계가 완료로 오인되지 않음
- Adapter 응답과 receipt를 이용한 reconciliation

## 16. 완료 기준

다음 조건을 모두 만족하기 전에는 실제 기관 Adapter를 활성화하지 않는다.

- Prometheus와 executor의 신뢰 경계가 HTTP 계약으로 분리되어 있다.
- 임의 URL·메서드·코드를 실행 계획으로 전달할 수 없다.
- 인증된 사용자와 권한 정책 없이는 실행·승인·조회할 수 없다.
- 승인이 계획 hash와 입력 요약에 결속되고 만료·재사용이 차단된다.
- 중복 요청과 process crash에서 동일 작업이 재제출되지 않는다.
- 결과 불명 상태와 부분 성공을 표현하고 복구할 수 있다.
- 모든 상태 변경이 감사 이벤트와 함께 transaction으로 기록된다.
- secret과 개인정보가 계획, 응답, 오류, 로그에 노출되지 않는다.
- Dummy Adapter와 Refresher Adapter의 필수 테스트가 통과한다.
- 실제 실행 기능은 명시적인 feature flag로만 활성화된다.

## 17. 최종 권고

행정서비스실행기의 방향은 유효하고 아카이브의 기본 개념도 유지할 가치가 있다. 그러나 현행화는 아카이브 복원이나 Prometheus에 `/execute` endpoint 하나를 추가하는 작업이 아니다.

가장 안전한 첫 범위는 다음과 같다.

> Dummy Adapter로 실행 통제 계층을 완성한 뒤, 이미 이중 확인 구조가 있는 Refresher 하나만 실제 Adapter로 등록한다. Prometheus 연동은 실행 요청 생성까지만 허용한다.

이 범위를 통과한 다음에만 기관별 Adapter를 하나씩 검토·추가한다.
