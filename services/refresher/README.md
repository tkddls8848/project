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
cd C:\project\services\refresher
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
창에서 직접 수행하며 세션은 `nara_storage/refresher/storage_state.json`에 저장된다.
로그인 자동 감지가 되지 않으면 `main.py login --manual`을 사용한다.

첫 실제 실행은 `--limit 1`로 확인한다. 포털이 `fn_detail`, 목록 컨테이너 또는 버튼
문구를 바꾸면 0건/실패로 끝나며 현재 HTML에 맞춰 파서를 갱신해야 한다.

## 테스트

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

목록 fixture는 2026-08-08 실제 캡처에서 계정 식별값만 치환한 것이다.
