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
