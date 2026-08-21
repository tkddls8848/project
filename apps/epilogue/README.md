# 행정서비스실행기

검증된 `ExecutionPlan`을 dry-run, 재인증 승인, 멱등 queue, lease Worker, 감사 기록의 순서로 통제하는 로컬 서비스다. 현재는 네트워크 요청을 전혀 하지 않는 Dummy Adapter만 제공하며 실제 행정 신청·제출이나 외부 시스템 변경을 수행하지 않는다.

Prometheus를 포함한 클라이언트는 URL, HTTP 메서드, Python 코드, 셸 명령, import 경로 또는 승인자 ID를 계획에 넣을 수 없다. 실행 대상과 메서드는 서버 소유 [OperationSpec 카탈로그](config/operations.json)에서만 결정되고, 승인자는 서버가 발급해 SQLite에 보관한 로컬 세션의 principal로 결정된다.

## 실행

Windows PowerShell에서 서비스별 가상환경을 만든다.

```powershell
cd C:\project\apps\epilogue
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:NARA_EPILOGUE_PASSWORD = "로컬에서 사용할 충분히 긴 비밀번호"
.\venv\Scripts\python.exe run.py
```

API는 CORS를 열지 않고 `127.0.0.1:8002`에만 바인딩한다. `POST /auth/sessions`에서 사용자명 `local`과 위 비밀번호로 opaque Bearer 세션을 발급받는다. OAuth, JWT, 외부 IdP는 사용하지 않는다.

API 프로세스는 Adapter를 호출하지 않는다. 별도 PowerShell에서 Worker를 실행해야 queued run이 처리된다.

```powershell
cd C:\project\apps\epilogue
.\venv\Scripts\python.exe -m worker.runner --worker-id local-worker
```

한 건만 처리하고 종료하려면 `--once`를 추가한다. Worker는 SQLite에서 queue 또는 만료된 lease를 원자적으로 획득하고, 긴 단계 중에는 lease를 갱신한다.

## API

| 메서드 | 경로 | 동작 |
| --- | --- | --- |
| `POST` | `/auth/sessions` | 로컬 자격정보를 확인하고 서버 저장 세션을 발급한다. 계획 9절에는 없지만 인증 principal을 요청 본문과 분리하기 위해 추가했다. |
| `POST` | `/execution-plans/validate` | 계획 hash, 만료, 의존 그래프, 등록 작업, 입력 스키마를 검증하고 값 없는 영향 요약을 반환한다. |
| `POST` | `/execution-runs` | `Idempotency-Key`가 필수이며 검증된 `plan_id`/version/hash로 승인 대기 run을 만든다. |
| `GET` | `/execution-runs/{id}` | 소유 principal의 상태와 단계 결과만 조회한다. 원본 입력은 반환하지 않는다. |
| `GET` | `/execution-runs/{id}/events` | 순서가 고정된 append-only 감사·진행 이벤트를 조회한다. |
| `POST` | `/execution-runs/{id}/approvals` | 세션 principal을 비밀번호로 재인증하고 일회용 challenge를 승인한다. 승인자 필드는 받지 않는다. |
| `POST` | `/execution-runs/{id}/approval-challenges` | 만료·분실된 challenge를 소유 principal에게 다시 발급하고 이전 challenge를 무효화한다. 계획 9절의 승인 replay 차단 후 복구 경로를 완성하기 위해 추가했다. |
| `POST` | `/execution-runs/{id}/start` | 계획 hash와 입력 hash에 결속된 미사용 승인을 소비하고 queue에 넣는다. Adapter 호출은 하지 않는다. |
| `POST` | `/execution-runs/{id}/cancel` | 실행 전에는 즉시 취소하고, 실행 중이면 Worker가 안전한 단계 경계에서 볼 취소 요청을 남긴다. |
| `POST` | `/execution-runs/{id}/reconcile` | `outcome_unknown` run을 저장된 allowlist 영수증으로 조정한다. 현재 Dummy 영수증만 읽으며 외부 요청은 없다. |

승인 후 계획 hash나 입력이 달라졌거나 승인이 만료·소비된 경우 `/start`는 기존 승인을 무효화하고 새 일회용 challenge를 반환한다. 동일 principal, 동일 계획 hash, 동일 `Idempotency-Key`의 동시 요청은 하나의 run만 만들며 다른 본문에 같은 key를 재사용하면 거부한다.

상태 전이는 `domain/state_machine.py`가 강제한다. 주 실행 흐름은 `draft → validating → awaiting_approval → approved → queued → running`이며 마지막 상태는 `succeeded`, `partially_succeeded`, `failed`, `outcome_unknown`, `awaiting_user`, `cancelled` 중 하나다. `manual`과 `linkout`은 항상 `awaiting_user`이고 사용자 완료로 취급하지 않는다.

## OperationSpec 등록

카탈로그는 서버가 소유한 `config/operations.json`이다. 클라이언트가 이를 수정하는 API는 없다. 변경은 코드 리뷰 후 파일을 수정하고 API와 Worker를 모두 재시작해 적용한다.

각 항목은 최소한 다음을 선언한다.

- 고정 `operation_id`와 version, 검토된 Adapter 이름
- 기관, 실행 mode, 서버 소유 HTTP 메서드·허용 host·path
- 입력 필드 타입·필수 여부·길이·정규식과 결과 allowlist
- 읽기/쓰기, 위험 등급, 권한, 재인증 승인 정책
- dry-run·멱등성·안전 재시도 여부와 최대 시도 횟수
- 성공 확인 방법, 수동 복구 절차, Dummy 동작

현재 모델은 Adapter 이름을 `dummy`로만 제한한다. 실제 기관 Adapter는 계획 16절의 모든 완료 기준을 만족하기 전까지 등록하거나 활성화하지 않는다. 특히 Refresher Adapter, Prometheus 연동, 기관 HTTP 호출은 이 단계에 포함되지 않는다.

## 저장과 복구

기본 DB는 저장소 `.nara-root`를 `nara_common.paths.find_project_root()`로 찾은 뒤 `api_storage/epilogue/epilogue.sqlite3`에 만든다. SQLite WAL과 표준 라이브러리 `sqlite3`만 사용하며 ORM은 없다.

| 테이블 | 핵심 제약 |
| --- | --- |
| `execution_plans` | `(plan_id, plan_version)` 기본 키, content hash 고유, 검증 계획 불변 |
| `execution_runs` | 소유 principal, plan/input hash, 상태, lease owner/만료, 취소·수동 복구 표시 |
| `step_runs` | `(run_id, step_id)`와 단계 idempotency key 고유 |
| `approvals` | challenge hash 고유, plan/input hash·principal·만료·소비·무효화 결속 |
| `audit_events` | `(run_id, sequence)` 고유, DB trigger로 UPDATE/DELETE 금지 |
| `idempotency_keys` | `(principal, plan_hash, key)` 기본 키와 요청 hash 결속 |
| `adapter_receipts` | 단계 idempotency key당 하나의 allowlist 영수증 |
| `auth_sessions` | opaque token의 hash만 저장하고 principal·만료에 결속 |

run/step 상태 변경과 대응 감사 이벤트는 하나의 `BEGIN IMMEDIATE` transaction 안에서 기록된다. DB trigger는 감사 context를 우회한 상태 UPDATE와 감사 이벤트 UPDATE/DELETE를 차단한다. Worker가 lease 획득 직후 죽으면 만료 후 다른 Worker가 pending 단계를 이어가고, Adapter 호출 marker 이후 죽으면 재제출하지 않고 `outcome_unknown`으로 전환한다. 쓰기 timeout도 자동 재시도하지 않으며 영수증 reconciliation 또는 수동 확인이 먼저다.

현재 Dummy 입력은 비밀정보·개인정보 필드를 허용하지 않는다. 요청 검증 오류는 거부된 값을 반사하지 않고, 응답·감사 이벤트·Adapter 영수증은 구조화된 allowlist만 사용한다. 실제 secret 저장소나 개인정보 암호화가 필요한 Adapter는 아직 지원하지 않는다.

## 테스트

```powershell
cd C:\project\apps\epilogue
.\venv\Scripts\python.exe -m pytest -q tests --basetemp C:\tmp\nara-epilogue -p no:cacheprovider
```

테스트는 미등록 작업과 주입 입력 차단, 인증·소유권, 승인 결속·만료·replay, 동시 멱등성, lease crash recovery, timeout 무재시도, 의존 실패, 부분 성공, 민감값 비반사, append-only 감사, `manual`/`linkout`, 취소, 안전 재시도, receipt reconciliation을 검증한다.
