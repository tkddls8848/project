from typing import List, Dict, Any

def flatten_documents(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    JSON 데이터의 중첩 구조를 평탄화하여 문서 리스트로 변환하는 순수 함수
    """
    documents = []
    # 각 카테고리(fileData, openapi_link, openapi_new, openapi_old)를 순회
    for category, items in data.items():
        # 각 카테고리 내의 ID별 항목을 순회
        for doc_id, doc_data in items.items():
            # 문서 객체 생성
            document = {
                "id": doc_id,
                "doc_id": doc_id,
                "api_id": doc_id,
                "api_type": category,  # fileData, openapi_old, openapi_new 등
                "category": category,
                "type": doc_data.get("type", ""),
                "title": doc_data.get("title", ""),
                "description": doc_data.get("description", ""),
                "url": doc_data.get("URL", ""),
                "org": doc_data.get("org", ""),
                "org_code": doc_data.get("org_code", ""),
                "keyword": doc_data.get("keyword", ""),
                "national_primary": doc_data.get("national_primary", ""),
                "provider": doc_data.get("org", ""),
                "keywords": doc_data.get("keyword", "").split(",") if doc_data.get("keyword") else [],
                "total_endpoints": len(doc_data.get("endpoints", [])),
            }
            documents.append(document)
    return documents

def create_search_text(doc: Dict[str, Any]) -> str:
    """
    문서 객체에서 검색용 텍스트를 생성하는 순수 함수
    """
    text_parts = [
        doc.get('title', ''),
        doc.get('description', ''),
        doc.get('keyword', ''),
        doc.get('org', '')
    ]
    return ' '.join(filter(None, text_parts))

def format_context_text(context_docs: List[Dict[str, Any]]) -> str:
    """
    컨텍스트 문서를 LLM 프롬프트용 텍스트로 포맷팅하는 순수 함수
    """
    return "\n\n".join([
        f"제목: {doc.get('title', 'N/A')}\n"
        f"설명: {doc.get('description', 'N/A')}\n"
        f"타입: {doc.get('type', 'N/A')}\n"
        f"URL: {doc.get('url', 'N/A')}\n"
        f"카테고리: {doc.get('category', 'N/A')}"
        for doc in context_docs
    ])

def format_relationships_text(relationships: List[str]) -> str:
    """
    관계 정보를 LLM 프롬프트용 텍스트로 포맷팅하는 순수 함수
    """
    if not relationships:
        return ""
    return "\n\n데이터 간 관계:\n" + "\n".join(f"- {rel}" for rel in relationships)
