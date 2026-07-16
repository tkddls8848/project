# 서브프로젝트 정리 및 통합 제품 설계

- 작성일: 2026-07-16
- 상태: 사용자 승인됨 (대화 중 섹션별 승인 완료)
- 대체 문서: 이 설계는 `plan unified.md`의 "서브프로젝트 독립 개발" 원칙을 대체한다.

## 1. 배경과 목표

여러 서브프로젝트가 병렬로 벌어져 있어 완성도가 분산되고 있다. `korea100`(제도 187개를
노드+엣지+법령 근거+검증 상태의 데이터 계약으로 고정해 공개 웹서비스로 완성)을 벤치마크하여,
다음 세 가지를 나라 서브프로젝트에 이식한다.

1. **완성 우선 태도** — 여러 개를 벌리지 않고 하나의 제품을 끝까지 민다.
2. **데이터 모델** — 노드 간 연결을 근거(evidence)와 상태(status)가 붙은 명시적 데이터 계약으로 만든다.
3. **결과물 형태** — 사용자 관점의 단일 웹 제품으로 수렴한다.

최종 목표: **자연어 질의 → 관련 공공 API 문서 검색 → 문서 노드 간 연결관계 연출 →
조합 제안으로 새로운 결과 도출**을 하나의 흐름으로 제공하는 제품.

배포 범위: **우선 로컬 완성품**. 호스팅·공개 배포는 로컬에서 제품이 완성된 뒤 별도 결정한다.

## 2. 서브프로젝트 판정

| 프로젝트 | 판정 | 근거 |
| --- | --- | --- |
| nara_search(API문서검색) | **유지 — 백엔드 핵심** | 자연어 질의의 입구 (FAISS 검색) |
| nara_combiner(API문서조합기) | **유지 — 백엔드 핵심** | 조합으로 새 결과 도출 |
| nara_dashboard(API관계대시보드) | **유지 — 제품의 얼굴** | 노드 연결관계 연출 (React Flow) |
| nara_crawler(API문서크롤러) | **유지 — 데이터 파이프라인** | apidata 공급원, 변경 없음 |
| nara_openclaw(행정서비스실행기) | **아카이브** | "실행"은 문서 관계 도출 목표와 거리가 큼 |
| nara_gov24_link_resolver(정부24서비스링크매핑) | **아카이브** | 링크 큐레이션 데이터셋은 주변부 |
| korea100 | 독립 유지 | 벤치마크 대상, 이번 작업 범위 밖 |

## 3. 정리(아카이브) 단계

- `D:\project\archive\` 디렉터리를 만들고 `nara_openclaw(행정서비스실행기)`,
  `nara_gov24_link_resolver(정부24서비스링크매핑)`를 `git mv`로 통째로 이동한다 (히스토리 유지).
- `plan unified.md`를 이 설계 기반의 통합 제품 계획으로 대체한다. 아카이브된 프로젝트는
  '보류' 상태로 명시한다.
- combiner의 "openclaw로 넘길 계획 초안" 관련 서술은 문서에서 범위 밖(out of scope)으로
  표시만 하고 코드는 수정하지 않는다.

## 4. 관계 데이터 계약 (korea100 벤치마크의 핵심)

현재 API 문서 간 연결관계는 combiner의 LLM 응답 텍스트 안에만 존재한다. 이를 korea100의
`nodes + edges + 근거 + 검증 상태` 방식으로 구조화된 산출물로 끌어올린다.

```ts
// relations.jsonl — 1행 1엣지
interface ApiRelation {
  id: string;
  source: string;            // service_id ({source}:{api_id})
  target: string;
  type: "same-agency"        // 같은 제공기관
      | "same-domain"        // 같은 분류체계
      | "param-overlap"      // 요청 파라미터 공유 (예: 둘 다 사업자등록번호)
      | "io-chain"           // A의 응답 필드 → B의 요청 파라미터 (조합의 핵심)
      | "llm-suggested";     // combiner가 제안한 관계
  evidence: string[];        // 근거 필드명·값 (korea100의 법령 인용에 대응)
  confidence: number;        // 0~1
  status: "derived" | "llm-suggested" | "reviewed";  // 기계생성 / LLM 제안 / 사람 검수
  generatedAt: string;       // YYYY-MM-DD
}
```

- **관계 빌더는 nara_search에 둔다** (apidata와 카탈로그를 이미 소유).
  `swagger_json`의 요청/응답 필드를 비교해 `param-overlap`, `io-chain`을 빌드 타임에
  프리컴퓨트하고 `relations.jsonl`로 저장한다.
- `GET /relations?ids=...` API로 노출한다.
- korea100의 "지어내지 않기" 원칙: 기계 도출(`derived`)과 LLM 제안(`llm-suggested`)을
  절대 섞지 않고 `status`로 구분해 UI까지 전달한다.
- `llm-suggested` 엣지는 런타임에 combiner 응답에서 생성되어 UI에만 표시하며,
  프리컴퓨트 산출물 `relations.jsonl`에는 `derived` 엣지만 기록한다. LLM 제안의
  영속 저장(사람 검수 후 `reviewed` 승격)은 후속 후보다.

## 5. 아키텍처

```
[nara_crawler]  ──apidata/*.json──►  [nara_search]
 (데이터 공급 파이프라인)              ├─ FAISS 검색 (기존)
                                      ├─ 상세조회 (기존 계획대로 수리)
                                      ├─ 관계 빌더 → relations.jsonl  (신규)
                                      └─ GET /relations API           (신규)
                                              │
                [nara_dashboard]  ◄───────────┤
                 ├─ 자연어 질의 바 (신규)
                 ├─ 검색결과 → 노드 자동 배치 (신규)
                 ├─ 근거 엣지 자동 표시 (신규)
                 └─ 조합 제안 패널 ──────► [nara_combiner]
                                            └─ POST /compose (기존)
```

### 프로젝트별 변경 범위

- **nara_dashboard (제품의 얼굴)**
  - 상단 자연어 질의 바 추가. 질의 시 search `/search` 호출 → 결과 API 문서를 노드로
    캔버스에 자동 배치.
  - `/relations` 호출 → 노드 간 근거 엣지를 **점선(제안 상태)** 으로 표시. 엣지 클릭 시
    evidence 표시, 사용자가 승인하면 실선 워크플로우 엣지로 확정.
  - 선택한 노드들을 combiner `/compose`로 보내 조합 제안을 사이드 패널에 표시.
  - 현재 `apiDocs.js`의 apidata eager-bundle(번들 비대의 주범)을 search 백엔드 호출로
    대체. 백엔드 미기동 시 명확한 안내 배너 + 빈 카탈로그로 동작.
  - 기존 flow JSON 내보내기/가져오기는 유지.
- **nara_search**: 관계 빌더와 `/relations` 추가. 그 외에는 기존 계획(상세조회 수리,
  config·loader 정리, 테스트 추가)을 그대로 수행.
- **nara_combiner**: 변경 최소. 관계 엣지 컨텍스트를 compose 요청에 함께 넘겨 제안
  품질을 올리는 것은 후속 후보.
- **nara_crawler**: 변경 없음. 재현 가능한 apidata 수집만 유지.

## 6. 사용자 데이터 흐름 (E2E 시나리오)

1. 사용자: "부모님 병원 이동을 지원받으려면?" 입력
2. dashboard → search `/search` → 상위 N개 API 문서 노드 배치
3. dashboard → search `/relations?ids=...` → 노드 간 근거 엣지(점선) 표시
4. 사용자가 엣지 근거 확인·승인, 노드 선택(예: 3개) → combiner `/compose` →
   조합 제안 사이드 패널 표시
5. 완성된 워크플로우는 flow JSON 내보내기로 저장·공유

## 7. 오류 처리

- search 미기동: 질의 바에 연결 오류 배너, 앱은 죽지 않음
- relations 데이터 없음: 엣지 없이 노드만 표시 (기능 저하 모드)
- combiner LLM 실패: 패널에 오류 표시, 캔버스의 워크플로우는 유지
- 잘못된/미존재 service_id: search 기존 계획의 4xx 구분을 따름

## 8. 완성 기준

- 스크립트 하나로 search + combiner + dashboard 기동
- 6장의 E2E 시나리오가 고정 fixture로 재현 가능
- 관계 빌더 단위 테스트 통과 (param-overlap, io-chain 도출 검증)
- dashboard 기존 테스트 유지 + 백엔드 연동 모드 테스트 추가
- README와 `plan unified.md` 대체본 갱신 완료

## 9. 범위 밖 (이번 설계에서 하지 않는 것)

- 공개 배포·호스팅 (로컬 완성 후 별도 결정)
- 실행 기능 일체 (openclaw 아카이브와 함께 보류)
- gov24 링크 데이터셋 활용 (아카이브와 함께 보류)
- korea100 자체의 변경
- crawler 기능 확장
- 중앙 DB/graph DB 도입, 단일 인증 체계
