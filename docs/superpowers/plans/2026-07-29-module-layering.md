# 모듈 계층화 — services/ · apps/ 디렉터리 재배치 구현 계획

> **For agentic workers:** 체크박스(`- [ ]`) 단위로 진행한다. Phase 1을 끝내기 전에는
> 어떤 디렉터리도 옮기지 않는다. Phase 경계마다 전체 테스트가 초록이어야 다음으로 넘어간다.

**작성일:** 2026-07-29
**Goal:** 생산층(crawler·search·combiner)과 소비층(workbench·dashboard·hermes_poc)을
`services/`·`apps/`로 분리하고, 한글 괄호 디렉터리명을 ASCII로 정리한다.

**핵심 제약(이 계획이 존재하는 이유):** 지금의 평평한 구조는 **기능적으로 지지하중을 받고 있다.**
4개 모듈이 "레포 루트 = 내 부모 디렉터리"를 코드에 하드코딩하고 있어, 디렉터리를 한 단계만
내려도 공유 데이터 루트(`nara_storage`) 해석이 조용히 깨진다. 따라서 **이동보다 결합 제거가 먼저다.**

**Tech Stack:** Python 3.13 (pytest), Node/Vite (dashboard), PowerShell 5.1, git

---

## 0. 현재 결합 지도 (조사 결과)

### 0.1 "루트 = 내 부모" 하드코딩 — 4곳

| 파일 | 라인 | 현재 코드 |
| --- | --- | --- |
| `nara_search(API문서검색)/backend/core/config.py` | 29 | `BASE_DIR.parent / "nara_storage" / "openapi_new"` |
| `nara_combiner(API문서조합기)/app/config.py` | 11 | `BASE_DIR.parent / "nara_storage" / "openapi_new"` |
| `nara_crawler(API문서크롤러)/managers/crawl_run_manager.py` | 21 | `self.base_dir.parent / "nara_storage"` |
| `nara_hermes_poc/app/config.py` | 11 | `BASE_DIR.parent / "nara_storage"` |

### 0.2 형제 모듈을 한글 이름 문자열로 탐색 — 2곳

| 파일 | 라인 | 현재 코드 |
| --- | --- | --- |
| `nara_hermes_poc/run.py` | 23, 50–51 | `PROJECT_DIR = BASE_DIR.parent` → `PROJECT_DIR / "nara_search(API문서검색)"`, `.../ "nara_combiner(API문서조합기)"` |
| `nara_workbench(API통합워크벤치)/run.py` | 16, 36, 45 | 동일 패턴 |

### 0.3 이동에 **영향 없는** 것 (확인 완료)

- **HTTP 결합은 전부 안전하다.** workbench 게이트웨이(`main.py:19-20`)와 dashboard vite 프록시
  (`vite.config.js:14,19`)는 `127.0.0.1:8000/8003`만 참조하므로 경로 무관.
- **`.gitignore`**는 `**/`·`__pycache__/` 등 비앵커 패턴 위주이고, 앵커된 항목
  (`nara_storage/`, 169–173행의 archive 대상)은 루트 기준이라 그대로 유효하다.
- **`.claude/settings.local.json`**은 `./venv/...` 상대경로만 쓴다.
- **`start-all.ps1`은 이 머신에 존재하지 않는다** (`Test-Path` → False). CLAUDE.md가
  참조하지만 git에 없고 로컬에도 없으므로 이 계획에서 갱신 대상이 아니다.
- workbench 테스트(`tests/test_app.py`), hermes 테스트 전반은 경로 단정문이 없다
  (`tests/conftest.py:6`의 `parents[1]`은 모듈 내부 기준이라 깊이 무관).

### 0.4 이동으로 **깨지는** 부수 자산

- **venv 5개가 절대경로를 내장하고 있다.** 예: `nara_search(API문서검색)/venv/pyvenv.cfg`의
  `command = ... -m venv C:\project\nara_search(API문서검색)\venv`. `Scripts/*.exe` 셔뱅도 마찬가지다.
  **디렉터리를 옮기면 venv는 전부 못 쓴다 — 재생성이 필수다.** (combiner, crawler, hermes_poc, search, workbench)
- dashboard에는 `node_modules/`가 아예 없다 → `npm install`만 하면 된다.

---

## 1. 목표 구조

```
C:\project\
├─ .nara-root                 ← 신규: 저장소 루트 마커 (빈 파일, 추적됨)
├─ services/                  ← 데이터·API 생산층
│   ├─ crawler/               (← nara_crawler(API문서크롤러))
│   ├─ search/                (← nara_search(API문서검색))
│   └─ combiner/              (← nara_combiner(API문서조합기))
├─ apps/                      ← 사용자 접점
│   ├─ workbench/             (← nara_workbench(API통합워크벤치))
│   ├─ dashboard/             (← nara_dashboard(API관계대시보드))
│   ├─ hermes_poc/            (← nara_hermes_poc)
│   └─ gazetta/               (← nara_gazetta — 파이프라인 비의존 정적 프로토타입)
├─ nara_storage/              (gitignore, 무변경)
├─ korea100/                  (별개 제품, 무변경)
├─ archive/                   (보류, 무변경)
└─ docs/
```

**루트에서 사라지는 것:** 위 6개 + `nara_gazetta/`, 그리고 미추적 잔여물
`nara_gov24_link_resolver(정부24서비스링크매핑)/` (Task 13에서 삭제).
결과적으로 루트에는 `services/`·`apps/`·`nara_storage/`·`korea100/`·`archive/`·`docs/`만 남는다.

**이름 규칙:** 부모 디렉터리가 네임스페이스를 제공하므로 `nara_` 접두사를 뗀다
(`services/search`). 한글 설명은 각 README 제목과 CLAUDE.md 지도에 남긴다 — 정보는 잃지 않는다.

---

## 2. Global Constraints

- **프로젝트 간 Python/JS 모듈 직접 import 금지** (기존 제약 유지). 따라서 루트 해석기는
  공유 패키지가 아니라 **각 모듈에 복제한다.** 4~8줄이며, 이 중복은 제약에 따른 의도된 선택이다.
- **새 환경변수 추가 금지.** 기존 오버라이드(`NARA_SEARCH_APIDATA_DIR`, `NARA_DATA_DIR`,
  `NARA_STORAGE_DIR`)의 의미는 그대로 둔다.
- 절대경로 하드코딩 금지 — 예외는 `config/hermes.example.yaml`(외부 CLI 설정 예시라 절대경로 불가피).
- **git 명령은 `git mv`만 사용한다.** 커밋은 사용자가 직접 관리하므로 계획에 커밋 단계를 넣지 않는다.
- Phase 1 완료 시점에 **디렉터리는 하나도 움직이지 않은 상태**여야 한다. 이것이 이 계획의 안전장치다.
- 셸에서 한글 괄호 경로는 반드시 따옴표로 감싼다 (이동 전까지).

---

## Phase 0 — 기준선 확보

### Task 0: 이동 전 스냅샷

- [ ] **Step 1: 작업 트리 클린 확인**

```powershell
git -C C:\project status --porcelain
```

Expected: `docs/superpowers/plans/` 아래 미추적 문서 외에 변경 없음. 다른 변경이 있으면 **중단하고 보고한다.**

- [ ] **Step 2: 테스트 기준선 측정 및 기록**

각 모듈에서 실행하고 **통과 개수를 이 문서에 받아적는다.** 이후 모든 회귀 판정의 기준이다.

```powershell
cd "C:\project\nara_crawler(API문서크롤러)";   .\venv\Scripts\python.exe -m pytest tests -q
cd "C:\project\nara_search(API문서검색)";     .\venv\Scripts\python.exe -m pytest tests -q
cd "C:\project\nara_combiner(API문서조합기)"; .\venv\Scripts\python.exe -m pytest tests -q
cd "C:\project\nara_workbench(API통합워크벤치)"; .\venv\Scripts\python.exe -m pytest tests -q
cd "C:\project\nara_hermes_poc";              .\venv\Scripts\python.exe -m pytest tests -q
```

**측정 결과 (2026-07-29):** crawler **5** / search **67** / combiner **26** /
workbench **6** / hermes **40** — 합 **144**
(dashboard는 `node_modules`가 없어 `npm install` 후 `npm test` — Task 10에서 처리)

> 실측 시 발견: crawler·search·workbench venv에는 **pytest가 없었다**
> (requirements에 없고 search README가 `pip install pytest httpx`를 별도 안내한다).
> 기준선 측정을 위해 세 venv에 `pytest httpx`를 설치했다. 이 venv들은 Task 10에서
> 어차피 재생성되므로 부작용이 남지 않는다. 재생성 후에도 같은 추가 설치가 필요하다.

- [ ] **Step 3: venv 복원점 확보**

이동 후 재생성할 때 대조할 스냅샷을 스크래치패드에 남긴다 (레포에 커밋하지 않는다).

```powershell
$out = "$env:TEMP\nara_venv_freeze"
New-Item -ItemType Directory -Force $out | Out-Null
foreach ($m in @('nara_crawler(API문서크롤러)','nara_search(API문서검색)','nara_combiner(API문서조합기)','nara_workbench(API통합워크벤치)','nara_hermes_poc')) {
  & "C:\project\$m\venv\Scripts\python.exe" -m pip freeze | Out-File -Encoding utf8 "$out\$($m -replace '[^\w]','_').txt"
}
Get-ChildItem $out
```

각 모듈의 정식 의존성 선언 위치 (재생성에 사용):
`crawler/requirements.txt`, `combiner/requirements.txt`, `workbench/requirements.txt`,
`hermes_poc/requirements.txt`, **`search/backend/requirements.txt`** (search만 하위 경로).

---

## Phase 1 — 결합 제거 (디렉터리는 그대로)

이 Phase의 성공 판정: **모든 코드가 마커 기반으로 루트를 찾지만, 아직 아무것도 움직이지 않았고
전체 테스트가 기준선 그대로다.** 여기까지 초록이면 Phase 2의 이동은 기계적 작업이 된다.

### Task 1: 루트 마커 생성

**Files:** Create `C:\project\.nara-root`

- [ ] **Step 1: 마커 파일 작성**

빈 파일이 아니라 한 줄 설명을 넣어 우발적 삭제를 막는다.

```powershell
Set-Content -Encoding utf8 C:\project\.nara-root "# 이 파일의 위치가 저장소 루트다. 각 모듈이 nara_storage를 찾는 기준점 — 삭제·이동 금지."
```

- [ ] **Step 2: `.gitignore`에 걸리지 않는지 확인**

```powershell
git -C C:\project check-ignore -v .nara-root
```

Expected: 출력 없음(=무시되지 않음). 무시되면 `.gitignore`에 `!.nara-root` 예외를 추가한다.

---

### Task 2: [search] 루트 해석기 도입

**Files:**
- Modify: `nara_search(API문서검색)/backend/core/config.py:4,29`
- Modify: `nara_search(API문서검색)/tests/test_config_defaults.py`

**Interfaces:**
- Produces: `config.PROJECT_ROOT: Path` — 마커로 찾은 저장소 루트.
  `config.APIDATA_DIR` 기본값 = `PROJECT_ROOT / "nara_storage" / "openapi_new"` (env 오버라이드 의미 불변)

- [ ] **Step 1: 테스트를 새 계약으로 먼저 고친다**

`tests/test_config_defaults.py` 전체를 교체:

```python
import importlib


def test_apidata_default_points_to_shared_storage(monkeypatch):
    from backend.core import config

    monkeypatch.delenv("NARA_SEARCH_APIDATA_DIR", raising=False)
    try:
        importlib.reload(config)
        assert config.APIDATA_DIR == config.PROJECT_ROOT / "nara_storage" / "openapi_new"
    finally:
        # 다른 테스트가 모듈 상태에 의존하지 않도록 원복 reload
        importlib.reload(config)


def test_project_root_is_resolved_by_marker():
    from backend.core import config

    # 루트는 디렉터리 깊이가 아니라 .nara-root 마커로 정해진다.
    assert (config.PROJECT_ROOT / ".nara-root").is_file()


def test_find_project_root_falls_back_to_parent(tmp_path):
    from backend.core.config import find_project_root

    # 마커가 없는 트리에서는 예전 규약(모듈이 루트의 직계 자식)으로 폴백한다.
    module_dir = tmp_path / "some_module"
    module_dir.mkdir()
    assert find_project_root(module_dir) == tmp_path


def test_find_project_root_finds_marker_above_nested_module(tmp_path):
    from backend.core.config import find_project_root

    (tmp_path / ".nara-root").write_text("", encoding="utf-8")
    nested = tmp_path / "services" / "search"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path
```

- [ ] **Step 2: 실패 확인**

```powershell
cd "C:\project\nara_search(API문서검색)"
.\venv\Scripts\python.exe -m pytest tests/test_config_defaults.py -v
```

Expected: FAIL — `PROJECT_ROOT`/`find_project_root` 없음 (AttributeError / ImportError)

- [ ] **Step 3: config.py 수정**

4행 아래에 해석기를 넣고, 29행의 `BASE_DIR.parent`를 `PROJECT_ROOT`로 바꾼다.

```python
BASE_DIR = Path(__file__).resolve().parents[2]


def find_project_root(start: Path) -> Path:
    """`.nara-root` 마커를 위로 훑어 저장소 루트를 찾는다.

    디렉터리 깊이에 의존하지 않으므로 모듈을 services/ 아래로 옮겨도 같은 지점을 가리킨다.
    마커를 못 찾으면 예전 규약(모듈이 루트의 직계 자식)으로 폴백한다 — 임시 디렉터리를
    기준으로 도는 테스트가 마커 없이도 예전과 동일하게 동작하게 하기 위함이다.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".nara-root").is_file():
            return candidate
    return start.parent


PROJECT_ROOT = find_project_root(BASE_DIR)
```

29행:

```python
APIDATA_DIR = _env_path("NARA_SEARCH_APIDATA_DIR", PROJECT_ROOT / "nara_storage" / "openapi_new")
```

`STORAGE_DIR`·`LOCAL_MODEL_PATH`·`DATA_DIR`(32·38·45행)은 **모듈 내부 경로이므로 손대지 않는다.**

- [ ] **Step 4: 전체 스위트 확인**

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

Expected: 기준선 + 3 (신규 테스트 3개). **이동 전이므로 `PROJECT_ROOT`는 여전히 `C:\project`다.**

---

### Task 3: [combiner] 루트 해석기 도입

**Files:**
- Modify: `nara_combiner(API문서조합기)/app/config.py:8,11`
- Modify: `nara_combiner(API문서조합기)/tests/test_config_defaults.py`

- [ ] **Step 1: 테스트 교체** — Task 2 Step 1과 동일 구조. `from app import config`,
  단정문은 `config.NARA_DATA_DIR == config.PROJECT_ROOT / "nara_storage" / "openapi_new"`,
  env는 `NARA_DATA_DIR`. `find_project_root` 폴백·마커 테스트 2개도 동일하게 추가한다.

  주의: `config.py`가 `load_dotenv()`를 호출한다. 레포에 `.env`가 있고 `NARA_DATA_DIR`를
  정의하면 reload 시 재주입되어 실패할 수 있다. `.env` 존재 여부를 먼저 확인하고,
  있으면 `monkeypatch`로 `os.environ`을 정리한 뒤 reload한다.

- [ ] **Step 2: 실패 확인**

```powershell
cd "C:\project\nara_combiner(API문서조합기)"
.\venv\Scripts\python.exe -m pytest tests/test_config_defaults.py -v
```

- [ ] **Step 3: config.py 수정** — 8행 아래에 Task 2와 **동일한** `find_project_root` 정의와
  `PROJECT_ROOT = find_project_root(BASE_DIR)`를 넣고, 11행을 교체:

```python
NARA_DATA_DIR: Path = Path(os.getenv("NARA_DATA_DIR", str(PROJECT_ROOT / "nara_storage" / "openapi_new")))
```

- [ ] **Step 4: 전체 스위트 확인** — Expected: 기준선 + 3

---

### Task 4: [crawler] 루트 해석기 도입

**Files:**
- Modify: `nara_crawler(API문서크롤러)/managers/crawl_run_manager.py:17-22`
- Modify: `nara_crawler(API문서크롤러)/tests/test_storage_paths.py` (케이스 추가)

**Interfaces:**
- `CrawlRunManager(base_dir).storage_dir` — 마커가 있으면 `찾은 루트 / "nara_storage"`,
  없으면 기존과 동일한 `base_dir.parent / "nara_storage"`

- [ ] **Step 1: 테스트 추가** (기존 5개는 **수정하지 않는다** — 폴백 덕분에 그대로 통과한다)

```python
def test_storage_root_follows_marker_when_module_is_nested(tmp_path):
    from managers.crawl_run_manager import CrawlRunManager

    (tmp_path / ".nara-root").write_text("", encoding="utf-8")
    nested = tmp_path / "services" / "crawler"
    nested.mkdir(parents=True)
    manager = CrawlRunManager(nested)
    # 두 단계 깊어져도 데이터 루트는 마커 위치를 따라간다
    assert manager.storage_dir == tmp_path / "nara_storage"
    assert manager.manifests_dir == tmp_path / "nara_storage" / "manifests"
```

- [ ] **Step 2: 실패 확인**

```powershell
cd "C:\project\nara_crawler(API문서크롤러)"
.\venv\Scripts\python.exe -m pytest tests/test_storage_paths.py -v
```

Expected: 신규 1건 FAIL (`services/nara_storage`를 가리킴), 기존 5건 PASS

- [ ] **Step 3: crawl_run_manager.py 수정** — 모듈 상단(11행 `KST` 정의 근처)에
  Task 2와 동일한 `find_project_root`를 추가하고, 생성자를 교체:

```python
    def __init__(self, base_dir: str | Path):
        # base_dir = 크롤러 프로젝트 루트. 데이터 루트는 .nara-root 마커로 찾는다
        # (마커가 없으면 예전 규약대로 base_dir의 부모).
        self.base_dir = Path(base_dir)
        self.storage_dir = find_project_root(self.base_dir) / "nara_storage"
        self.manifests_dir = self.storage_dir / "manifests"
```

- [ ] **Step 4: 전체 스위트 확인** — Expected: 기준선 + 1

---

### Task 5: [hermes_poc] 루트 해석기 도입

**Files:**
- Modify: `nara_hermes_poc/app/config.py:10-11`
- Test: `nara_hermes_poc/tests/test_config_paths.py` (신규)

- [ ] **Step 1: 신규 테스트 작성** — `tests/test_config_paths.py`

```python
from app.config import DEFAULT_STORAGE_DIR, PROJECT_ROOT, find_project_root


def test_storage_dir_follows_project_root():
    assert DEFAULT_STORAGE_DIR == PROJECT_ROOT / "nara_storage"
    assert (PROJECT_ROOT / ".nara-root").is_file()


def test_find_project_root_finds_marker_above_nested_module(tmp_path):
    (tmp_path / ".nara-root").write_text("", encoding="utf-8")
    nested = tmp_path / "apps" / "hermes_poc"
    nested.mkdir(parents=True)
    assert find_project_root(nested) == tmp_path
```

- [ ] **Step 2: 실패 확인**

```powershell
cd C:\project\nara_hermes_poc
.\venv\Scripts\python.exe -m pytest tests/test_config_paths.py -v
```

- [ ] **Step 3: config.py 수정** — 10–11행을 교체 (`find_project_root`는 Task 2와 동일 본문):

```python
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = find_project_root(BASE_DIR)
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "nara_storage"
```

`FRESHNESS_ENV_DEFAULTS["NARA_STORAGE_DIR"]`(33행)은 `DEFAULT_STORAGE_DIR`를 참조하므로
자동으로 따라간다. `load_project_env`의 `BASE_DIR / ".env"`(40행)는 모듈 내부라 무변경.

- [ ] **Step 4: 전체 스위트 확인** — Expected: 기준선 + 2

---

### Task 6: [실행기 2종] 형제 탐색을 루트 기준으로

이동 **전에** 실행기를 루트 기준으로 바꿔둔다. 이름 리터럴은 아직 옛 이름이므로 이 단계에서도
동작이 동일하다 — 즉 Phase 1은 끝까지 무해하다.

**Files:**
- Modify: `nara_hermes_poc/run.py:22-23,50-51`
- Modify: `nara_workbench(API통합워크벤치)/run.py:15-16,36,45`

- [ ] **Step 1: hermes run.py**

`app.config`가 이미 해석기를 갖고 있으므로 재사용한다 (같은 모듈 내 import이므로 제약 위반 아님).
19행 import를 확장하고 22–23행을 교체:

```python
from app.config import PROJECT_ROOT, load_project_env


BASE_DIR = Path(__file__).resolve().parent
```

50–51행:

```python
    search_dir = PROJECT_ROOT / "nara_search(API문서검색)"
    combiner_dir = PROJECT_ROOT / "nara_combiner(API문서조합기)"
```

(`PROJECT_DIR` 심볼은 삭제한다. 잔존 참조 확인: `Select-String -Path run.py -Pattern 'PROJECT_DIR'` → 0건)

- [ ] **Step 2: workbench run.py**

workbench에는 config 모듈이 없으므로 `run.py` 안에 `find_project_root`를 직접 둔다.
15–16행을 교체:

```python
BASE_DIR = Path(__file__).resolve().parent


def find_project_root(start: Path) -> Path:
    """`.nara-root` 마커를 위로 훑어 저장소 루트를 찾는다 (없으면 부모로 폴백)."""
    for candidate in (start, *start.parents):
        if (candidate / ".nara-root").is_file():
            return candidate
    return start.parent


PROJECT_ROOT = find_project_root(BASE_DIR)
```

36·45행의 `PROJECT_DIR / ...`를 `PROJECT_ROOT / ...`로 바꾼다. 이름 리터럴은 아직 그대로 둔다.

- [ ] **Step 3: 실행기 스모크 (기동 없이 경로만)**

```powershell
cd "C:\project\nara_workbench(API통합워크벤치)"
.\venv\Scripts\python.exe -c "import run; print(run.PROJECT_ROOT); [print(s.cwd, s.cwd.is_dir()) for s in run.SERVICES]"
cd C:\project\nara_hermes_poc
.\venv\Scripts\python.exe -c "import run; print(run.PROJECT_ROOT); [print(s.cwd, s.cwd.is_dir()) for s in run.service_definitions(8020)]"
```

Expected: 루트가 `C:\project`, 모든 서비스 디렉터리 `True`

---

### Task 7: Phase 1 게이트 — 전체 회귀

- [ ] **Step 1: 5개 스위트 전부 실행** (Task 0 Step 2와 동일 명령)

Expected: search 기준선+3, combiner 기준선+3, crawler 기준선+1, hermes 기준선+2, workbench 기준선 그대로

- [ ] **Step 2: 디렉터리가 안 움직였는지 확인**

```powershell
git -C C:\project status --porcelain | Select-String '^R'
```

Expected: 출력 없음 (rename 0건). **여기서 rename이 잡히면 계획을 벗어난 것이므로 중단한다.**

한 건이라도 빨간불이면 **Phase 2로 넘어가지 않는다.**

---

## Phase 2 — 이동

### Task 8: git mv

**Files:** 6개 디렉터리 이동

- [ ] **Step 1: 실행 중인 프로세스·에디터 종료 확인**

이동 대상 디렉터리를 잡고 있는 프로세스가 있으면 Windows에서 rename이 실패한다.

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8003,8010,8020,5173 -ErrorAction SilentlyContinue |
  Select-Object LocalPort, OwningProcess
```

Expected: 출력 없음. 있으면 해당 서비스를 먼저 내린다.

- [ ] **Step 2: 계층 디렉터리 생성 후 이동**

```powershell
cd C:\project
New-Item -ItemType Directory -Force services, apps | Out-Null

git mv "nara_crawler(API문서크롤러)"      "services/crawler"
git mv "nara_search(API문서검색)"         "services/search"
git mv "nara_combiner(API문서조합기)"     "services/combiner"
git mv "nara_workbench(API통합워크벤치)"  "apps/workbench"
git mv "nara_dashboard(API관계대시보드)"  "apps/dashboard"
git mv "nara_hermes_poc"                  "apps/hermes_poc"
git mv "nara_gazetta"                     "apps/gazetta"
```

`nara_gazetta`는 추적 파일 4개(README·index.html·app.js·styles.css)뿐이고
경로·모듈 참조가 **0건**이라(`git grep` 확인 완료) 이동 후 손댈 것이 없다.

- [ ] **Step 3: rename으로 잡혔는지 확인**

```powershell
git -C C:\project status --porcelain | Select-String '^R' | Measure-Object
git -C C:\project status --porcelain | Select-String -NotMatch '^R'
```

Expected: rename 다수, non-rename 항목은 미추적 계획 문서뿐.
`git mv`는 디스크상 디렉터리를 통째로 옮기므로 **미추적 `venv/`도 함께 따라온다** (다음 태스크에서 재생성).

---

### Task 9: 실행기의 이름 리터럴 갱신

**Files:**
- Modify: `apps/hermes_poc/run.py:50-51`
- Modify: `apps/workbench/run.py:36,45`

- [ ] **Step 1: hermes**

```python
    search_dir = PROJECT_ROOT / "services" / "search"
    combiner_dir = PROJECT_ROOT / "services" / "combiner"
```

- [ ] **Step 2: workbench** — `SERVICES` 정의의 `cwd`를

```python
        PROJECT_ROOT / "services" / "search",
        ...
        PROJECT_ROOT / "services" / "combiner",
```

- [ ] **Step 3: 잔존 옛 이름 전수 검색**

```powershell
cd C:\project
git grep -n -E "nara_search\(|nara_combiner\(|nara_crawler\(|nara_dashboard\(|nara_workbench\(" -- . ":(exclude)archive" ":(exclude)docs"
```

Expected: 0건. 남으면 Task 11에서 문서로 처리할 항목인지 코드인지 구분한다.

---

### Task 10: venv 셔뱅 복구 (전면 재생성 불필요 — 실행 중 정정)

> **정정 (2026-07-29 실측):** 이 태스크의 원래 전제 "옮긴 venv는 동작하지 않으므로
> 전면 재생성해야 한다"는 **틀렸다.** 실측 결과:
>
> - `python.exe`는 **자기 위치에서** `sys.prefix`를 파생하고 `pyvenv.cfg`의 `home`은
>   이동하지 않은 기본 파이썬을 가리킨다 → **`python -m <module>` 경로는 그대로 동작한다.**
>   5개 모듈 전부 새 위치에서 전체 테스트가 통과했다.
> - `pyvenv.cfg`의 `command` 줄에 남은 옛 경로는 **순전히 기록용**이라 무해하다.
> - `Activate.ps1`은 `$VenvDir`를 런타임 계산하므로 정상이다.
> - **실제로 깨지는 것은 `Scripts/*.exe` 콘솔 셔뱅뿐이다** (`pytest.exe` 무응답 확인).
>   그런데 두 실행기는 `python -m uvicorn`을 쓰므로(`run.py`의 `start_uvicorn`)
>   기동 경로는 셔뱅과 무관하다.
>
> 따라서 torch·sentence-transformers 재다운로드(수 GB) 없이 **셔뱅만 복구**한다.
> 원래 계획대로 전면 재생성해도 결과는 같지만 수십 분이 더 걸린다.

- [x] **Step 1: 이동한 venv가 실제로 동작하는지 먼저 검증**

```powershell
foreach ($m in @('services\crawler','services\search','services\combiner','apps\workbench','apps\hermes_poc')) {
  & "C:\project\$m\venv\Scripts\python.exe" -c "import sys; print(sys.prefix, '|', sys.base_prefix)"
}
```

Expected: `prefix`가 **새 경로**, `base_prefix`가 기본 파이썬 설치 경로.
그다음 각 모듈에서 전체 테스트를 돌려 기능으로 확인한다. 통과하면 재생성은 불필요하다.

- [x] **Step 2: 콘솔 셔뱅만 복구**

```powershell
foreach ($m in @('services\crawler','services\search','services\combiner','apps\workbench','apps\hermes_poc')) {
  $py = "C:\project\$m\venv\Scripts\python.exe"
  $pkgs = @('pip','pytest')
  if (Test-Path "C:\project\$m\venv\Scripts\uvicorn.exe") { $pkgs += 'uvicorn' }
  & $py -m pip install -q --force-reinstall --no-deps @pkgs
}
```

`--no-deps`라 의존성 트리를 건드리지 않고 셔뱅만 재생성된다. 확인:
`& "C:\project\services\combiner\venv\Scripts\pytest.exe" --version`

> 나머지 셔뱅(`fastapi.exe`, `transformers.exe` 등)은 여전히 깨져 있다. 필요해지면
> 같은 방식으로 해당 패키지만 복구하거나, 그 모듈만 venv를 재생성한다.
> 문서화된 워크플로는 전부 `python -m` 형식이라 일상 사용에는 지장이 없다.

- [ ] **Step 2b (선택): 전면 재생성이 필요할 때**

셔뱅을 전부 정상화하고 싶거나 venv가 실제로 깨진 경우에만 실행한다.

```powershell
$mods = @{
  'services\crawler'   = 'requirements.txt'
  'services\search'    = 'backend\requirements.txt'   # search만 하위 경로
  'services\combiner'  = 'requirements.txt'
  'apps\workbench'     = 'requirements.txt'
  'apps\hermes_poc'    = 'requirements.txt'
}
foreach ($m in $mods.Keys) {
  $dir = Join-Path C:\project $m
  Remove-Item -Recurse -Force (Join-Path $dir 'venv') -ErrorAction SilentlyContinue
  & python -m venv (Join-Path $dir 'venv')
  & (Join-Path $dir 'venv\Scripts\python.exe') -m pip install -r (Join-Path $dir $mods[$m])
  # requirements에 pytest가 없다 — 테스트를 돌리려면 추가로 설치한다
  & (Join-Path $dir 'venv\Scripts\python.exe') -m pip install pytest httpx
}
```

search의 `torch`/`faiss` 설치는 수 분~수십 분 걸린다. GPU 구성을 쓰고 있었다면
`services/search/README.md`의 `requirements-gpu.txt` 절차를 이어서 적용하고,
Task 0 Step 3의 freeze 스냅샷과 `Compare-Object`로 대조해 누락을 확인한다.

- [ ] **Step 3: dashboard 의존성 설치**

```powershell
cd C:\project\apps\dashboard
npm install
npm test
```

Expected: 테스트 통과 (dashboard는 경로 결합이 없어 코드 변경이 없다)

---

## Phase 3 — 문서·설정 정리와 최종 검증

### Task 11: 상대경로·절대경로 문서 갱신

모듈이 2단계 깊어졌으므로 README의 `../nara_storage/`는 전부 `../../nara_storage/`가 된다.

- [ ] **Step 1: `../nara_storage` → `../../nara_storage`** (아래 8곳)

| 파일 | 라인 |
| --- | --- |
| `services/crawler/README.md` | 7, 9, 10, 11, 12, 13 |
| `services/search/README.md` | 33, 39, 193 |
| `services/combiner/README.md` | 88 |
| `services/combiner/.env.example` | 1, 2 (`..\nara_storage\openapi_new` → `..\..\nara_storage\openapi_new`) |
| `apps/hermes_poc/README.md` | 166 |
| `apps/hermes_poc/docs/hermes_tool_loop_plan.md` | 427 |
| `apps/hermes_poc/docs/agent_expansion_exploration.md` | 121 |

- [ ] **Step 2: 절대경로 갱신**

| 파일 | 라인 | 변경 |
| --- | --- | --- |
| `apps/hermes_poc/config/hermes.example.yaml` | 5 | `C:\\project\\nara_hermes_poc\\venv\\Scripts\\python.exe` → `C:\\project\\apps\\hermes_poc\\venv\\Scripts\\python.exe` |
| `apps/hermes_poc/config/hermes.example.yaml` | 10 | `PYTHONPATH: "C:\\project\\nara_hermes_poc"` → `"C:\\project\\apps\\hermes_poc"` |
| `apps/hermes_poc/README.md` | 45 | `cd C:\project\nara_hermes_poc` → `cd C:\project\apps\hermes_poc` |
| `apps/hermes_poc/docs/hermes_tool_loop_plan.md` | 5, 6 | 적용/보호 대상 경로 |
| `apps/hermes_poc/docs/plan_critic_agent_plan.md` | 8 | 보호 대상 이름 |
| `apps/hermes_poc/docs/flow_export_plan.md` | 7 | 보호 대상 이름 |
| `apps/hermes_poc/README.md` | 3, 26 | workbench 이름·트리 표기 |
| `apps/workbench/README.md` | 25 | `cd "D:\project\nara_workbench(API통합워크벤치)"` → `cd C:\project\apps\workbench` |
| `services/combiner/README.md` | 23 | `cd "D:\project\..."` → `cd C:\project\services\combiner` |

> `D:\` 표기는 원 개발 환경 잔재다. 이번에 손대는 줄은 `C:\project\` 기준으로 통일한다.
> `archive/` 아래의 `D:\project` 참조는 **보류 프로젝트이므로 건드리지 않는다.**

- [ ] **Step 3: CLAUDE.md 지도 갱신** — 이 파일이 SSoT이므로 반드시 함께 고친다.

  - 데이터 흐름 다이어그램(9–24행)의 모듈명을 새 경로로 교체
  - 모듈 표(26–34행)의 디렉터리명 열을 `services/crawler` 등으로 교체
  - **모듈 표에 `apps/gazetta` 행을 추가한다.** `nara_gazetta`는 커밋 `2af819a`로
    들어왔으나 CLAUDE.md 지도에 **누락되어 있다** — 이동하는 김에 SSoT를 맞춘다.
    (역할: 관보 정적 리더 프로토타입 / 비고: 나라 파이프라인 비의존, 빌드·서버 없음)
  - 38–39행 "무게중심" 문장의 모듈명
  - 52행 `각 모듈 README의 ../nara_storage/는 모듈 디렉터리 기준 상대경로다.`
    → `../../nara_storage/`로 고치고, **루트는 `.nara-root` 마커로 결정된다**는 문장을 추가
  - 58행 `start-all.ps1` 관련 서술: 이 스크립트는 현재 로컬에도 없으므로
    "존재하지 않는다"로 정정하거나 항목을 삭제
  - "코드만으로 알 수 없는 것들"에 **새 규칙 추가**:
    > 저장소 루트는 `.nara-root` 마커 파일로 결정된다. 각 모듈은 `find_project_root()`로
    > 위로 훑어 루트를 찾으므로, 모듈을 다른 깊이로 옮겨도 `nara_storage` 해석이 유지된다.
    > 모듈 간 import 금지 제약 때문에 이 함수는 각 모듈에 복제되어 있다 —
    > 한 곳을 고치면 나머지도 같이 고친다.

- [ ] **Step 4: 비교 문서의 경로 인용 갱신**

`docs/superpowers/plans/2026-07-29-hermes-workbench-comparison.md`는 `모듈/파일:라인` 형식
인용이 30건 이상이다. **의사결정 기록이므로 결론은 고치지 않고**, 문서 머리말에 한 줄 추가한다:

```markdown
> **경로 주석(2026-07-29 재배치 이후):** 본문의 `nara_search(API문서검색)/…` 등은
> 작성 시점 경로다. 현재 경로는 `services/search/…`, `apps/workbench/…`,
> `apps/hermes_poc/…`로 읽는다. 계획: `docs/superpowers/plans/2026-07-29-module-layering.md`
```

---

### Task 12: 최종 회귀 + 스모크

- [ ] **Step 1: 전 스위트 실행**

```powershell
cd C:\project\services\crawler;  .\venv\Scripts\python.exe -m pytest tests -q
cd C:\project\services\search;   .\venv\Scripts\python.exe -m pytest tests -q
cd C:\project\services\combiner; .\venv\Scripts\python.exe -m pytest tests -q
cd C:\project\apps\workbench;    .\venv\Scripts\python.exe -m pytest tests -q
cd C:\project\apps\hermes_poc;   .\venv\Scripts\python.exe -m pytest tests -q
cd C:\project\apps\dashboard;    npm test
```

Expected: Phase 1 게이트와 동일한 개수. **이동 때문에 바뀐 숫자가 하나라도 있으면 원인을 규명한다.**

- [ ] **Step 2: 데이터 루트 해석 실증**

```powershell
cd C:\project\services\search
.\venv\Scripts\python.exe -c "from backend.core import config; print(config.PROJECT_ROOT); print(config.APIDATA_DIR); print(config.APIDATA_DIR.exists())"
```

Expected: `C:\project` / `C:\project\nara_storage\openapi_new` / `True`
(마지막이 `False`면 데이터 미수집 상태일 뿐 경로 오류가 아니다 — `nara_storage` 존재 여부로 구분한다.)

- [ ] **Step 3: 실행기 스모크**

```powershell
cd C:\project\apps\workbench
.\venv\Scripts\python.exe run.py
```

브라우저에서 `http://127.0.0.1:8010` 확인 후 종료. 이어서 hermes:

```powershell
cd C:\project\apps\hermes_poc
.\venv\Scripts\python.exe run.py --poc-port 8020
```

Ollama 미기동이면 조합 경로만 503이고 검색·기동은 성공해야 정상이다.

- [ ] **Step 4: 잔존 참조 최종 확인**

```powershell
cd C:\project
git grep -n -E "nara_hermes_poc|nara_workbench|API통합워크벤치|API문서검색|API문서조합기|API문서크롤러|API관계대시보드" -- . ":(exclude)archive"
```

Expected: CLAUDE.md·README의 **의도적 한글 설명**과 비교 문서의 과거 인용만 남는다.
코드·설정에 남은 것이 있으면 놓친 것이다.

---

### Task 13: 루트 gov24 잔여물 제거

**대상:** `C:\project\nara_gov24_link_resolver(정부24서비스링크매핑)/` (추적 파일 **0건**)

이 디렉터리는 정본이 `archive/`로 옮겨진 뒤 남은 껍데기다. 조사 결과 내용물은:

| 항목 | 판정 |
| --- | --- |
| `venv/`, `.pytest_cache/`, `.pytest_tmp_locked/`, `scripts/__pycache__/`, `tests/__pycache__/` | 재생성 가능 — 버린다 |
| `scripts/`, `tests/`의 소스 파일 | 아카이브 사본과 동일 — 버린다 |
| `data/output/gov24_service_metadata.jsonl` (13.6KB) | **아카이브에 없다** — 먼저 보존 |
| `data/output/link_resolution_report.json` (0.7KB) | **아카이브에 없다** — 먼저 보존 |

**되돌릴 수 없는 삭제이므로 순서를 지킨다: 보존 먼저, 삭제 나중.**
(두 산출물은 2026-07-09자 링크 해석 결과다. `**/output/`이 gitignore 대상이라
아카이브로 옮겨도 추적되지는 않는다 — 로컬 보존일 뿐이다.)

- [ ] **Step 1: 미아카이브 산출물을 archive로 이동**

```powershell
$root = "C:\project\nara_gov24_link_resolver(정부24서비스링크매핑)"
$dest = "C:\project\archive\nara_gov24_link_resolver(정부24서비스링크매핑)\data\output"
New-Item -ItemType Directory -Force $dest | Out-Null
Move-Item -LiteralPath "$root\data\output\gov24_service_metadata.jsonl" -Destination $dest
Move-Item -LiteralPath "$root\data\output\link_resolution_report.json"  -Destination $dest
Get-ChildItem -LiteralPath $dest
```

Expected: 두 파일이 archive 아래에 존재

- [ ] **Step 2: 남은 것이 캐시·venv·중복본뿐인지 재확인**

```powershell
Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\(venv|__pycache__|\.pytest_cache|\.pytest_tmp_locked)\\' } |
  Select-Object FullName, Length
```

Expected: 출력 없음. **한 줄이라도 나오면 삭제하지 말고 보고한다.**

- [ ] **Step 3: 삭제**

```powershell
Remove-Item -LiteralPath $root -Recurse -Force
Test-Path -LiteralPath $root
```

Expected: `False`

`.pytest_tmp_locked/`에 접근 거부가 걸려 있어 실패할 수 있다. 그 경우:

```powershell
takeown /F "$root" /R /D Y | Out-Null
icacls "$root" /grant "$($env:USERNAME):(F)" /T /Q
Remove-Item -LiteralPath $root -Recurse -Force
```

그래도 실패하면 **강제하지 말고 보고한다.**

> **실행 결과 (2026-07-29): Step 1·2는 완료, Step 3은 차단됨.**
>
> - Step 1 ✅ 산출물 2건을 `archive/.../data/output/`로 이동 완료 (13,953 / 733 바이트).
> - Step 2 ✅ 남은 것은 `venv/`·`__pycache__/`·`.pytest_cache/`·`.pytest_tmp_locked/`뿐임을 확인.
> - Step 3 ❌ `.pytest_tmp_locked\.pytest_tmp`가 **관리자 권한 없이는 삭제 불가**.
>   `takeown`·`icacls` 모두 거부되고 `Get-Acl`조차 "Attempted to perform an
>   unauthorized operation"으로 실패한다. 프로세스 잠금이 아니라 **ACL 자체가
>   막고 있다** — 이름대로 잠긴 디렉터리를 다루는 테스트 픽스처로 보인다.
>
> **남은 조치 (관리자 PowerShell 필요):**
>
> ```powershell
> $root = "C:\project\nara_gov24_link_resolver(정부24서비스링크매핑)"
> takeown /F "$root" /R /D Y
> icacls "$root" /reset /T /Q
> Remove-Item -LiteralPath $root -Recurse -Force
> ```
>
> 이 디렉터리는 **추적 파일이 0건**이므로 남아 있어도 git·빌드·테스트에 영향이 없다.
> 보존이 필요한 데이터는 이미 archive로 옮겼으므로 급하지 않은 정리 항목이다.

- [ ] **Step 4: git 상태 무영향 확인**

```powershell
git -C C:\project status --porcelain | Select-String 'gov24'
```

Expected: 출력 없음 (애초에 추적되지 않았으므로 삭제가 git에 보이지 않는 것이 정상)

---

## 3. 이 계획에서 **하지 않는** 것

- 모듈 내부 구조 변경 (`backend/`, `app/`, `static/` 배치는 그대로)
- 포트 계약 변경 (8000/8003/8010/8020/5173 유지)
- `korea100/`, `archive/` 이동 — 각각 별개 제품·보류 자산이다
- 비교 문서(§10)가 권고한 기능 개선(관계 근거 프롬프트 주입 등) — **별개 작업**이다.
  구조 정리와 기능 변경을 한 커밋 범위에 섞지 않는다
- `git commit` — 사용자가 직접 관리한다

---

## 4. 확정된 결정 (2026-07-29, 사용자 승인)

계획 수립 중 열려 있던 세 항목은 모두 닫혔다. 실행자는 재질의 없이 아래대로 진행한다.

1. **`nara_gazetta/` → `apps/gazetta`.** 파이프라인 비의존 정적 프로토타입이지만
   `apps/` 아래로 함께 옮긴다. 경로·모듈 참조가 0건이라 이동 비용이 없다. (Task 8)

2. **루트 `nara_gov24_link_resolver(정부24서비스링크매핑)/` 삭제.** 정본이 `archive/`에
   있으므로 루트 껍데기는 제거한다. 단 **아카이브에 없는 산출물 2건(14KB)이 확인되었으므로
   먼저 archive로 옮긴 뒤 삭제한다** — "아카이빙되어 있으면 삭제"라는 조건을 그대로 지킨다. (Task 13)

3. **`nara_` 접두사는 디렉터리명에서만 제거한다.** Python 패키지명(`backend`, `app`),
   환경변수(`NARA_*`), 데이터 루트명(`nara_storage`)은 **전부 그대로 둔다** —
   건드리면 블라스트 반경이 몇 배로 커진다.

### 그래도 멈춰야 하는 경우

아래는 계획이 예상하지 못한 상태이므로 **임의 판단 없이 보고한다.**

- Task 0에서 작업 트리에 예상 밖 변경이 있을 때
- Task 7(Phase 1 게이트)에서 테스트 개수가 기준선과 다를 때
- Task 12에서 이동 전후 테스트 개수가 달라졌을 때
- Task 13 Step 2에서 캐시·venv·중복본 외 파일이 나올 때

---

## 5. 롤백

Phase 2 이후 문제가 생기면, 커밋 전이라면:

```powershell
cd C:\project
git status --porcelain | Select-String '^R'   # 무엇이 옮겨졌는지 먼저 확인
git reset --hard HEAD                          # 추적 파일 원복 (미추적 venv는 남는다)
Remove-Item -Recurse -Force C:\project\services, C:\project\apps -ErrorAction SilentlyContinue
```

`git reset --hard`는 추적된 변경을 모두 버린다. Phase 1 작업까지 되돌리고 싶지 않다면
**Phase 1 완료 시점에 커밋을 한 번 만들어 두는 것을 권한다** (커밋은 사용자 결정 사항).
venv는 어차피 Task 10에서 재생성하므로 롤백 대상이 아니다.
