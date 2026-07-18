# Nara API Workbench

`nara_search`, `nara_dashboard`, `nara_combiner`의 핵심 흐름을 한 화면과 한 실행
진입점으로 통합한 웹 앱이다.

## 통합 방식

| 기존 프로젝트 | 통합 앱에서의 역할 |
| --- | --- |
| `nara_search(API문서검색)` | 자연어·렉시컬 검색, 문서 상세, API 관계 근거 |
| `nara_dashboard(API관계대시보드)` | 선택 문서의 관계 맵과 관계 근거 검토 흐름 |
| `nara_combiner(API문서조합기)` | 선택한 API의 행정 서비스 조합 제안 |
| `korea100` | 차분한 공공정책형 색상·타이포·근거 중심 정보 구조 |

기존 프로젝트 코드를 중복 복사하지 않고 통합 게이트웨이가 기존 HTTP 계약을 같은
출처 아래로 연결한다. 새 UI가 검색 → 선택 → 관계 검토 → 조합 설계를 하나의
상태로 관리하며, 조합 계약처럼 공통으로 지켜야 하는 제한은 기존 서비스와 함께
맞춘다.

## 실행

처음 한 번 가상환경을 만들고 통합 런타임 의존성을 설치한다.

```powershell
cd "D:\project\nara_workbench(API통합워크벤치)"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

이후에는 활성화된 가상환경에서 다음 한 줄로 실행한다.

```powershell
python .\run.py
```

브라우저에서 `http://127.0.0.1:8010`을 연다. 통합 실행기는 8000의 검색 서비스와
8003의 조합 서비스를 함께 시작한다. 해당 포트에 이미 서비스가 실행 중이면
기존 프로세스를 그대로 사용한다.

실행기는 시작 전에 현재 Python의 필수 패키지를 검사한다. 검색 프로젝트의 자체
가상환경이 있으면 우선 사용하며, 없으면 현재 가상환경과 기본 Python 중
`faiss`·`sentence-transformers`가 준비된 환경을 선택한다. 사용할 Python을
직접 고정하려면 `NARA_SEARCH_PYTHON`, `NARA_COMBINER_PYTHON`에 실행 파일
경로를 지정한다.

이미 두 백엔드를 따로 실행 중일 때는 UI 게이트웨이만 시작할 수 있다.

```powershell
python .\run.py --no-services
```

## 환경 변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `NARA_SEARCH_URL` | `http://127.0.0.1:8000` | 검색 백엔드 |
| `NARA_COMBINER_URL` | `http://127.0.0.1:8003` | 조합 백엔드 |
| `NARA_SEARCH_PYTHON` | 자동 선택 | 검색 백엔드용 Python 실행 파일 |
| `NARA_COMBINER_PYTHON` | 자동 선택 | 조합 백엔드용 Python 실행 파일 |

검색 모델·데이터·Ollama 설정은 각 기존 프로젝트의 환경 변수를 그대로 따른다.
FAISS가 준비되지 않아도 `nara_search`의 렉시컬 검색을 사용할 수 있다. 조합
제안은 로컬 Ollama가 준비되지 않으면 해당 패널에 연결 오류를 표시하지만 검색과
관계 검토는 계속 사용할 수 있다. 조합 서버의 기본 생성 모델은
`qwen3.5:4b`이고 thinking이 활성화되어 있다. 한 번에 최대 3개의 API를 조합하며,
분석 중에는 화면에서 현재 대기 단계와 경과 시간을 확인할 수 있다. 실행 전에
`OLLAMA_MODEL` 환경변수를 지정하면 다른 설치 모델로 덮어쓸 수 있다.

## 개발 서버

게이트웨이만 직접 실행하려면:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8010 --reload
```

정적 프론트엔드는 `static/`에 있으며 별도 Node 빌드가 필요 없다.
