"""
문서 간 상하위 위계 관계 타입 정의
"""

from enum import Enum
from typing import Dict, List


class HierarchyRelationType(str, Enum):
    """위계 관계 타입"""
    PARENT_OF = "PARENT_OF"  # 상위 문서
    CHILD_OF = "CHILD_OF"  # 하위 문서
    INCLUDES = "INCLUDES"  # 포함


# 위계 관계 메타데이터
HIERARCHY_METADATA: Dict[str, Dict] = {
    "PARENT_OF": {
        "name": "상위 문서",
        "description": "이 문서는 대상 문서의 상위 개념/정책입니다",
        "direction": "down",  # 상위에서 하위로
        "inverse": "CHILD_OF",
        "examples": ["총괄 정책 → 세부 정책", "법률 → 시행령"]
    },
    "CHILD_OF": {
        "name": "하위 문서",
        "description": "이 문서는 대상 문서의 하위 개념/세부사항입니다",
        "direction": "up",  # 하위에서 상위로
        "inverse": "PARENT_OF",
        "examples": ["세부 지침 → 상위 정책", "시행규칙 → 법률"]
    },
    "INCLUDES": {
        "name": "포함",
        "description": "이 문서는 대상 문서를 포함합니다",
        "direction": "down",
        "inverse": "INCLUDED_IN",
        "examples": ["종합 보고서 → 부분 보고서", "전체 계획 → 세부 항목"]
    }
}


def get_hierarchy_types() -> List[Dict]:
    """위계 관계 타입 목록 반환 (API 응답용)"""
    return [
        {
            "id": rel_type,
            "name": metadata["name"],
            "description": metadata["description"],
            "direction": metadata["direction"],
            "examples": metadata["examples"]
        }
        for rel_type, metadata in HIERARCHY_METADATA.items()
    ]


def get_inverse_relation(rel_type: str) -> str:
    """역방향 관계 타입 반환"""
    if rel_type in HIERARCHY_METADATA:
        return HIERARCHY_METADATA[rel_type]["inverse"]
    return rel_type
