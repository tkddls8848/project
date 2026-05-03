"""
자동 관계 정의 설정 파일
문서 적재 시 자동으로 생성되는 관계들을 정의합니다.
이 파일을 수정하여 관계 구조를 변경할 수 있습니다.
"""

from typing import List, Dict, Any, Optional
from app.graph_schema import NodeLabel, RelationType, PropKey


class AutoRelationship:
    """자동 관계 정의 클래스"""

    def __init__(
        self,
        name: str,
        description: str,
        relationship_type: str,
        target_node_label: str,
        target_property: str,
        source_data_path: str,
        is_list: bool = False,
        create_target: bool = True,
        target_create_properties: Optional[List[str]] = None
    ):
        """
        Args:
            name: 관계 이름 (식별용)
            description: 관계 설명
            relationship_type: Neo4j 관계 타입 (예: "HAS_KEYWORD")
            target_node_label: 타겟 노드 라벨 (예: "Keyword")
            target_property: 타겟 노드의 키 속성 (예: "name")
            source_data_path: 소스 데이터에서 값을 가져올 경로 (예: "metadata.keywords")
            is_list: 소스 데이터가 리스트인지 여부
            create_target: 타겟 노드가 없으면 자동 생성할지
            target_create_properties: 타겟 노드 생성 시 추가할 속성들
        """
        self.name = name
        self.description = description
        self.relationship_type = relationship_type
        self.target_node_label = target_node_label
        self.target_property = target_property
        self.source_data_path = source_data_path
        self.is_list = is_list
        self.create_target = create_target
        self.target_create_properties = target_create_properties or []

    def get_value_from_data(self, doc_data: Dict[str, Any]) -> Any:
        """
        중첩된 딕셔너리에서 값을 추출
        예: "metadata.keywords" -> doc_data["metadata"]["keywords"]
        """
        keys = self.source_data_path.split('.')
        value = doc_data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

        return value

    def generate_cypher_fragment(self) -> str:
        """
        이 관계를 생성하는 Cypher 쿼리 조각 생성
        """
        if self.is_list:
            # 리스트 처리: FOREACH 사용
            return f"""
        // {self.description}
        FOREACH (item IN $_{self.name}_value |
            MERGE (target:{self.target_node_label} {{ {self.target_property}: item }})
            MERGE (d)-[:{self.relationship_type}]->(target)
        )
            """
        else:
            # 단일 값 처리
            return f"""
        // {self.description}
        MERGE (target_{self.name}:{self.target_node_label} {{ {self.target_property}: $_{self.name}_value }})
        MERGE (d)-[:{self.relationship_type}]->(target_{self.name})
            """


# ========================================
# 자동 관계 정의
# ========================================

AUTO_RELATIONSHIPS = [
    AutoRelationship(
        name="provider",
        description="문서 제공 기관 관계",
        relationship_type=RelationType.PROVIDED_BY,
        target_node_label=NodeLabel.PROVIDER,
        target_property=PropKey.NAME,
        source_data_path="metadata.provider",
        is_list=False
    ),

    AutoRelationship(
        name="category",
        description="문서 카테고리 관계",
        relationship_type=RelationType.BELONGS_TO,
        target_node_label=NodeLabel.CATEGORY,
        target_property=PropKey.NAME,
        source_data_path="metadata.category",
        is_list=False
    ),

    AutoRelationship(
        name="keywords",
        description="문서 키워드 관계",
        relationship_type=RelationType.HAS_KEYWORD,
        target_node_label=NodeLabel.KEYWORD,
        target_property=PropKey.NAME,
        source_data_path="metadata.keywords",
        is_list=True
    ),
]


# ========================================
# 헬퍼 함수
# ========================================

def get_relationship_parameters(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    문서 데이터에서 모든 자동 관계의 파라미터 추출
    """
    params = {}

    for rel in AUTO_RELATIONSHIPS:
        value = rel.get_value_from_data(doc_data)

        # 기본값 처리
        if value is None:
            if rel.is_list:
                value = []
            else:
                value = "Unknown"

        params[f"_{rel.name}_value"] = value

    return params


def generate_full_cypher_query() -> str:
    """
    모든 자동 관계를 생성하는 전체 Cypher 쿼리 생성
    """
    base_query = f"""
    MERGE (d:{NodeLabel.DOCUMENT} {{ {PropKey.API_ID}: $api_id }})
    ON CREATE SET
        d.{PropKey.TITLE} = $title,
        d.{PropKey.DESCRIPTION} = $description,
        d.{PropKey.URL} = $url,
        d.{PropKey.CREATED_AT} = datetime()
    ON MATCH SET
        d.{PropKey.TITLE} = $title,
        d.{PropKey.DESCRIPTION} = $description,
        d.{PropKey.URL} = $url
    """

    # 모든 자동 관계의 Cypher 조각 결합
    relationship_fragments = [rel.generate_cypher_fragment() for rel in AUTO_RELATIONSHIPS]

    return base_query + "\n".join(relationship_fragments)


# ========================================
# 사용 예시 (주석)
# ========================================
"""
# 새로운 자동 관계 추가 방법:

AUTO_RELATIONSHIPS.append(
    AutoRelationship(
        name="region",
        description="문서 지역 관계",
        relationship_type="LOCATED_IN",
        target_node_label="Region",
        target_property="name",
        source_data_path="metadata.region",
        is_list=False
    )
)

# 리스트 타입 관계 추가 예시:

AUTO_RELATIONSHIPS.append(
    AutoRelationship(
        name="tags",
        description="문서 태그 관계",
        relationship_type="TAGGED_WITH",
        target_node_label="Tag",
        target_property="name",
        source_data_path="metadata.tags",
        is_list=True  # 리스트 처리
    )
)
"""
