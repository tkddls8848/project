"""
Neo4j 서비스 패키지

1,256줄의 God Object를 6개의 전문 서비스로 분해:
- ConnectionManager: 연결 풀 관리
- DocumentRepository: 문서 CRUD
- GraphExplorer: 그래프 탐색
- PathFinder: 경로 찾기
- RelationshipManager: 사용자 정의 관계 CRUD
- RelationshipSuggester: AI 기반 관계 추천
"""

from app.services.neo4j.connection_manager import Neo4jConnectionManager, connection_manager
from app.services.neo4j.document_repository import DocumentRepository
from app.services.neo4j.graph_explorer import GraphExplorer
from app.services.neo4j.path_finder import PathFinder
from app.services.neo4j.relationship_manager import RelationshipManager
from app.services.neo4j.relationship_suggester import RelationshipSuggester

__all__ = [
    "Neo4jConnectionManager",
    "connection_manager",
    "DocumentRepository",
    "GraphExplorer",
    "PathFinder",
    "RelationshipManager",
    "RelationshipSuggester",
]
