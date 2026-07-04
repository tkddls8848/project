                                                                        
                                                                                                       
  # Nara MCP 적용 계획                                                                                 
                                                                                                       
  ## Summary                                                                                           
                                                                                                       
  - 기사 핵심은 MCP를 통해 LLM/IDE가 데이터 소스의 스키마, 조회, 업데이트, 운영 작업을 안전하게        
    호출하게 하는 것입니다. 참고: ITWorld 기사                                                         
    (https://www.itworld.co.kr/article/4184249/%EC%9E%90%EC%97%B0%EC%96%B4%EB%A1%9C-%EB%8D%B0%EC%9D%B4%ED%84%B0%EB%B2%A0%EC%9D%B4%EC%8A%A4%EB%A5%BC-%EC%A1%B0%EC%9E%91%ED%95%98%EB%8A%94-%EC%8B%9C%EB%8C%80-mcp-%EC%84%9C%EB%B2%84%EA%B0%80-%EC%97%B4.html)                                                          
                                                                                                       
  - 현재 repo는 RDBMS가 아니라 JSON 문서, FAISS 인덱스, Ollama, 실행 감사 JSON을 중심으로 동작합니다.  
  - 따라서 Supabase/Postgres/MongoDB 같은 DB MCP 서버 도입보다, 기존 Nara 기능을 MCP tools/resources   
    로 노출하는 것이 1순위입니다.                                                                      
                                                                                                       
  ## Key Changes                                                                                       
                                                                                                       
  - 새 nara_mcp 모듈을 추가해 MCP 서버를 구성합니다.                                                   
  - 우선 read-only 도구부터 제공합니다:                                                                
      - search_api_docs(query, top_k): nara_search의 FAISS 검색과 동일한 결과 반환                     
      - get_service_detail(service_id): API 문서 JSON에서 상세 정보 조회                               
      - compose_services(service_ids, question): nara_combiner의 조합 제안 호출                        
      - get_run_record(run_id): nara_openclaw 실행 감사 로그 조회                                      
                                                                                                       
  - write/execute 계열은 기본 비활성화합니다:                                                          
      - trigger_index_build                                                                            
      - execute_dry_run                                                                                
      - execute_with_approval                                                                          
                                                                                                       
  - MCP 설정 예시는 Claude/Codex/Cursor에서 붙일 수 있도록 JSON 형태로 문서화합니다.                   
                                                                                                       
  ## Not Recommended Now                                                                               
                                                                                                       
  - 기사에 나온 DB별 MCP 서버 중 바로 맞는 것은 많지 않습니다.                                         
  - Postgres/Supabase/MongoDB/Redis/BigQuery는 현재 repo의 주 저장소가 아니므로 도입 우선순위가 낮습   
    니다.                                                                                              
                                                                                                       
  - Pinecone은 FAISS를 외부 벡터 DB로 교체할 때만 검토합니다.                                          
  - Neo4j는 API 간 관계 그래프를 실제 DB로 저장하기 시작할 때 의미가 있습니다.                         
                                                                                                       
  ## Test Plan                                                                                         
                                                                                                       
  - MCP tool 단위 테스트:                                                                              
      - 검색어 입력 시 nara_search와 동일한 service 결과 반환                                          
      - 없는 service/run ID는 명확한 not found 오류 반환                                               
      - top_k, query 길이 검증                                                                         
                                                                                                       
  - 통합 테스트:                                                                                       
      - MCP client에서 search_api_docs 호출                                                            
      - 검색 결과 service ID를 compose_services에 넘겨 조합 제안 생성                                  
      - 실행 로그 JSON 조회 확인                                                                       
                                                                                                       
  - 보안 테스트:                                                                                       
      - 기본 설정에서 파일 쓰기, 인덱스 재빌드, 실행 제출이 호출되지 않음                              
      - 민감정보가 포함될 수 있는 run payload는 마스킹된 필드만 노출                                   
                                                                                                       
  ## Assumptions                                                                                       
                                                                                                       
  - v1은 로컬 개발용 MCP 서버입니다.                                                                   
  - 기본 정책은 read-only입니다.                                                                       
  - 기존 FastAPI 서비스와 데이터 파일 구조는 유지합니다.                                               
  - DB 제품 MCP 서버 도입은 나중에 저장소를 Postgres, MongoDB, Pinecone, Neo4j 등으로 옮길 때 재검토   
    합니다.                                                                                            
                                                                                                       
