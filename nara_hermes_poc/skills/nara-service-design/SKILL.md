---
name: nara-service-design
description: 공공 API 문서를 검색·검토하고 근거 있는 행정 서비스 계획을 작성한다
version: 0.1.0
platforms: [windows, linux]
metadata:
  hermes:
    category: public-service
    requires_toolsets: [mcp-nara]
---

# Nara Service Design

## When to Use

사용자가 여러 공공 API를 찾아 연결하거나 행정 서비스 계획을 만들고 싶을 때
사용한다. 실제 행정 처리나 외부 API 실행 요청에는 사용하지 않는다.

## Procedure

1. 사용자의 목적, 대상자, 필요한 결과를 짧게 정리한다.
2. `search_api_docs`로 하이브리드 검색을 실행한다.
3. 결과가 비어 있거나 의미적으로 동떨어지면 `use_vector=false`로 다시 검색한다.
4. 후보마다 `get_api_detail`을 호출해 설명과 입력·출력 필드를 확인한다.
5. 근거가 충분한 API만 최대 세 개 선택한다.
6. 두 개 이상이면 `derive_relations`로 관계 근거를 확인한다.
7. 관계가 없으면 억지로 연결하지 말고 독립 단계라고 명시한다.
8. `compose_service_plan`으로 계획 초안을 만든다.
9. 결과에 사용한 service_id, 관계 근거, 누락 문서, 실행되지 않았다는 사실을 적는다.

## Safety

- 검색 결과에 없는 API나 필드를 만들어내지 않는다.
- 도구가 반환한 ID와 근거를 그대로 추적 가능하게 남긴다.
- 개인정보, 인증정보, 민원 원문을 메모리나 스킬에 저장하지 않는다.
- 이 PoC는 계획만 작성한다. 실제 API 호출이나 행정 처리를 완료했다고 말하지 않는다.
- 스킬 또는 메모리 변경은 사용자 승인을 받은 뒤 반영한다.

## Pitfalls

- 벡터 점수만 보고 문서를 선택하지 않는다.
- API 이름이 비슷하다는 이유만으로 관계가 있다고 판단하지 않는다.
- 조합기의 자연어 제안을 API 명세보다 우선하지 않는다.
- 찾지 못한 문서를 임의의 대체 문서로 바꾸지 않는다.

## Verification

- 선택한 모든 문서에 실제 `service_id`가 있는가?
- 각 문서의 상세 조회가 성공했는가?
- 관계 주장이 `derive_relations` 결과에 의해 뒷받침되는가?
- 조합 결과가 실제 실행이 아닌 계획 초안으로 표시되었는가?
- 누락·경고·불확실성이 최종 답변에 포함되었는가?

