---
name: run-dashboard
description: apps/dashboard(React Flow 논증 보드 · API 워크플로)를 띄우고 브라우저로 조작·스크린샷한다. 대시보드 변경이 실제 화면에서 도는지 확인할 때 쓴다.
---

# 대시보드 실행·조작

Vite dev 서버 + Playwright다. 이 저장소에는 함정이 둘 있어 기본 절차가 그대로
먹지 않는다. 아래 두 가지만 지키면 나머지는 평범하다.

## 함정 1 — `127.0.0.1`은 거부된다

Vite는 `localhost`에만 바인딩하고, Windows에서 그것은 `::1`(IPv6)로 먼저 풀린다.
`http://127.0.0.1:5173/`은 `ERR_CONNECTION_REFUSED`가 난다.

**항상 `http://localhost:5173/`을 쓴다.**

## 함정 2 — Playwright는 refresher venv에만 있다

`apps/dashboard/node_modules`에 Playwright도 chromium-cli도 없다. 새로 설치하지
말고 refresher의 것을 쓴다. chromium도 거기 이미 깔려 있다.

```
C:\project\services\refresher\venv\Scripts\python.exe
```

## 절차

1. dev 서버를 백그라운드로 띄운다.

   ```bash
   cd /c/project/apps/dashboard && npm run dev
   ```

   `VITE ... ready` 와 `Local: http://localhost:5173/` 이 뜨면 준비된 것이다.

2. 조작 스크립트를 스크래치패드에 쓰고 refresher venv로 돌린다.

   ```powershell
   cd C:\project\services\refresher
   .\venv\Scripts\python.exe <스크립트> <스크린샷경로>
   ```

3. 끝나면 서버를 내린다.

   ```powershell
   Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue |
     Select-Object -ExpandProperty OwningProcess -Unique |
     ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
   ```

## 화면 구조

`Root.jsx`의 기본 모드는 `argument`다. 즉 **첫 화면이 논증 보드**다.
API 워크플로는 상단 `API 워크플로` 탭에 있다.

논증 보드 초기 상태는 빈 노드 셋(`p-0` 전제, `c-0` 주장, `i-0` 해석)에 관계
없음이다. 주장에 지지가 없으므로 `근거 없음` 위반이 처음부터 하나 떠 있다.

## React Flow 조작

노드는 `data-id`로 잡는다. 툴바 버튼으로 추가한 노드의 id는 생성 순서에 따라
달라지므로(엣지도 같은 카운터를 쓴다) **추측하지 말고 추가 전후의 id 집합을
비교해서 알아낸다.**

```python
def node_ids(page):
    return set(page.locator(".react-flow__node").evaluate_all(
        "list => list.map(n => n.getAttribute('data-id'))"
    ))

before = node_ids(page)
page.get_by_role("button", name="▣ 전제").click()
page.wait_for_timeout(300)
new_id = (node_ids(page) - before).pop()
```

새 노드는 화면 밖에 놓일 수 있다. `fitView`는 마운트 때만 돌므로 노드를 추가한
뒤에는 컨트롤 버튼을 눌러 다시 맞춘다.

```python
page.locator(".react-flow__controls-fitview").click()
```

연결은 핸들에서 핸들로 끄는 포인터 드래그로만 된다. `click`으로는 안 된다.

```python
def connect(page, source_id, target_id):
    a = page.locator(f'.react-flow__node[data-id="{source_id}"] .react-flow__handle.source').bounding_box()
    b = page.locator(f'.react-flow__node[data-id="{target_id}"] .react-flow__handle.target').bounding_box()
    page.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
    page.mouse.down()
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=20)
    page.mouse.up()
    page.wait_for_timeout(150)
```

맺을 관계는 툴바에서 먼저 고른다(`지지`가 기본, `반박` 버튼은
`get_by_role("button", name="반박", exact=True)`). 해석 노드로 가는 연결만은
관계 종류와 무관하게 `입력`으로 처리된다.

텍스트는 노드 안 `textarea`에 넣는다.

```python
box = page.locator(f'.react-flow__node[data-id="{node_id}"] textarea')
box.click()
box.fill("...")
```

## 결과 확인

판정은 오른쪽 `aside`에 있다. 화면만 보지 말고 값을 찍어 확인한다.

```python
print(page.locator("aside").inner_text())
```

`형식 판정`(성립·논파됨·미판정 수)과 `위반 사항`이 여기 나온다. 노드에 붙는
위반 배지는 `순환논증`·`근거 없음`·`미해소 충돌`·`끊긴 관계` 넷이다.

## Ollama

`해석 생성` 버튼은 `/ollama`(→ `localhost:11434`)로 나간다. Ollama는 저장소 밖
런타임이라 없으면 그 버튼만 실패한다. 나머지 화면은 그대로 동작하므로, 판정
계층을 확인하는 데는 Ollama가 필요 없다.
