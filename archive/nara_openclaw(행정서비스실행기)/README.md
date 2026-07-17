# Nara OpenClaw

Nara OpenClaw is the administrative execution service. It does not compose API documents by itself. It receives an `ExecutionPlan` from `nara_combiner(API문서조합기)` or another planner, checks whether the plan can be executed, requires user approval, runs the proper execution adapter, and stores an audit record.

The current implementation uses a dummy government executor for local testing. No real government submission is performed yet. The adapter boundary is in place so a real Government24 or agency connector can replace the dummy executor later.

## Responsibilities

- `POST /execute/dry-run`: validate a plan before execution
- `POST /execute`: execute only after explicit approval
- `GET /runs/{run_id}`: load execution and audit results
- `GET /demo/plan`: return a test execution plan

Out of scope:

- API document composition
- LLM prompt generation
- automatic submission without approval
- storing raw sensitive personal data

## Run

```powershell
cd "D:\project\nara_openclaw(행정서비스실행기)"
pip install -r requirements.txt
python .\app\main.py
```

Server:

```text
http://127.0.0.1:8002
```

## Demo Flow

1. Load the demo plan.

```powershell
curl.exe http://127.0.0.1:8002/demo/plan
```

2. Send a dry-run request with the demo plan and user inputs.

```json
{
  "plan": {
    "plan_id": "demo-parent-medical-transport-001",
    "goal": "부모님 병원 이동 지원, 교통비 감면, 복지 지원 신청 준비",
    "source": "nara_combiner",
    "steps": []
  },
  "user_inputs": {
    "applicant_name": "홍길동",
    "birth_date": "1940-01-01",
    "region": "서울특별시 종로구",
    "income_type": "기초연금",
    "identity_token": "dummy-identity-token"
  },
  "approval": {
    "approved": false,
    "approver": "tester"
  }
}
```

3. Execute with approval.

```json
{
  "approval": {
    "approved": true,
    "approver": "tester",
    "approval_token": "dummy-approval-token"
  }
}
```

Execution creates a JSON audit file under `runs/`.

## Execution Modes

| mode | behavior |
| --- | --- |
| `api` | dummy government API submission with masked payload and fake receipt ID |
| `linkout` | prepares a Government24 or agency link for user handoff |
| `manual` | returns a checklist for steps that cannot be automated |

## Approval Gate

`POST /execute`는 다음을 모두 통과해야 실행된다. 차단된 요청도 감사 기록을 남긴다.

| 조건 | 실패 시 | `status_reason` |
| --- | --- | --- |
| dry-run 통과 (필수 입력·target_url 충족) | `400` | `dry_run_blocked` |
| 승인 필요 계획에 `approval.approved=true` | `403` | `approval_missing` |
| 승인 필요 계획에 승인자(`approver`) 지정 | `403` | `approver_missing` |

모든 `RunRecord`는 `executor_mode` 필드를 갖는다. `"dummy"`는 실제 기관 제출이
아니라 모사 실행이며, api 단계의 `receipt_id`는 `DUMMY-GOV-` prefix를 가진다.

## Masking Contract

run 기록과 응답의 `user_inputs`, `request_preview`, `submitted_payload`는
`app/executor.py`의 `mask_inputs`로 마스킹된다.

- 대상 키(정확 일치, 소문자 비교): `name`, `applicant_name`, `birth_date`,
  `resident_id`, `phone`, `email`, `address`, `identity_token`, `documents`,
  `token`, `secret`, `password` 등
- 접미사 일치: `*_token`, `*_secret`, `*_password`, `*_key`
- 중첩 dict/list 내부도 재귀적으로 마스킹한다
- 이 목록은 좁히지 않는다 — 새 민감 필드는 추가만 한다

## Executor Adapter Interface

실행 어댑터는 `execute_step(step: ExecutionStep, user_inputs: dict) -> StepExecutionResult`
하나를 구현한다 (`DummyGovernmentExecutor` 참고).

실패 계약:

- 단계 실패는 예외가 아니라 `StepExecutionResult(status="failed", message=...)`로 표현한다
- 하나라도 `completed`가 아니면 run 전체 status는 `partial`
- 민감정보 원문을 `message`/`response_data`에 넣지 않는다 (마스킹 후 기록)
- 실제 기관 어댑터는 별도 권한·법률·감사 검토 없이 추가하지 않는다

## Environment

```text
OPENCLAW_RUNS_DIR=./runs
OPENCLAW_EXECUTOR_MODE=dummy
```

`OPENCLAW_EXECUTOR_MODE=dummy` is the only implemented mode. A real connector should keep the same dry-run and approval contract.

## Tests

```powershell
python -m pytest tests -v
```

테스트는 run 기록을 임시 디렉터리로 격리하며(`tests/conftest.py`) 작업 트리의
`runs/`에 파일을 남기지 않는다. `runs/*.json`은 Git에서 제외된다.
