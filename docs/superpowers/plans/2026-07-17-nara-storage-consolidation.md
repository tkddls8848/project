# nara_storage 중앙 데이터 저장소 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** crawler가 `D:\project\nara_storage\{데이터타입}\{api_id}.json`으로 저장하고(타임스탬프 run 폴더 제거, 전 타입 덮어쓰기), search·combiner가 같은 곳을 기본값으로 조회하게 한다.

**Architecture:** 규칙은 문서가 아니라 각 앱 config의 기본값으로 표현한다 — 각 앱은 `BASE_DIR.parent / "nara_storage"`로 동일 지점을 계산하고, 기존 앱별 env 오버라이드는 유지된다. crawler의 run 기록(manifest·summary)은 `nara_storage/manifests/{run_id}*.json`으로 분리 보존한다. dashboard는 search API 경유라 무변경.

**Tech Stack:** Python (crawler 표준 라이브러리 + pytest 신규, FastAPI search, combiner), PowerShell 5.1 (start-all.ps1)

**Spec:** `docs/superpowers/specs/2026-07-17-nara-storage-consolidation-design.md`

## Global Constraints

- 저장 규칙: `nara_storage/{data_type}/{api_id}.json` — data_type ∈ {openapi_new, openapi_link, fileData, standard}, 재크롤링 시 **전 타입 공통** 덮어쓰기 (파일명에 수정일 없음)
- run 기록: `nara_storage/manifests/{run_id}.json` (manifest), `nara_storage/manifests/{run_id}_{data_type}_summary.json` (summary). run_id 형식 `%Y-%m-%dT%H-%M-%S` (KST) 유지
- 경로 계산: 각 앱에서 `BASE_DIR.parent / "nara_storage"` — 절대경로·사용자 경로 하드코딩 금지
- env 오버라이드 유지: `NARA_SEARCH_APIDATA_DIR`, `NARA_DATA_DIR` (새 env 추가 금지)
- search·combiner는 `nara_storage/openapi_new`만 조회 (canonical prefix `openapi_new:`)
- 프로젝트 간 Python/JS 모듈 직접 import 금지
- **git 명령 실행 금지** — 사용자가 커밋을 직접 관리한다. 계획의 커밋 단계는 모두 생략하고 변경은 작업 트리에만 남긴다
- 테스트 실행: 각 프로젝트 디렉터리에서 `python -m pytest tests -q` (dashboard는 `npm test`)
- 기존 스위트 기준선: search 62, combiner 22, dashboard 47 — 회귀 없이 유지

**경로 표기:** `crawler/` = `D:\project\nara_crawler(API문서크롤러)\`, `search/` = `D:\project\nara_search(API문서검색)\`, `combiner/` = `D:\project\nara_combiner(API문서조합기)\`. 괄호·한글 경로는 셸에서 반드시 따옴표로 감싼다.

---

### Task 1: [crawler] 저장 경로를 nara_storage 평면 구조로 전환

**Files:**
- Modify: `crawler/managers/crawl_run_manager.py` (경로 계산 전면 수정)
- Modify: `crawler/managers/file_storage.py:31,52` (파일명에서 수정일 제거)
- Modify: `crawler/main.py:109-113,139,191-196,203,314` (run_dir 제거 반영)
- Create: `crawler/tests/__init__.py` 없음 — 대신 `crawler/tests/conftest.py`
- Test: `crawler/tests/test_storage_paths.py` (신규 — crawler 최초의 테스트)

**Interfaces:**
- Consumes: 없음 (독립)
- Produces (Task 2·3이 가정하는 계약):
  - `CrawlRunManager(base_dir).storage_dir == Path(base_dir).parent / "nara_storage"`
  - `CrawlRunManager.get_raw_output_dir(data_type: str) -> Path` — **run_id 파라미터 제거됨**, `storage_dir / data_type` 반환
  - `CrawlRunManager.manifests_dir == storage_dir / "manifests"`
  - `CrawlRunManager.save_manifest(crawl_run_id, manifest) -> Path` — `manifests_dir / f"{crawl_run_id}.json"`에 저장
  - `DataExporter.save_crawling_result(...)` 파일명 `{api_id}.json` (openapi 타입은 `{output_dir}/{api_type}/` 하위, 그 외는 `{output_dir}/` 직행 — 기존 분기 유지)

- [ ] **Step 1: 실패하는 테스트 작성**

`crawler/tests/conftest.py`:

```python
import sys
from pathlib import Path

# 디렉터리명에 한글·괄호가 있어 패키지 import가 불가하므로
# 크롤러 루트를 sys.path에 넣고 managers 패키지로 import한다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

`crawler/tests/test_storage_paths.py`:

```python
import json
import os

from managers.crawl_run_manager import CrawlRunManager
from managers.file_storage import DataExporter


def test_storage_root_is_sibling_nara_storage(tmp_path):
    manager = CrawlRunManager(tmp_path / "nara_crawler")
    assert manager.storage_dir == tmp_path / "nara_storage"
    assert manager.manifests_dir == tmp_path / "nara_storage" / "manifests"


def test_raw_output_dir_is_flat_type_dir(tmp_path):
    manager = CrawlRunManager(tmp_path / "nara_crawler")
    # run_id 계층 없이 데이터타입 폴더 직행
    assert manager.get_raw_output_dir("fileData") == tmp_path / "nara_storage" / "fileData"
    assert manager.get_raw_output_dir("standard") == tmp_path / "nara_storage" / "standard"


def test_save_manifest_goes_to_manifests_dir(tmp_path):
    manager = CrawlRunManager(tmp_path / "nara_crawler")
    run_id = "2026-07-17T10-00-00"
    path = manager.save_manifest(run_id, {"crawl_run_id": run_id, "runs": []})
    assert path == tmp_path / "nara_storage" / "manifests" / f"{run_id}.json"
    assert json.loads(path.read_text(encoding="utf-8"))["crawl_run_id"] == run_id


def test_openapi_recrawl_overwrites_single_file(tmp_path):
    storage = tmp_path / "nara_storage"
    data = {
        "api_id": "15000001",
        "api_type": "openapi_new",
        "info": {"제공기관": "한국환경공단", "수정일": "2026-01-01"},
    }
    saved, errors = DataExporter.save_crawling_result(data, str(storage), "15000001")
    assert errors == []
    assert saved == [os.path.join(str(storage), "openapi_new", "15000001.json")]

    # 수정일이 달라져도 같은 파일을 덮어쓴다 (파일 1개 유지)
    data_recrawled = {**data, "info": {"제공기관": "한국환경공단", "수정일": "2026-02-02"}}
    saved2, errors2 = DataExporter.save_crawling_result(data_recrawled, str(storage), "15000001")
    assert errors2 == []
    assert saved2 == saved
    files = list((storage / "openapi_new").glob("*.json"))
    assert len(files) == 1
    stored = json.loads(files[0].read_text(encoding="utf-8"))
    assert stored["info"]["수정일"] == "2026-02-02"


def test_non_openapi_saves_flat_in_given_dir(tmp_path):
    # 비 openapi 타입은 main이 이미 {storage}/{data_type}을 output_dir로 넘긴다
    type_dir = tmp_path / "nara_storage" / "fileData"
    data = {"api_id": "20000001", "api_type": "fileData", "info": {}}
    saved, errors = DataExporter.save_crawling_result(data, str(type_dir), "20000001")
    assert errors == []
    assert saved == [os.path.join(str(type_dir), "20000001.json")]
```

- [ ] **Step 2: 실패 확인**

```powershell
cd "D:\project\nara_crawler(API문서크롤러)"
python -m pytest tests -v
```

Expected: FAIL — `storage_dir`/`manifests_dir` 속성 없음(AttributeError), `get_raw_output_dir` 인자 개수 오류, 파일명 `15000001_2026-01-01.json`으로 저장되어 경로 단정 실패

- [ ] **Step 3: crawl_run_manager.py 수정**

클래스 상단(생성자~save_manifest)을 다음으로 교체한다. `create_run_id`, `sha256_file`, `now_iso`, `build_file_records`는 그대로 둔다:

```python
class CrawlRunManager:
    """공유 데이터 루트(nara_storage)와 크롤 실행 기록을 관리한다."""

    def __init__(self, base_dir: str | Path):
        # base_dir = 크롤러 프로젝트 루트. 데이터는 형제 디렉터리
        # {base_dir 부모}/nara_storage 에 run 폴더 없이 평면으로 저장한다.
        self.base_dir = Path(base_dir)
        self.storage_dir = self.base_dir.parent / "nara_storage"
        self.manifests_dir = self.storage_dir / "manifests"

    @staticmethod
    def create_run_id(now: datetime | None = None) -> str:
        now = now or datetime.now(KST)
        return now.astimezone(KST).strftime("%Y-%m-%dT%H-%M-%S")

    def get_raw_output_dir(self, data_type: str) -> Path:
        return self.storage_dir / data_type
```

`_build_file_record`의 상대경로 기준을 storage로 바꾼다:

```python
        try:
            rel_path = path.relative_to(self.storage_dir).as_posix()
        except ValueError:
            rel_path = path.as_posix()
```

`save_manifest`를 manifests 디렉터리 기준으로 교체한다:

```python
    def save_manifest(self, crawl_run_id: str, manifest: Dict[str, Any]) -> Path:
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.manifests_dir / f"{crawl_run_id}.json"
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return manifest_path
```

(`get_run_dir` 메서드는 삭제한다 — 호출부는 Step 4·5에서 정리.)

- [ ] **Step 4: file_storage.py 수정**

`save_crawling_result`에서 수정일 접미사를 없앤다. 31행의 `modified_date = table_info.get('수정일', 'unknown_date')` 줄을 삭제하고, 52행을:

```python
        file_prefix = f"{doc_num}_{modified_date}"
```

에서 다음으로 교체:

```python
        # 재크롤링 시 같은 파일을 덮어쓴다 — 전 타입 공통, 최신 1파일만 유지
        file_prefix = doc_num
```

- [ ] **Step 5: main.py 호출부 정리**

109-113행 `get_default_output_dir`를 교체 (run_id 의존 제거):

```python
def get_default_output_dir(data_type: str) -> str:
    run_manager = CrawlRunManager(BASE_DIR)
    if is_openapi_type(data_type):
        # openapi는 file_storage가 api_type(openapi_new/openapi_link) 하위 폴더를 붙인다
        return str(run_manager.storage_dir)
    return str(run_manager.get_raw_output_dir(storage_data_type(data_type)))
```

139행: `output_dir = output_dir or get_default_output_dir(data_type, crawl_run_id)` → `output_dir = output_dir or get_default_output_dir(data_type)`

191-196행 summary 저장을 manifests 기준으로 교체:

```python
    run_manager.manifests_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_manager.manifests_dir / f"{crawl_run_id}_{data_type}_summary.json"

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
```

203행: `"summary_path": str(summary_path.relative_to(BASE_DIR).as_posix()),` → `"summary_path": str(summary_path.relative_to(run_manager.storage_dir).as_posix()),`

314행 안내 출력: `print(f"Manifest saved to {run_manager.get_run_dir(crawl_run_id) / 'manifest.json'}")` → `print(f"Manifest saved to {run_manager.manifests_dir / (crawl_run_id + '.json')}")`

마지막으로 `get_run_dir` 잔존 호출이 없는지 확인한다: `grep -n "get_run_dir" main.py managers/*.py` → 0건이어야 한다.

- [ ] **Step 6: 테스트 통과 확인**

```powershell
python -m pytest tests -v
```

Expected: 5 passed

- [ ] **Step 7: crawler README 경로 서술 현행화**

`crawler/README.md`에서 `apidata`·run 폴더·타임스탬프 관련 서술을 grep으로 찾아(`grep -n "apidata\|run" README.md`) 산출물 경로 설명을 다음 내용으로 교체·추가한다 (문서의 기존 문체 유지):

```markdown
## 산출물 경로

크롤링 결과는 저장소 공통 데이터 루트 `../nara_storage/`에 저장된다 (run 폴더 없음).

- `../nara_storage/openapi_new/{api_id}.json` — OpenAPI(신형) 문서
- `../nara_storage/openapi_link/{api_id}.json` — LINK형 문서
- `../nara_storage/fileData/{api_id}.json`, `../nara_storage/standard/{api_id}.json`
- `../nara_storage/manifests/{run_id}.json` — 실행별 manifest (수집 파일 목록·체크섬)
- `../nara_storage/manifests/{run_id}_{type}_summary.json` — 실행별 요약

같은 api_id를 다시 크롤링하면 해당 파일을 덮어쓴다 (최신 1파일 유지).
`-o/--output-dir`로 다른 경로를 지정할 수 있다.
```

- [ ] **Step 8: 커밋 생략 (git 금지)** — 변경은 작업 트리에 남긴다.

---

### Task 2: [search·combiner] 조회 기본값을 nara_storage/openapi_new로

**Files:**
- Modify: `search/backend/core/config.py:19`
- Modify: `combiner/app/config.py:10`
- Test: `search/tests/test_config_defaults.py` (신규)
- Test: `combiner/tests/test_config_defaults.py` (신규)
- Modify: `search/README.md` (폴더 구조·데이터 섹션), `combiner/README.md` (환경 변수 섹션)

**Interfaces:**
- Consumes: Task 1의 저장 규칙 (`nara_storage/openapi_new/{api_id}.json`)
- Produces: search `config.APIDATA_DIR` 기본값 = `BASE_DIR.parent / "nara_storage" / "openapi_new"`; combiner `NARA_DATA_DIR` 기본값 동일 지점. env 오버라이드 의미는 기존과 동일 (테스트들이 fixture 주입에 사용)

- [ ] **Step 1: 실패하는 테스트 작성 (search)**

`search/tests/test_config_defaults.py`:

```python
import importlib


def test_apidata_default_points_to_shared_storage(monkeypatch):
    from backend.core import config

    monkeypatch.delenv("NARA_SEARCH_APIDATA_DIR", raising=False)
    try:
        importlib.reload(config)
        assert config.APIDATA_DIR == config.BASE_DIR.parent / "nara_storage" / "openapi_new"
    finally:
        # 다른 테스트가 모듈 상태에 의존하지 않도록 원복 reload
        importlib.reload(config)
```

- [ ] **Step 2: 실패 확인 (search)**

```powershell
cd "D:\project\nara_search(API문서검색)"
python -m pytest tests/test_config_defaults.py -v
```

Expected: FAIL — 현재 기본값은 `BASE_DIR / "apidata"`

- [ ] **Step 3: search config 수정**

`search/backend/core/config.py` 19행을 교체:

```python
# OpenAPI JSON 데이터 — 저장소 공통 루트 nara_storage의 openapi_new 폴더
# ({api_id}.json 평면, nara_crawler가 생산). env로 오버라이드 가능.
APIDATA_DIR = _env_path("NARA_SEARCH_APIDATA_DIR", BASE_DIR.parent / "nara_storage" / "openapi_new")
```

- [ ] **Step 4: 전체 테스트 통과 확인 (search)**

```powershell
python -m pytest tests -q
```

Expected: 63 passed (62 기존 + 1 신규; 기존 테스트는 env·monkeypatch 주입이라 기본값 변경에 영향받지 않는다)

- [ ] **Step 5: 실패하는 테스트 작성 (combiner)**

먼저 `combiner/tests/` 의 기존 테스트 상단 import 방식을 확인하고 동일하게 따른다 (conftest가 sys.path를 잡아주면 그대로, 아니면 기존 패턴 복제). `combiner/tests/test_config_defaults.py`:

```python
import importlib


def test_data_dir_default_points_to_shared_storage(monkeypatch):
    from app import config

    monkeypatch.delenv("NARA_DATA_DIR", raising=False)
    try:
        importlib.reload(config)
        assert config.NARA_DATA_DIR == config.BASE_DIR.parent / "nara_storage" / "openapi_new"
    finally:
        importlib.reload(config)
```

주의: `config.py`가 `load_dotenv()`를 호출하므로, 저장소에 `.env` 파일이 있고 `NARA_DATA_DIR`를 정의한다면 reload 시 다시 주입된다. 그 경우 `monkeypatch.delenv` 후에도 실패할 수 있으니 `.env` 존재 여부를 확인하고, 있으면 테스트에서 `monkeypatch.setattr`로 `os.environ` 정리 후 reload한다 (없으면 위 코드 그대로).

- [ ] **Step 6: 실패 확인 (combiner)**

```powershell
cd "D:\project\nara_combiner(API문서조합기)"
python -m pytest tests/test_config_defaults.py -v
```

Expected: FAIL — 현재 기본값은 `BASE_DIR / "apidata"`

- [ ] **Step 7: combiner config 수정**

`combiner/app/config.py` 10행을 교체:

```python
# 공유 데이터 루트 nara_storage의 openapi_new 폴더 (env로 오버라이드 가능)
NARA_DATA_DIR: Path = Path(os.getenv("NARA_DATA_DIR", str(BASE_DIR.parent / "nara_storage" / "openapi_new")))
```

- [ ] **Step 8: 전체 테스트 통과 확인 (combiner)**

```powershell
python -m pytest tests -q
```

Expected: 23 passed (22 기존 + 1 신규)

- [ ] **Step 9: README 갱신**

`search/README.md`:
- 폴더 구조 블록의 `apidata/` 행(`apidata/               ← OpenAPI JSON ({api_id}_{date}.json, 평면 3,526건)`)을 삭제하고, 구조 블록 아래에 한 줄 추가: `데이터는 저장소 공통 루트 ../nara_storage/openapi_new/{api_id}.json 에서 읽는다 (NARA_SEARCH_APIDATA_DIR로 오버라이드).`
- `### 데이터` 섹션의 `apidata/*.json` 서술을 교체: `../nara_storage/openapi_new/*.json ({api_id}.json 평면 — nara_crawler 산출물). 스키마: api_id, info, endpoints, swagger_json.`

`combiner/README.md` 환경 변수 블록:
`NARA_DATA_DIR=.\apidata` → `NARA_DATA_DIR=..\nara_storage\openapi_new   # 기본값 (미설정 시)`

- [ ] **Step 10: 커밋 생략 (git 금지)** — 변경은 작업 트리에 남긴다.

---

### Task 3: [루트] start-all 기본 경로·.gitignore·빈 폴더 정리

**Files:**
- Modify: `D:\project\start-all.ps1:1-10`
- Modify: `D:\project\.gitignore` (183행 `**/apidata/` 블록 근처)
- Delete: 빈 디렉터리 `crawler/apidata`, `search/apidata`, `combiner/apidata`, `dashboard/apidata` (모두 현재 비어 있음 — 비어 있지 않으면 중단하고 보고)

**Interfaces:**
- Consumes: Task 2의 기본값 (search·combiner가 `../nara_storage/openapi_new`를 스스로 찾으므로 start-all의 env 주입은 오버라이드 용도로만 남는다)
- Produces: 없음 (마무리 태스크)

- [ ] **Step 1: start-all.ps1 기본 경로 교체**

1-10행을 다음으로 교체 (이하 Start-Process 부분은 무변경):

```powershell
# Nara 통합 제품 로컬 기동: search(8000) + combiner(8003) + dashboard(5173)
# 사용: .\start-all.ps1 [-ApidataDir <경로>]
param(
  [string]$ApidataDir = (Join-Path $PSScriptRoot 'nara_storage\openapi_new')
)

if (-not (Test-Path $ApidataDir)) {
  Write-Warning "API 문서 디렉터리가 없습니다: $ApidataDir"
  Write-Warning "검색·카탈로그가 빈 상태로 뜹니다. nara_crawler를 실행해 nara_storage를 채우거나 -ApidataDir로 경로를 지정하세요."
}
```

구문 검증:

```powershell
powershell -NoProfile -Command "$null = [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw 'D:\project\start-all.ps1'), [ref]$null); 'PARSE_OK'"
```

Expected: `PARSE_OK`

- [ ] **Step 2: .gitignore에 nara_storage 추가**

`**/apidata/` 항목(183행 부근) 위에 다음 두 줄을 추가:

```gitignore
# 공유 API 문서 데이터 루트 (nara_crawler 산출물 — git 제외)
nara_storage/
```

- [ ] **Step 3: 빈 apidata 폴더 제거**

각 폴더가 비어 있는지 확인 후 제거한다 (비어 있지 않으면 제거하지 말고 보고):

```powershell
foreach ($d in @(
  'D:\project\nara_crawler(API문서크롤러)\apidata',
  'D:\project\nara_search(API문서검색)\apidata',
  'D:\project\nara_combiner(API문서조합기)\apidata',
  'D:\project\nara_dashboard(API관계대시보드)\apidata'
)) {
  if (Test-Path $d) {
    if (@(Get-ChildItem -Force $d).Count -eq 0) { Remove-Item $d } else { Write-Warning "비어 있지 않음: $d" }
  }
}
```

(`tests/fixtures/apidata`는 각 프로젝트 tests 하위라 위 목록과 무관 — 건드리지 않는다.)

- [ ] **Step 4: 최종 회귀 확인**

```powershell
cd "D:\project\nara_crawler(API문서크롤러)"; python -m pytest tests -q      # 5 passed
cd "D:\project\nara_search(API문서검색)"; python -m pytest tests -q        # 63 passed
cd "D:\project\nara_combiner(API문서조합기)"; python -m pytest tests -q    # 23 passed
cd "D:\project\nara_dashboard(API관계대시보드)"; npm test                  # 47 passed (무변경 확인)
```

- [ ] **Step 5: 커밋 생략 (git 금지)** — 변경은 작업 트리에 남긴다.
