# Nara Crawler - Korean Public API Documentation Crawler

Crawler for Korean public-API documentation from data.go.kr.

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
| `--full-download` | `--deep`을 샘플링 대신 전량 다운로드로 (포털 부하 큼) | 〃 |
| `--harvest` | LINK형에서 추출한 외부 호스트를 프로토콜 감지로 수집 | `..._portal_harvest.json` |
| `--harvest-max-hosts N` | 한 실행에서 프로브할 최대 호스트 수 (기본 4) | — |

리포트를 개별로 켜는 플래그는 없다. 비용은 전부 파일 수신에 있고 품질·주소
분석은 같은 샘플을 후처리할 뿐이라 나눌 실익이 없기 때문이다.

심화 단계는 저장된 문서를 읽으므로 **크롤 타입 없이 단독 실행**되며, 이때는
목록 CSV 갱신도 자동 생략된다 (`--skip-update` 불필요):

```powershell
python main.py --deep
python main.py --harvest
```

### openapi 하위 타입이 셋으로 늘었다

`openapi_link`가 진짜 LINK형과 swagger 파싱 실패분을 뭉개고 있었다. 이제 셋으로
나뉘고, 분류 근거는 각 문서의 `api_type_evidence`에 남는다.

| 타입 | 판별 근거 | 의미 |
| --- | --- | --- |
| `openapi_new` | 인라인 `swaggerJson` 파싱 성공 | 신형 문서 |
| `openapi_old` | 비-LINK + 인라인 `swaggerJson` 파싱 불가/부재 | 구형 HTML 문서. 상세 표에서 API 규칙을 추출한다 |
| `openapi_link` | CSV `API 유형`이 LINK | 기관 자체 포털에 API가 있음 |

`openapi_old`는 새로 만든 이름이 아니라 **원래 있던 분류를 되살린 것**이다.
리팩터링 과정에서 분기가 사라지면서 구형 문서들이 `openapi_link`에 조용히
섞여 들어갔다 (git 이력: `nara_crawler/crawler/crawler/openapi_crawler.py`). 특정
`select` 태그 하나에 의존하지 않고, 파싱 가능한 Swagger 명세의 유무로 신·구형을
구분한다.
저장된 7,643건 중 37.9%가 실제로는 LINK형이 아니었다.

LINK형 문서도 이제 `endpoints[]`를 갖는다. data.go.kr 상세 페이지의 요청/응답
표를 openapi_new와 **동일한 스키마로** 합성한 것이며, 이 과정에 외부 요청은 없다.
페이지에서 확정할 수 없는 HTTP 메서드·타입·상태코드는 `unverified`로 보존된다.

> **재크롤링이 필요하다.** `external_endpoint_urls`는 이번에 추가된 필드라
> 기존에 저장된 LINK 문서 7,643건에는 없다. `--harvest-portals`는 이 필드를
> 입력으로 쓰므로, 재크롤링 전에는 0호스트를 보고한다.
