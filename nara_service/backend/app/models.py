"""Pydantic 모델 정의"""
from pydantic import BaseModel, Field, validator
from typing import Optional


class QueryRequest(BaseModel):
    message: str = Field(..., max_length=1000)
    llm_type: str = "ollama"  # "openai" 또는 "ollama"

    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('Message cannot be empty')
        return v


class QueryResponse(BaseModel):
    message: str
    relevant_documents: list = []
    total_documents: int = 0


class FeedbackRequest(BaseModel):
    query: str
    response: str
    feedback: str  # "like" 또는 "dislike"
    llm_type: str
    timestamp: str
    user: str = ""


class FeedbackResponse(BaseModel):
    status: str
    message: str
    total_feedbacks: int


class PrometheusChatRequest(BaseModel):
    query: str
    context_docs: list
    relationships: list = []
    llm_type: str = "ollama"


class PrometheusBase(BaseModel):
    name: str
    nodes: list
    edges: list
    user_id: str


class PrometheusCreateRequest(PrometheusBase):
    pass


class PrometheusUpdateRequest(BaseModel):
    name: str | None = None
    nodes: list | None = None
    edges: list | None = None


class PrometheusResponse(PrometheusBase):
    id: str
    created_at: str
    updated_at: str


class PrometheusListResponse(BaseModel):
    prometheuss: list[PrometheusResponse]
    total: int


# ============ Graph Exploration Models ============

class GraphNode(BaseModel):
    """그래프 노드 모델 (Document, Keyword, Category, Provider)"""
    id: str
    label: str  # 노드의 display name
    type: str   # "Document", "Keyword", "Category", "Provider"
    properties: dict


class GraphEdge(BaseModel):
    """그래프 엣지 모델 (관계)"""
    id: str
    source: str
    target: str
    type: str   # "HAS_KEYWORD", "PROVIDED_BY", "BELONGS_TO"
    label: str  # 한글 표시용 (예: "키워드", "제공기관")


class GraphExploreResponse(BaseModel):
    """그래프 탐색 응답 모델"""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    center_node: str


class GraphSummaryResponse(BaseModel):
    """그래프 통계 요약 응답 모델"""
    stats: dict
    top_keywords: list[dict]
    top_providers: list[dict]
    top_categories: list[dict]


class GraphExploreRequest(BaseModel):
    """그래프 탐색 요청 모델"""
    doc_id: str = Field(..., min_length=1, description="문서 ID")
    depth: int = Field(2, ge=0, le=3, description="탐색 깊이 (0-3)")
    limit: int = Field(100, ge=1, le=500, description="최대 노드 개수")


class PathFindRequest(BaseModel):
    """최단 경로 탐색 요청 모델"""
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)


class PathFindResponse(BaseModel):
    """최단 경로 탐색 응답 모델"""
    path: list[GraphNode]
    relationships: list[GraphEdge]
    insights: str


# ==========================================
# Custom Relationship Models (Phase 3)
# ==========================================

class RelationshipCreate(BaseModel):
    """사용자 정의 관계 생성 요청 모델"""
    source_id: str = Field(..., min_length=1, description="시작 문서 ID")
    target_id: str = Field(..., min_length=1, description="대상 문서 ID")
    custom_type: str = Field(..., min_length=1, description="관계 타입 (예: '비교', '참고', '연관')")
    description: str = Field(..., min_length=1, description="관계 설명")
    strength: Optional[float] = Field(None, ge=0.0, le=1.0, description="관계 강도 (0.0 - 1.0)")

    @validator('source_id', 'target_id', 'custom_type', 'description')
    def validate_not_empty(cls, v):
        """빈 문자열 및 공백 검증"""
        if not v or not v.strip():
            raise ValueError('Field cannot be empty or whitespace')
        return v.strip()

    @validator('target_id')
    def validate_different_ids(cls, v, values):
        """source_id와 target_id가 다른지 검증"""
        if 'source_id' in values and v == values['source_id']:
            raise ValueError('Source and target must be different documents')
        return v


class RelationshipUpdate(BaseModel):
    """사용자 정의 관계 수정 요청 모델"""
    custom_type: Optional[str] = Field(None, min_length=1, description="관계 타입")
    description: Optional[str] = Field(None, min_length=1, description="관계 설명")
    strength: Optional[float] = Field(None, ge=0.0, le=1.0, description="관계 강도")


class RelationshipResponse(BaseModel):
    """사용자 정의 관계 응답 모델"""
    id: str
    source_id: str
    source_title: str
    target_id: str
    target_title: str
    custom_type: str
    description: str
    strength: Optional[float] = None
    created_by: str
    created_at: str


class RelationshipListResponse(BaseModel):
    """사용자 정의 관계 목록 응답 모델"""
    relationships: list[RelationshipResponse]
    total: int


class RelationshipSuggestion(BaseModel):
    """AI 관계 추천 모델"""
    target_doc: dict = Field(..., description="추천 대상 문서 정보")
    suggested_type: str = Field(..., description="추천 관계 타입 (보완, 유사, 인과 등)")
    reason: str = Field(..., description="추천 이유 설명")
    confidence: float = Field(..., ge=0.0, le=1.0, description="추천 신뢰도 (0.0 - 1.0)")
    common_keywords: list[str] = Field(default=[], description="공통 키워드 목록")
    common_category: Optional[str] = Field(None, description="공통 카테고리")
    common_provider: Optional[str] = Field(None, description="공통 제공기관")


class RelationshipSuggestionsResponse(BaseModel):
    """AI 관계 추천 목록 응답 모델"""
    doc_id: str = Field(..., description="기준 문서 ID")
    suggestions: list[RelationshipSuggestion] = Field(..., description="추천 목록")
    total: int = Field(..., description="총 추천 개수")


# ==========================================
# Advanced Insights Models (Phase 4)
# ==========================================

class RelationshipChainsRequest(BaseModel):
    """관계 체인 발견 요청 모델"""
    doc_id: str = Field(..., min_length=1, description="기준 문서 ID")
    min_chain_length: int = Field(1, ge=1, le=6, description="최소 체인 길이")
    max_chain_length: int = Field(6, ge=1, le=6, description="최대 체인 길이")
    limit: int = Field(50, ge=1, le=50, description="최대 결과 개수")

    @validator('max_chain_length')
    def validate_chain_length(cls, v, values):
        min_length = values.get('min_chain_length', 1)
        if v < min_length:
            raise ValueError('max_chain_length must be >= min_chain_length')
        return v


class RelationshipChain(BaseModel):
    """관계 체인 모델"""
    chain_id: str = Field(..., description="체인 고유 ID")
    nodes: list[dict] = Field(..., description="체인의 문서 노드 목록")
    relationships: list[dict] = Field(..., description="체인의 관계 목록")
    length: int = Field(..., description="체인 길이 (관계 개수)")
    chain_types: list[str] = Field(..., description="체인에 포함된 관계 타입 목록")
    insight: str = Field(..., description="체인 분석 인사이트")


class RelationshipChainsResponse(BaseModel):
    """관계 체인 발견 응답 모델"""
    doc_id: str = Field(..., description="기준 문서 ID")
    chains: list[RelationshipChain] = Field(..., description="발견된 관계 체인 목록")
    total: int = Field(..., description="총 체인 개수")


class HiddenConnection(BaseModel):
    """숨겨진 연결 모델"""
    source_doc: dict = Field(..., description="시작 문서 정보")
    target_doc: dict = Field(..., description="대상 문서 정보")
    intermediate_nodes: list[dict] = Field(..., description="중간 매개 노드 목록")
    connection_strength: float = Field(..., ge=0.0, le=1.0, description="연결 강도")
    common_attributes: dict = Field(..., description="공통 속성 (키워드, 카테고리 등)")
    suggested_relationship: str = Field(..., description="제안 관계 타입")
    reason: str = Field(..., description="연결 이유 설명")


class HiddenConnectionsRequest(BaseModel):
    """숨겨진 연결 발견 요청 모델"""
    doc_id: str = Field(..., min_length=1, description="기준 문서 ID")
    limit: int = Field(50, ge=1, le=50, description="최대 결과 개수")


class HiddenConnectionsResponse(BaseModel):
    """숨겨진 연결 발견 응답 모델"""
    doc_id: str = Field(..., description="기준 문서 ID")
    connections: list[HiddenConnection] = Field(..., description="발견된 숨겨진 연결 목록")
    total: int = Field(..., description="총 연결 개수")


class Community(BaseModel):
    """커뮤니티 모델"""
    community_id: int = Field(..., description="커뮤니티 ID")
    nodes: list[dict] = Field(..., description="커뮤니티 소속 노드 목록")
    size: int = Field(..., description="커뮤니티 크기 (노드 개수)")
    dominant_category: Optional[str] = Field(None, description="주요 카테고리")
    dominant_provider: Optional[str] = Field(None, description="주요 제공기관")
    common_keywords: list[str] = Field(default=[], description="공통 키워드")
    description: str = Field(..., description="커뮤니티 설명")


class CommunitiesRequest(BaseModel):
    """커뮤니티 탐지 요청 모델"""
    min_size: int = Field(2, ge=2, le=20, description="커뮤니티 최소 크기")


class CommunitiesResponse(BaseModel):
    """커뮤니티 탐지 응답 모델"""
    communities: list[Community] = Field(..., description="발견된 커뮤니티 목록")
    total_communities: int = Field(..., description="총 커뮤니티 개수")
    modularity: float = Field(..., description="모듈성 점수 (커뮤니티 품질)")


class NodeCentrality(BaseModel):
    """노드 중심성 모델"""
    node_id: str = Field(..., description="노드 ID")
    node_title: str = Field(..., description="노드 제목")
    node_type: str = Field(..., description="노드 타입")
    degree_centrality: float = Field(..., description="연결 중심성")
    betweenness_centrality: float = Field(..., description="매개 중심성")
    pagerank: float = Field(..., description="PageRank 점수")
    importance_score: float = Field(..., description="종합 중요도 점수")


class CentralityAnalysisResponse(BaseModel):
    """중심성 분석 응답 모델"""
    top_nodes: list[NodeCentrality] = Field(..., description="상위 중요 노드 목록")
    total_analyzed: int = Field(..., description="분석된 총 노드 개수")
    insights: str = Field(..., description="분석 인사이트")


class ComplementaryData(BaseModel):
    """보완 데이터 추천 모델"""
    doc_id: str = Field(..., description="추천 문서 ID")
    title: str = Field(..., description="문서 제목")
    category: str = Field(..., description="카테고리")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="관련성 점수")
    gap_filled: str = Field(..., description="채워지는 지식 갭")
    reason: str = Field(..., description="추천 이유")


class ComplementaryDataResponse(BaseModel):
    """보완 데이터 추천 응답 모델"""
    doc_id: str = Field(..., description="기준 문서 ID")
    recommendations: list[ComplementaryData] = Field(..., description="보완 데이터 추천 목록")
    total: int = Field(..., description="총 추천 개수")
    coverage_analysis: dict = Field(..., description="현재 커버리지 분석")


# ==========================================
# Relationship Chat Models (NotebookLM Style)
# ==========================================

class ChatMessage(BaseModel):
    """채팅 메시지 모델"""
    role: str = Field(..., description="메시지 역할 (user/assistant)")
    content: str = Field(..., description="메시지 내용")

class RelationshipChatRequest(BaseModel):
    """관계 채팅 요청 모델 - N개 문서 지원"""
    documents: list[dict] = Field(..., description="분석할 문서 목록 (2개 이상)")
    messages: list[ChatMessage] = Field(default_factory=list, description="이전 대화 히스토리")
    query: str = Field(..., min_length=1, description="사용자 질문")

    @validator('documents')
    def validate_documents(cls, v):
        if len(v) < 2:
            raise ValueError('At least 2 documents are required')
        return v

    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()

class RelationshipChatResponse(BaseModel):
    """관계 채팅 응답 모델"""
    response: str = Field(..., description="AI 응답")
    context_used: dict = Field(..., description="사용된 컨텍스트 정보")
