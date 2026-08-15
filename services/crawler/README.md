# Nara Crawler - Korean Public API Documentation Crawler

Crawler for Korean public-API documentation from data.go.kr.

## 실행

옵션이 많아 외우기 어렵다면 **인자 없이 실행한다.** 마지막에 조립된 명령을 보여준 뒤
확인을 받는다 (`-i`로도 진입한다). 묻는 순서는 두 단계다:

1. **무엇을 크롤할지** — `--full`, 타입, `-s`, `-e`를 하나씩. 답이 없으면 실행이
   불가능한 것들이다. `--full`을 켜면 타입·범위는 묻지 않는다.
2. **나머지 선택 옵션** — 한 화면에 모아 놓고 켤 것만 번호로 고른다(`2,5`처럼 쉼표로
   여러 개, 옵션 이름을 그대로 쳐도 된다). Enter 한 번이면 전부 기본값이다.
   고른 옵션이 다른 옵션을 열면(`--deep` → `--full-download`) 그때만 한 번 더 묻는다.

타입 메뉴는 `fileData`·`openapi`·`standard` 셋만 제시한다. `openapi_new`·`openapi_old`·
`openapi_link`는 같은 CSV를 걸러낸 부분집합이고 실제 하위 타입은 크롤 후에 정해지므로
(아래 "openapi 하위 타입") 고를 것은 `openapi` 하나다. 명령줄로는 그대로 받는다.

```powershell
python main.py                          # 대화형: 물어보고 채워준다
python main.py openapi -s 1 -e 100      # 기존 명령줄 방식은 그대로
```

파이프·CI처럼 입력이 콘솔이 아니면 대화형으로 들어가지 않고 예전처럼 인자 부족
에러를 낸다.

## 브라우저 제어 UI (:8004)

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8004
```

`http://127.0.0.1:8004`에서 타입·범위·심화 옵션을 고르고 실행·중단하며 진행률과
로그를 본다. 백엔드는 위 CLI를 그대로 서브프로세스로 돌리고 출력을 SSE로 흘리므로,
브라우저에서 누른 실행과 터미널에서 친 명령이 같은 코드 경로를 탄다.

- 실행될 명령은 `POST /runs/preview`가 돌려준다. UI가 argv를 자체 조립하면 서버와
  어긋나므로 미리보기도 실제 실행과 같은 코드로 만든다.
- 문서번호 범위는 "CSV 범위 조회" 버튼을 누를 때만 계산한다. `metadata_file.csv`는
  100MB가 넘어 페이지를 열 때마다 훑을 수 없다. 결과는 CSV의 mtime·크기로 캐시한다.
- `--deep`·`--full-download`·`--harvest`는 기본 꺼짐이고 실행 전 확인을 받는다.
- tqdm 진행 표시줄은 `\r`로 같은 줄을 덮어쓰므로 `\n`만이 아니라 `\r`에서도 줄을
  끊어 진행률로 파싱한다.
- CORS를 열지 않는다. 이 서비스는 크롤을 시작시킬 수 있어 다른 출처의 페이지가
  로컬호스트로 요청을 보내게 두면 안 된다. `127.0.0.1`에만 바인딩한다.
- 한 번에 하나의 크롤만 허용한다. 목록 CSV와 `nara_storage`가 공유 자원이다.

## 산출물 경로

크롤링 결과는 저장소 공통 데이터 루트 `../../nara_storage/`에 저장된다 (run 폴더 없음).

- `../../nara_storage/openapi_new/{api_id}.json` — OpenAPI(신형) 문서
- `../../nara_storage/openapi_old/{api_id}.json` — OpenAPI(구형 HTML) 문서
- `../../nara_storage/openapi_link/{api_id}.json` — LINK형 문서
- `../../nara_storage/fileData/{api_id}.json`, `../../nara_storage/standard/{api_id}.json`
- `../../nara_storage/manifests/{run_id}.json` — 실행별 manifest (수집 파일 목록·체크섬)
- `../../nara_storage/manifests/{run_id}_{type}_summary.json` — 실행별 요약

같은 api_id를 다시 크롤링하면 해당 파일을 덮어쓴다 (최신 1파일 유지).
`-o/--output-dir`로 다른 경로를 지정할 수 있다.

## 심화 파이프라인 (크롤링 이후 단계)

전부 **옵트인**이다. 평범한 크롤에서는 아무것도 실행되지 않는다 — 데이터 파일을
내려받고 기관 포털을 두드리는 일은 data.go.kr 상세 페이지를 읽는 것보다 훨씬
침습적이기 때문이다.

| 플래그 | 하는 일 | 산출물 |
| --- | --- | --- |
| `--deep` | fileData를 Range 샘플링으로 받아 스키마·품질·주소 리포트를 전부 생성 | `nara_storage/reports/{run_id}_{file_schemas,quality,address_geo}.json` |
| `--full-download` | `--deep`을 샘플링 대신 전량 다운로드로 (포털 부하 큼) | 〃 + 받은 파일 `nara_storage/files/{run_id}/` |
| `--harvest` | LINK형에서 추출한 외부 호스트를 프로토콜 감지로 수집 | `..._portal_harvest.json` |
| `--harvest-max-hosts N` | 한 실행에서 프로브할 최대 호스트 수 (기본 4) | — |

리포트를 개별로 켜는 플래그는 없다. 비용은 전부 파일 수신에 있고 품질·주소
분석은 같은 샘플을 후처리할 뿐이라 나눌 실익이 없기 때문이다.

세 리포트는 모두 **파일명(`download_urls`의 키)으로 색인된 객체**다. 배열로 두면
어느 파일에서 나온 지표인지 알 수 없다.

### 심화 단계의 대상은 "이번 크롤"이 아니라 "저장소 전체"다

`--deep`은 `nara_storage/fileData/`를, `--harvest`는 `nara_storage/openapi_link/`를
읽는다. **이번 실행의 타입도 `-s/-e` 범위도 보지 않는다.** `fileData -s 1 -e 10 --deep`은
그 10건이 아니라 저장된 fileData 문서 전량을 프로파일링한다 — 파일 수신 비용이 크롤
범위에 비례하지 않으니 켜기 전에 저장 건수를 확인할 것. 대상 폴더가 비어 있으면
안내만 출력하고 넘어간다.

그래서 두 옵션은 크롤 없이 단독으로도 돈다(위 예시). 대화형 모드는 **그 코퍼스를
만들어낼 수 있는 실행에서만** 질문을 띄운다: `--deep`은 fileData·`--full`·타입 없는
단독 실행에서, `--harvest`는 openapi 계열·`--full`·단독 실행에서 묻는다.
openapi 크롤이 `--harvest` 대상이 되는 이유는 하위 타입이 크롤 후에 정해져
`openapi` 한 번이 LINK 문서를 만들어내기 때문이다. 명령줄에서는 어느 조합이든 받는다.

심화 단계는 저장된 문서를 읽으므로 **크롤 타입 없이 단독 실행**되며, 이때는
목록 CSV 갱신도 자동 생략된다 (`--skip-update` 불필요):

```powershell
python main.py --deep
python main.py --harvest
```

### openapi 하위 타입이 셋으로 늘었다

openapi 문서는 셋으로 나뉘며 분류 근거는 각 문서의 `api_type_evidence`에 남는다.

| 타입 | 판별 근거 | 의미 |
| --- | --- | --- |
| `openapi_new` | 인라인 `swaggerJson` 파싱 성공 | 신형 문서 |
| `openapi_old` | 비-LINK + 인라인 `swaggerJson` 파싱 불가/부재 | 구형 HTML 문서. 상세 표에서 API 규칙을 추출한다 |
| `openapi_link` | CSV `API 유형`이 LINK | 기관 자체 포털에 API가 있음 |

특정 `select` 태그가 아니라 파싱 가능한 Swagger 명세의 유무로 신·구형을 구분한다.

LINK형 문서도 이제 `endpoints[]`를 갖는다. data.go.kr 상세 페이지의 요청/응답
표를 openapi_new와 **동일한 스키마로** 합성한 것이며, 이 과정에 외부 요청은 없다.
페이지에서 확정할 수 없는 HTTP 메서드·타입·상태코드는 `unverified`로 보존된다.

### 상세기능 드롭박스를 전부 수집한다

`openapi_old`·`openapi_link` 상세 페이지의 "API 서비스" 드롭박스
(`select#open_api_detail_select`)는 오퍼레이션 목록이고, **옵션마다 요청주소와
요청변수·출력결과가 다르다.** 그런데 포털은 그중 하나만 서버에서 렌더한다.
예전에는 그 하나만 저장돼 15061362는 8개 중 1개, 15000063은 2개 중 1개만 남았다.

이제 옵션마다 `/tcs/dss/selectApiDetailFunction.do`에 POST해 조각을 받아 합성한다
(페이지의 조회하기 버튼과 같은 요청). 옵션별 성패는 문서의 `detail_functions[]`에
남고, 하나가 실패해도 나머지는 수집되며 전부 실패하면 페이지가 렌더한 하나가 남는다.
인라인 swagger가 있는 `openapi_new`는 스펙이 이미 전체를 담으므로 조회하지 않는다.
