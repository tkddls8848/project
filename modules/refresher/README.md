# Nara Refresher

data.go.kr 개발계정의 OpenAPI 활용신청 연장을 반복 실행하는 CLI다. 현재 포털에서
확인한 흐름만 지원한다.

```text
활용신청 목록 -> fn_detail(...) -> 연장 신청하기 -> confirm/alert -> 목록
```

신규 활용신청이나 다른 계정 작업은 수행하지 않는다. `extend`는 기본 dry-run이며
`--commit`을 명시해야 실제 버튼을 누른다.

## 설치

```powershell
cd C:\project\modules\refresher
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m playwright install chromium
Copy-Item .env.example .env
```

## 사용

```powershell
.\venv\Scripts\python.exe main.py login
.\venv\Scripts\python.exe main.py list
.\venv\Scripts\python.exe main.py extend
.\venv\Scripts\python.exe main.py extend --commit --limit 1
```

인자 없이 실행하거나 `-i`를 주면 커맨드와 옵션을 묻는다. 로그인은 열린 Chromium
창에서 직접 수행하며 세션은 `api_storage/refresher/storage_state.json`에 저장된다.
로그인 자동 감지가 되지 않으면 `main.py login --manual`을 사용한다.

첫 실제 실행은 `--limit 1`로 확인한다. 포털이 `fn_detail`, 목록 컨테이너 또는 버튼
문구를 바꾸면 0건/실패로 끝나며 현재 HTML에 맞춰 파서를 갱신해야 한다.

## 브라우저 제어 UI (:8005)

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8005
```

`http://127.0.0.1:8005`에서 보유 API 목록을 표로 보고 login·extend를 실행한다.
백엔드는 위 CLI를 그대로 서브프로세스로 돌리고 출력을 SSE로 흘린다. 브라우저에서
누른 실행과 터미널에서 친 명령이 같은 코드 경로를 탄다.

- 목록 표시만 `fetch_account_rows`를 직접 호출한다. 화면에 표로 그리려면 구조화된
  값이 필요한데 CLI는 사람이 읽는 문장을 찍기 때문이다. 읽기 전용이다.
- **실제 제출은 두 관문을 모두 통과해야 한다.** UI에서 `연장`을 입력해야 버튼이
  켜지고, API는 `commit`과 별개로 `confirm_commit`을 요구한다. dry-run 요청을 그대로
  다시 보내는 것만으로는 실제 제출이 되지 않는다.
- `login --manual`은 터미널 Enter를 기다린다. 브라우저에는 그 터미널이 없으므로
  stdin을 열어두고 UI의 "로그인 완료" 버튼이 `POST /runs/{id}/stdin`으로 잇는다.
- 로그인 창(Chromium)은 **서버가 도는 컴퓨터**에 열린다. 원격에서는 쓸 수 없다.
- CORS를 열지 않는다. 이 서비스는 실제 제출을 일으킬 수 있어 다른 출처의 페이지가
  로컬호스트로 요청을 보내게 두면 안 된다. `127.0.0.1`에만 바인딩한다.
- 한 번에 하나의 실행만 허용한다.

## 테스트

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

목록 fixture는 2026-08-08 실제 캡처에서 계정 식별값만 치환한 것이다.
