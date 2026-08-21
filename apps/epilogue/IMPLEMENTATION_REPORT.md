# 행정서비스실행기 1·2단계 구현 보고

## 1. 구현 API와 실제 경로

| 메서드 | 실제 경로 | 구현 |
| --- | --- | --- |
| `POST` | `/execution-plans/validate` | 계획 hash·만료·의존 그래프, OperationSpec, 입력 스키마와 영향 범위를 검증하고 계획을 불변 저장한다. |
| `POST` | `/execution-runs` | 필수 `Idempotency-Key`와 검증 계획 참조로 승인 대기 run을 생성한다. Adapter는 호출하지 않는다. |
| `GET` | `/execution-runs/{run_id}` | 인증된 소유 principal에게 상태·단계·값 없는 입력 요약을 반환한다. |
| `GET` | `/execution-runs/{run_id}/events` | append-only 감사·진행 이벤트를 sequence 순서로 반환한다. |
| `POST` | `/execution-runs/{run_id}/approvals` | 세션 principal을 비밀번호로 재인증하고 challenge를 계획/input hash에 결속한다. |
| `POST` | `/execution-runs/{run_id}/start` | 유효한 일회용 승인을 소비해 queued로 전환한다. Worker가 별도 처리한다. |
| `POST` | `/execution-runs/{run_id}/cancel` | 실행 전 즉시 취소하거나 running Worker에 협력적 취소 요청을 남긴다. |
| `POST` | `/execution-runs/{run_id}/reconcile` | 외부 요청 없이 저장된 Dummy Adapter receipt의 allowlist 결과로 `outcome_unknown`을 조정한다. |
| `POST` | `/auth/sessions` | 로컬 사용자 자격정보로 서버 저장 opaque 세션을 발급한다. |
| `POST` | `/execution-runs/{run_id}/approval-challenges` | 만료·분실된 challenge를 재발급하고 이전 challenge를 무효화한다. |

계획 9절의 8개 실행 API는 경로 그대로 구현했다. `/auth/sessions`는 승인자 ID를 요청 본문에서 받지 않고 서버 세션 principal로 결정하기 위해, `/approval-challenges`는 만료·분실된 일회용 challenge의 안전한 복구를 위해 추가했다. `/`, `/health`, FastAPI 기본 OpenAPI 문서 경로도 있고 CORS middleware는 없다.

## 2. SQLite 스키마

기본 경로는 `.nara-root`를 `nara_common.paths.find_project_root()`로 찾은 뒤의 `api_storage/epilogue/epilogue.sqlite3`이며 WAL을 사용한다.

| 테이블 | 핵심 제약 |
| --- | --- |
| `execution_plans` | `(plan_id, plan_version)` PK, `content_hash` UNIQUE, UPDATE/DELETE 금지 trigger |
| `execution_runs` | `run_id` PK, plan FK, 소유 principal, plan/input hash, 상태·lease·취소·수동 복구 필드 |
| `step_runs` | `(run_id, step_id)` UNIQUE, 단계 idempotency key UNIQUE, timeout·attempt·결과 |
| `approvals` | challenge hash UNIQUE, run FK, principal·plan hash·input hash·만료·소비·무효화 |
| `audit_events` | `(run_id, sequence)` UNIQUE, UPDATE/DELETE 금지 trigger |
| `idempotency_keys` | `(principal_id, plan_hash, idempotency_key)` PK, request hash와 run FK |
| `adapter_receipts` | 단계 idempotency key UNIQUE, in-flight/최종 상태와 allowlist receipt |
| `auth_sessions` | session token hash PK, principal·만료·취소 시각 |

run/step 상태 UPDATE는 연결별 audit context가 없으면 DB trigger가 거부한다. 서비스의 상태 전이 메서드는 `BEGIN IMMEDIATE` 안에서 상태 UPDATE와 감사 INSERT를 함께 수행하며, 허용 전이는 `domain/state_machine.py`가 검사한다.

## 3. Worker lease·복구

API는 run을 queued로만 만들고 `python -m worker.runner` 별도 프로세스가 처리한다. Worker는 `BEGIN IMMEDIATE`로 queued run 또는 `lease_expires_at`이 지난 running run을 하나만 획득하고, 실행 중 lease를 주기적으로 갱신한다. 획득 직후 crash면 새 Worker가 pending 단계를 실행하고, Adapter 호출 marker 뒤 crash면 같은 쓰기 작업을 재제출하지 않고 `outcome_unknown`과 수동 조정 절차로 전환한다.

이를 증명하는 테스트는 `test_expired_worker_lease_is_recovered_without_duplicate_execution`, `test_crash_after_attempt_marker_becomes_unknown_without_resubmission`, `test_same_idempotency_key_concurrently_creates_and_executes_once`다. 쓰기 timeout 무재시도는 `test_timeout_write_is_not_retried`, 명시적으로 안전한 재시도는 `test_registered_safe_retry_reuses_step_key_and_succeeds`가 검증한다.

## 4. 테스트 결과

지정된 전용 venv 명령 결과는 **29 passed, 0 failed**다.

```text
.\venv\Scripts\python.exe -m pytest -q tests --basetemp C:\tmp\nara-epilogue -p no:cacheprovider
.............................                                            [100%]
29 passed in 14.72s
```

추가로 `compileall`이 오류 없이 완료됐다.

## 5. 계획 문서와 다르게 구현한 점

- 계획 8절은 같은 프로세스 background loop와 별도 프로세스 중 선택을 열어 두었고, crash 경계를 명확히 하기 위해 별도 Worker CLI를 선택했다.
- 계획 9절 외에 로컬 세션 발급 API와 approval challenge 재발급 API를 추가했다. 둘 다 인증·승인 결속을 완성하는 제어 API이며 실행을 합치거나 외부 호출을 만들지 않는다.
- `/reconcile`은 현재 Dummy receipt를 로컬에서 읽으므로 API 처리 안에서 상태 조정한다. 외부 기관 조회가 필요한 reconciliation은 Worker 작업이어야 하지만 3단계 이후 범위다.
- `manual`/`linkout` 서버 소유 경로는 카탈로그에만 있고 네트워크 호출하지 않으며 결과는 `awaiting_user`다.
- Adapter call의 in-flight marker만 남은 crash는 호출 전 crash일 수도 있지만 중복 쓰기보다 보수적인 `outcome_unknown`을 선택했다.

## 6. 1·2단계 범위에서 하지 못한 것

지시된 1·2단계 필수 항목과 해당 필수 테스트는 모두 구현했다. 다만 범위 내 구현의 의도적인 한계로 running 단계 취소는 이미 시작된 쓰기를 강제 종료하지 않고 안전한 단계 경계에서 협력적으로 처리하며, `awaiting_user` 사용자가 완료 증빙을 제출해 별도 완료 상태로 옮기는 API는 계획 9절에 없어 구현하지 않았다. 실제 secret store와 개인정보 암호화는 Dummy OperationSpec이 비밀·개인정보 필드를 전부 거부하므로 사용하지 않았고, 실제 Adapter를 추가할 때 별도 위협 모델과 함께 구현해야 한다.

## 7. 계획 16절 중 아직 만족하지 못한 완료 기준

- Prometheus와 executor의 실제 HTTP 연동은 4단계 범위이므로 아직 없다. executor 자체는 HTTP 경계로 독립 실행된다.
- Refresher Adapter와 그 필수 테스트는 3단계이자 명시적 금지 범위이므로 없다. Dummy Adapter 테스트만 통과한다.
- 실제 실행 기능 feature flag는 활성화할 실제 Adapter 코드 자체가 없어 아직 동작 검증할 대상이 없다. 실제 Adapter를 추가하기 전에 기본 비활성 flag를 반드시 추가해야 한다.
- 실제 기관 receipt/신청 목록 조회 reconciliation은 없다. 현재는 Dummy Adapter receipt를 사용한 조정만 검증한다.

그 밖의 임의 URL·메서드·코드 차단, 세션 principal 권한, 승인 hash 결속·만료·replay 차단, 멱등·crash 무재제출, 결과 불명·부분 성공 표현, 상태/감사 transaction, 민감값 비반사는 현재 Dummy 범위에서 충족한다.
