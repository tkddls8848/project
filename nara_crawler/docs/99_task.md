llm api키를 사용자가 직접 생성하고 입력하게 한다? 내가 내 크레딧 쓰고 싶지 않다. 아직은

과거 인디아 프로젝트 참고? (일정, 채팅, 기록 등등)

index.json은 내가보는 공공데이터에 대한 시각과 문제의식이 담긴 문학문으로 접근해야한다. 데이터 범주를 내가 적절히 태깅해줘야 특별한 rag서비스를 제공한다.

https://www.piku.co.kr/ 아이디어?

파일별 불필요한 부분 직접 검수 필요

크롤링 데이터의 <br>, 쿼리 답변에 대한 html 태그나 특수문자 처리 필요

4가지 데이터 타입 일괄 규격으로 정제
- standard 타입에 대한 엔트포인트 별 상세 쿼리스트링에 대한 api "파라미터=값"요청시 요청에 맞는 json 리턴 구현. 엔드포인트 2개 만들었다 getAll, getEach. getEach에 대한 문서내 특정 오브젝트 검색 기능 검토 필요요
- general, swagger, fileData, link 완료
- 백엔드에서 엔드포인트 별 일일히 다 라우트 만들고 구현하고 있는데 엔드포인트 파라미터 받아서 내부에서 알아서 처리할 수 있도록 해야 함
- 디테일 페이지 표시 내용 다듬기 필요

계정 가입 및 정보보안 기본적, 개인화 장기기억 정보
브라우저 익스텐션으로 응용? openwebui?


"search_context":  전략 구현 필요
search_context전략 관련 MCP 사용?
scale ai 데이터 태깅 비즈니스 모델 alexander wang
  "operation_ids": [],
  "data": []

파알데이터 형식에 다운로드 링크 걍 json에 박기

이 사이트가 사람들이 원하는 민원행정처리에 도움될까

https://www.data.go.kr/iim/api/selectAcountList.do 여기 페이지는 내가 크롤링한 모든 개별문서마다 사용 승인권한을 관리하는페이지다 매년 갱신 신청을 해야하는데 문제는 문서가 수만개인데 내가 직접할수 없다 자동화하는코드 생성가능할까

지금 프로젝트에는 api/엔드포인트로 데이터 받을 수 있도록 api인터페이스가 설계되어있다. 보안위협은 있는가

1. 인증/인가 없음
2. 공개된 API 키 노출 위험
3. CORS 설정 과도하게 개방
4. Rate Limiting 없음
5. 입력 검증 부족

swagger 명세 공개 위험

리프레시 및 등록 프로세스

백엔드 직접 API 없이 프론트에서 api 프록시

과금모델은 소정의 돈과 사용자에게 아주 특이하고 독특한 글이나 컨텍스트 같은 컨텐츠를 받는 것?

데이터 크롤링 후 정제 및 키워드, 디스크립션의 연출이 매우 중요하다.

https://www.mermaidchart.com/pricing 을 참고할까? 가격 그레이드가 높아지면서 보안쪽 기능이 필요하고 만약 이 서비스가 확장한다면 그 때 해당 개발자 필요하겠지?

채팅그룹 대시보드에 대한 개인 저장, 채팅기록에 대한 저장?

뭔가 사이트 전반적으로 이런 구도가 좋을까?
https://www.google.com/search?q=&sourceid=chrome&ie=UTF-8&udm=50&aep=48&cud=0&qsubts=1765700849491

neo4j 사용법 숙지 필요
현재 메인 페이지의 핵심 검색 기능은 Neo4j 없이 FAISS만으로 동작하며, Neo4j는 검색 결과를 풍부하게 만드는 부가 기능(Related Documents & Context Insights)으로만 사용되고 있습니다. 
  결론: `/prometheus`에서는 현재 Neo4j를 사용하지 않습니다.

  코드를 분석한 결과는 다음과 같습니다:

   1. 문서 검색 (`/prometheus/search`):
       * rag_service.search() 메서드를 호출합니다.
       * 앞서 확인했듯이, 이 메서드는 FAISS(벡터 검색)만 사용하며 Neo4j를 통한 관계 검색(search_with_relations)은 수행하지 않습니다.

   2. 채팅 (`/prometheus/chat`):
       * rag_service.generate_response() 메서드를 사용하여 응답을 생성합니다.
       * 이때 클라이언트(프론트엔드)에서 보내준 context_docs와 relationships를 그대로 사용합니다.
       * 서버 측에서 Neo4j를 조회하여 관계 정보를 추가로 가져오는 로직은 이 엔드포인트에 포함되어 있지 않습니다.

2.  Neo4j 적재 후 일괄 처리
    크롤링 시에는 키워드 생성 스킵 → 모든 데이터를 Neo4j에 적재 후 → 배치 스크립트로 모든 문서의 키워드를 그래프 기반으로 생성. 전체 그래프 정보 활용 가능하지만 워크플로우 변경 필요

나만의 데이터 정의 및 혼합

3개 이상의 문서 및 계층관계 추가

사용자 페르소나

대시보드 다중 노드 연결에 문제있다. 한노드가 여러 노드의 소스 혹은 타겟이 되지 못하고 있다.

메인페이지와 rag 검색 search페이지는 결국 하나로 통합되야 한다. 메인페이지 검색 창은 api 문서에 대해 rag를 search는 청크된 데이터에 대한 rag를 하고 있으니까

네이버 기사 연관 API 완전 딴판 (기사 keywords와 API keyword를 유사 관계 비교하게 수정?)

https://github.com/yeongseon/kpubdata
https://github.com/StatPan/kr-data-portal-client
프로젝트 참고하여 서비스 돌리는 하위 api 래퍼 혹은 프로바이더로 활용