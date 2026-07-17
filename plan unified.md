# Nara 통합 제품 계획

- 기준일: 2026-07-16
- 설계 근거: docs/superpowers/specs/2026-07-16-subproject-consolidation-design.md
- 이 문서는 이전의 "서브프로젝트 독립 개발 계획"을 대체한다.

## 목표

자연어 질의 → 관련 공공 API 문서 검색 → 문서 노드 간 연결관계(근거 포함) 연출 →
조합 제안으로 새로운 결과 도출. korea100을 벤치마크한다:
완성 우선 태도, 근거 있는 관계 데이터 계약, 사용자 관점의 단일 웹 제품.

배포 범위는 우선 로컬 완성품이다. 호스팅·공개 배포는 완성 후 별도 결정한다.

## 프로젝트 구성

| 프로젝트 | 역할 |
| --- | --- |
| `nara_dashboard(API관계대시보드)` | 제품의 얼굴 — 자연어 질의 바, 노드 캔버스, 관계 엣지, 조합 제안 패널 |
| `nara_search(API문서검색)` | 검색·상세·카탈로그·관계(derived) API |
| `nara_combiner(API문서조합기)` | LLM 조합 제안 API (변경 최소) |
| `nara_crawler(API문서크롤러)` | apidata 공급 파이프라인 (변경 없음) |
| `korea100` | 독립 유지 — 벤치마크 대상 |

## 보류 (archive/)

- `archive/nara_openclaw(행정서비스실행기)` — 실행 기능 일체는 범위 밖
- `archive/nara_gov24_link_resolver(정부24서비스링크매핑)` — 링크 데이터셋은 범위 밖

보류 프로젝트는 유지보수하지 않는다. 재개 여부는 통합 제품 완성 후 판단한다.

## 완성 기준

- `start-all.ps1` 하나로 search + combiner + dashboard 기동
- E2E 시나리오(질의→노드→관계 엣지→조합 제안)가 고정 fixture 테스트로 재현
- 관계 빌더·백엔드 연동 테스트 포함 전체 테스트 통과
