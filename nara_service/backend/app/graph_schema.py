"""
Neo4j Graph Schema Definitions
프로젝트의 질을 결정하는 관계(Relationship) 및 노드(Node) 구조를 정의하는 파일입니다.
사용자가 직접 관계 설정을 변경할 수 있도록 별도로 분리되었습니다.
"""

# ==========================================
# 1. Node Labels (노드 라벨)
# ==========================================
class NodeLabel:
    DOCUMENT = "Document"       # 개별 데이터 파일 (예: '울진군_어린이집_현황')
    KEYWORD = "Keyword"         # 메타데이터 키워드 (예: '육아', '보육')
    PROVIDER = "Provider"       # 데이터 제공 기관 (예: '경상북도 울진군')
    CATEGORY = "Category"       # 데이터 분류 (예: '사회복지')
    
    # 향후 확장 가능성 (예: 지역, 파일형식 등)
    # REGION = "Region"
    # FILE_FORMAT = "FileFormat"


# ==========================================
# 2. Relationship Types (관계 타입)
# ==========================================
class RelationType:
    # Document -> Metadata (시스템 자동 생성)
    HAS_KEYWORD = "HAS_KEYWORD"     # 문서가 해당 키워드를 포함함
    PROVIDED_BY = "PROVIDED_BY"     # 문서가 해당 기관에 의해 제공됨
    BELONGS_TO = "BELONGS_TO"       # 문서가 해당 카테고리에 속함

    # Document -> Document (사용자 정의 관계)
    CUSTOM_RELATED_TO = "CUSTOM_RELATED_TO"  # 사용자가 직접 정의한 문서 간 관계

    # Metadata -> Metadata (향후 확장)
    # RELATED_TO = "RELATED_TO"     # 키워드 간 연관성
    # PART_OF = "PART_OF"           # 기관의 상하 관계 (예: 울진군 -> 경상북도)


# ==========================================
# 3. Property Keys (속성 키)
# ==========================================
class PropKey:
    # Common
    ID = "id"
    NAME = "name"
    CREATED_AT = "created_at"

    # Document Specific
    API_ID = "api_id"
    TITLE = "title"
    DESCRIPTION = "description"
    URL = "crawled_url"

    # Custom Relationship Specific
    CUSTOM_TYPE = "custom_type"        # 사용자 정의 관계 타입 (예: "비교", "참고", "연관")
    REL_DESCRIPTION = "description"    # 관계 설명
    CREATED_BY = "created_by"          # 생성자 (예: "user", "system", "ai")
    STRENGTH = "strength"              # 관계 강도 (0.0 - 1.0, 선택적)

    # Provider Specific
    # TYPE = "org_type" (지자체, 공공기관 등)


# ==========================================
# 4. Schema Constraints (제약 조건 - 참조용)
# ==========================================
# 실제 적용은 코드에서 수행하지만, 구조 파악을 위해 명시
CONSTRAINTS = [
    # (Label, Property) - Unique Key
    (NodeLabel.DOCUMENT, PropKey.API_ID),
    (NodeLabel.KEYWORD, PropKey.NAME),
    (NodeLabel.PROVIDER, PropKey.NAME),
    (NodeLabel.CATEGORY, PropKey.NAME),
]
