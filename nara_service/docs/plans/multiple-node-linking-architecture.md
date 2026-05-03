# 다중 노드(3개 이상) 엮기 기능 아키텍처 문서

## 개요

Prometheus 대시보드에서 3개 이상의 문서(카드)를 선택하여 관계를 분석하고 인사이트를 탐색하는 기능의 전체 아키텍처를 설명합니다.

## 목차

1. [기능 개요](#기능-개요)
2. [프론트엔드 구조](#프론트엔드-구조)
3. [백엔드 구조](#백엔드-구조)
4. [데이터 흐름](#데이터-흐름)
5. [주요 컴포넌트 상세](#주요-컴포넌트-상세)

---

## 기능 개요

### 주요 기능

사용자는 대시보드에서 **2개 이상의 문서 노드**를 선택하여 다음 작업을 수행할 수 있습니다:

1. **Relationship 모드 (N개 문서)**
   - 목적: Google NotebookLM 스타일의 AI 대화형 관계 탐색
   - 선택 가능: 2개 이상의 문서
   - 기능: AI와 대화하며 문서 간 관계, 공통점, 차이점, 통합 활용 방안 탐색
   - 결과: 채팅 인터페이스로 인사이트 제공 (그래프 엣지 생성 안함)

2. **Hierarchy 모드 (2개 문서)**
   - 목적: 문서 간 상하위 위계 관계를 그래프에 시각적으로 표현
   - 선택 가능: 정확히 2개 문서 (원본 + 대상)
   - 기능: PARENT_OF, CHILD_OF, INCLUDES 관계 생성
   - 결과: 그래프에 hierarchy 엣지 추가

---

## 프론트엔드 구조

### 디렉토리 구조

```
nara_service/frontend/src/app/prometheus/
├── page.tsx                          # 메인 페이지, 전체 조율
├── types.ts                          # 공통 타입 정의
├── types/
│   └── hierarchyTypes.ts            # 위계 관계 타입 정의
├── hooks/
│   └── useRelationshipMode.ts       # N개 노드 선택 관리 Hook
├── components/
│   ├── RightSidebar.tsx             # 우측 사이드바 (모드 전환, 컨트롤)
│   ├── RelationshipChatModal.tsx    # N개 문서 AI 채팅 모달
│   └── HierarchyRelationshipModal.tsx  # 2개 문서 위계 관계 설정 모달
└── utils.ts
```

### 핵심 Hook: useRelationshipMode

**파일**: `hooks/useRelationshipMode.ts`

```typescript
interface RelationshipSelection {
  selectedNodes: GraphNodeData[];  // 선택된 노드 배열
}

export const useRelationshipMode = () => {
  const [selection, setSelection] = useState<RelationshipSelection>({
    selectedNodes: [],
  });

  // 노드 클릭 시 토글 방식으로 추가/제거
  const selectNodeForRelationship = useCallback((node: GraphNodeData) => {
    setSelection((prev) => {
      const isAlreadySelected = prev.selectedNodes.some(n => n.id === node.id);

      if (isAlreadySelected) {
        return {
          selectedNodes: prev.selectedNodes.filter(n => n.id !== node.id)
        };
      } else {
        return {
          selectedNodes: [...prev.selectedNodes, node]
        };
      }
    });
  }, []);

  return {
    selection,
    selectNodeForRelationship,
    clearSelection,
    canCreateRelationship: selection.selectedNodes.length >= 2,
  };
};
```

**특징**:
- N개 노드를 배열로 관리
- 토글 방식: 같은 노드 클릭 시 제거
- `canCreateRelationship`: 2개 이상일 때 true

---

### Interaction Mode 시스템

**파일**: `page.tsx:50`

```typescript
const [interactionMode, setInteractionMode] =
  useState<'path' | 'relationship' | 'hierarchy'>('path');
```

#### 모드별 동작

| 모드 | 선택 개수 | 목적 | 결과 |
|------|----------|------|------|
| **path** | 2개 (source, target) | 최단 경로 찾기 | 경로 하이라이트 |
| **relationship** | 2개 이상 | AI 관계 탐색 | 채팅 인사이트 |
| **hierarchy** | 2개 | 위계 관계 생성 | 그래프 엣지 추가 |

---

### 노드 클릭 처리 흐름

**파일**: `page.tsx:232-285`

```typescript
const onNodeClick = useCallback(
  (event: React.MouseEvent, node: AppNode) => {
    if (node.type === 'contextNode' && node.data.id) {
      setSelectedDocId(node.data.id);

      if (interactionMode === 'relationship' || interactionMode === 'hierarchy') {
        selectNodeForRelationship({
          id: node.id,
          label: node.data.title || node.id,
          type: 'Document',
          properties: node.data,
        });
      }
    }
  },
  [interactionMode, selectNodeForRelationship]
);
```

**흐름**:
1. 사용자가 노드 클릭
2. `interactionMode` 확인
3. relationship 또는 hierarchy 모드면 `selectNodeForRelationship()` 호출
4. Hook 내부에서 배열에 토글 방식으로 추가/제거

---

### RightSidebar UI

**파일**: `components/RightSidebar.tsx`

#### Relationship 모드 UI (269-360줄)

```typescript
{interactionMode === 'relationship' && (
  <div className="p-3 border-b border-border/50">
    <div className="text-xs font-semibold">Create Link</div>

    {/* 선택된 노드 표시 */}
    {relationshipSelection.selectedNodes[0] && (
      <Badge>From: {relationshipSelection.selectedNodes[0].label}</Badge>
    )}
    {relationshipSelection.selectedNodes[1] && (
      <Badge>To: {relationshipSelection.selectedNodes[1].label}</Badge>
    )}

    {/* AI 추천 목록 */}
    {relationshipSelection.selectedNodes.length === 1 && (
      <div>
        {aiRecommendations?.connections.map((conn, idx) => (
          <div onClick={() => selectNodeForRelationship(targetNode)}>
            {conn.target_doc.title}
          </div>
        ))}
      </div>
    )}

    {/* "Explore Relationship" 버튼 */}
    {canCreateRelationship && (
      <Button onClick={openRelationshipModal}>
        Explore Relationship
      </Button>
    )}
  </div>
)}
```

#### Hierarchy 모드 UI (208-266줄)

```typescript
{interactionMode === 'hierarchy' && (
  <div className="p-3 border-b border-border/50">
    <div className="text-xs font-semibold">위계 관계 설정</div>

    {/* 선택된 노드 표시 */}
    {relationshipSelection.selectedNodes[0] && (
      <Badge>원본: {relationshipSelection.selectedNodes[0].label}</Badge>
    )}
    {relationshipSelection.selectedNodes[1] && (
      <Badge>대상: {relationshipSelection.selectedNodes[1].label}</Badge>
    )}

    {/* "관계 설정" 버튼 */}
    {canCreateRelationship && (
      <Button onClick={openHierarchyModal}>관계 설정</Button>
    )}

    {/* 위계 관계 타입 설명 */}
    <div className="mt-3 p-2 bg-blue-50">
      <ul>
        <li>상위 문서 (PARENT_OF)</li>
        <li>하위 문서 (CHILD_OF)</li>
        <li>포함 (INCLUDES)</li>
      </ul>
    </div>
  </div>
)}
```

---

### RelationshipChatModal (N개 문서 지원)

**파일**: `components/RelationshipChatModal.tsx`

**기능**: Google NotebookLM 스타일 채팅 인터페이스

```typescript
interface RelationshipChatModalProps {
  selectedNodes: GraphNodeData[];  // N개 문서
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
```

#### 주요 기능

1. **Welcome Message** (55-66줄)
```typescript
useEffect(() => {
  if (open && selectedNodes.length >= 2 && messages.length === 0) {
    const docList = selectedNodes.map((node, idx) => `• ${node.label}`).join('\n');
    const welcomeMessage: Message = {
      content: `안녕하세요! ${selectedNodes.length}개 문서 간의 관계와 인사이트를 탐색할 준비가 되었습니다.\n\n**선택된 문서:**\n${docList}`,
    };
    setMessages([welcomeMessage]);
  }
}, [open, selectedNodes]);
```

2. **백엔드 API 호출** (106-119줄)
```typescript
const response = await fetch('/api/backend/relationship/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    documents: selectedNodes.map(node => ({
      id: node.id,
      label: node.label,
      type: node.type,
      properties: node.properties,
    })),
    messages: chatHistory,
    query: currentQuery,
  }),
});
```

3. **문서 색상 표시** (189-211줄)
```typescript
// 각 문서마다 다른 색상 배경으로 표시
const DOCUMENT_COLORS = [
  { bg: 'bg-blue-50', border: 'border-blue-200', ... },
  { bg: 'bg-green-50', border: 'border-green-200', ... },
  { bg: 'bg-purple-50', border: 'border-purple-200', ... },
  // ...
];

<div className={`grid gap-3 ${selectedNodes.length === 2 ? 'grid-cols-2' : 'grid-cols-2'}`}>
  {selectedNodes.map((node, idx) => {
    const color = DOCUMENT_COLORS[idx % DOCUMENT_COLORS.length];
    return (
      <div key={node.id} className={`${color.bg} border ${color.border}`}>
        <div className={color.label}>문서 {idx + 1}</div>
        <div>{node.label}</div>
      </div>
    );
  })}
</div>
```

**특징**:
- N개 문서 모두 백엔드로 전송
- 대화 히스토리 유지
- 실제 그래프 엣지 생성 안함
- 오직 인사이트 탐색용

---

### HierarchyRelationshipModal (2개 문서만)

**파일**: `components/HierarchyRelationshipModal.tsx`

**기능**: 2개 문서 간 위계 관계 설정

```typescript
interface HierarchyRelationshipModalProps {
  selectedNodes: GraphNodeData[];  // 항상 2개
  onCreateRelationship: (sourceId: string, targetId: string, hierarchyType: HierarchyRelationType) => void;
}
```

#### UI 구조

1. **문서 선택 표시** (73-104줄)
```typescript
<div className="grid grid-cols-2 gap-4">
  {/* 원본 문서 */}
  <div className="bg-blue-50 border border-blue-200">
    <Badge>원본 문서</Badge>
    <div>{sourceNode?.label}</div>
  </div>

  {/* 대상 문서 */}
  <div className="bg-green-50 border border-green-200">
    <Badge>대상 문서</Badge>
    <div>{targetNode?.label}</div>
  </div>
</div>
```

2. **위계 타입 선택** (111-151줄)
```typescript
{Object.values(HierarchyRelationType).map((type) => {
  const hierarchyType = HIERARCHY_TYPES[type];
  return (
    <button onClick={() => setSelectedType(type)}>
      <div>{getTypeIcon(type)}</div>
      <div>
        <span>{hierarchyType.name}</span>
        <p>{hierarchyType.description}</p>
        <div>예시: {hierarchyType.examples.join(', ')}</div>
      </div>
    </button>
  );
})}
```

3. **관계 생성 핸들러** (page.tsx:155-185)
```typescript
const handleCreateHierarchyRelationship = useCallback(
  (sourceId: string, targetId: string, hierarchyType: HierarchyRelationType) => {
    const sourceNode = nodes.find(n => n.data.id === sourceId);
    const targetNode = nodes.find(n => n.data.id === targetId);

    const newEdge: Edge = {
      id: `hierarchy-${sourceNode.id}-${targetNode.id}-${Date.now()}`,
      source: sourceNode.id,
      target: targetNode.id,
      type: 'hierarchy',
      data: {
        hierarchyType: hierarchyType,
      },
      sourceHandle: 'bottom',
      targetHandle: 'top',
    };

    setEdges((eds) => [...eds, newEdge]);
    clearRelationshipSelection();
    setIsHierarchyModalOpen(false);
  },
  [nodes, setEdges, clearRelationshipSelection]
);
```

**특징**:
- 정확히 2개 문서만 사용
- UI에서 위계 타입 선택
- 실제 그래프에 hierarchy 엣지 추가
- 엣지는 top/bottom handle 사용 (수직 연결)

---

### 위계 관계 표시 토글

**파일**: `page.tsx:322-333`

```typescript
const filteredEdges = useMemo(() => {
  if (showHierarchyRelations) {
    return edges;
  }
  // Hide hierarchy relation edges when toggle is off
  return edges.filter(edge => {
    const edgeType = edge.type;
    const hierarchyType = edge.data?.hierarchyType;
    return edgeType !== 'hierarchy' && !isHierarchyRelation(hierarchyType);
  });
}, [edges, showHierarchyRelations]);
```

사용자가 RightSidebar에서 "위계 관계선 표시" 체크박스를 토글하면 hierarchy 엣지가 표시/숨김됩니다.

---

## 백엔드 구조

### 디렉토리 구조

```
nara_service/backend/app/
├── main.py                                # FastAPI 앱 진입점
├── models.py                              # Pydantic 모델
├── routers/
│   ├── relationship_chat.py              # /relationship/chat 엔드포인트
│   └── graph_relationships.py            # /graph/relationship CRUD, AI 추천
├── services/
│   └── relationship_chat_service.py      # N개 문서 분석 LLM 서비스
└── core/
    └── hierarchy_types.py                # 위계 관계 타입 정의
```

---

### API 엔드포인트

#### 1. POST /relationship/chat

**파일**: `routers/relationship_chat.py`

```python
@router.post("/chat", response_model=RelationshipChatResponse)
async def chat_about_relationship(
    request: RelationshipChatRequest,
    _: bool = Depends(verify_api_key),
    chat_service: RelationshipChatService = Depends(get_chat_service)
) -> RelationshipChatResponse:
    """
    N개 문서 간의 관계에 대해 LLM과 대화

    - documents: N개 문서 정보 목록 (2개 이상)
    - messages: 이전 대화 히스토리
    - query: 사용자 질문

    Note: Ollama gemma3:4b 모델 사용
    """
    response = await chat_service.chat(request)
    return response
```

**요청 모델**: `models.py:294-310`

```python
class RelationshipChatRequest(BaseModel):
    """관계 채팅 요청 모델 - N개 문서 지원"""
    documents: list[dict] = Field(..., min_items=2, description="분석할 문서 목록 (2개 이상)")
    messages: list[ChatMessage] = Field(default=[], description="이전 대화 히스토리")
    query: str = Field(..., min_length=1, description="사용자 질문")

    @validator('documents')
    def validate_documents(cls, v):
        if len(v) < 2:
            raise ValueError('At least 2 documents are required')
        return v
```

**응답 모델**: `models.py:312-316`

```python
class RelationshipChatResponse(BaseModel):
    """관계 채팅 응답 모델"""
    response: str = Field(..., description="AI 응답")
    context_used: dict = Field(..., description="사용된 컨텍스트 정보")
```

---

#### 2. GET /graph/hierarchy-types

**파일**: `routers/graph_relationships.py:175-194`

```python
@router.get("/hierarchy-types")
async def get_hierarchy_relationship_types(
    _: bool = Depends(verify_api_key)
) -> JSONResponse:
    """
    위계 관계 타입 목록을 반환합니다.

    Why: 프론트엔드에서 문서 간 상하위 위계 관계를 정의할 때
         사용할 수 있는 관계 타입 목록을 제공합니다.
    """
    hierarchy_types = get_hierarchy_types()
    return JSONResponse(content={
        "hierarchy_types": hierarchy_types,
        "total": len(hierarchy_types)
    })
```

**응답 예시**:
```json
{
  "hierarchy_types": [
    {
      "id": "PARENT_OF",
      "name": "상위 문서",
      "description": "이 문서는 대상 문서의 상위 개념/정책입니다",
      "direction": "down",
      "examples": ["총괄 정책 → 세부 정책", "법률 → 시행령"]
    },
    {
      "id": "CHILD_OF",
      "name": "하위 문서",
      "description": "이 문서는 대상 문서의 하위 개념/세부사항입니다",
      "direction": "up",
      "examples": ["세부 지침 → 상위 정책", "시행규칙 → 법률"]
    },
    {
      "id": "INCLUDES",
      "name": "포함",
      "description": "이 문서는 대상 문서를 포함합니다",
      "direction": "down",
      "examples": ["종합 보고서 → 부분 보고서", "전체 계획 → 세부 항목"]
    }
  ],
  "total": 3
}
```

---

### RelationshipChatService 상세

**파일**: `services/relationship_chat_service.py`

#### 클래스 구조

```python
class RelationshipChatService:
    """여러 문서 간 관계 분석을 위한 대화형 LLM 서비스 (N개 문서 지원)"""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "gemma3:4b"):
        self.ollama_url = ollama_url.rstrip('/')
        self.model = model
        self.system_prompt = """..."""  # 상세 프롬프트 (24-93줄)
```

#### 시스템 프롬프트 구조 (24-93줄)

```python
self.system_prompt = """당신은 문서 간의 관계와 인사이트를 분석하는 전문 AI 어시스턴트입니다.
사용자는 {doc_count}개의 문서를 선택했고, 이 문서들 간의 관계에 대해 질문할 것입니다.

{documents_info}

**당신의 역할:**
1. 선택된 문서들 간의 공통점, 차이점, 연관성을 분석합니다
2. 사용자의 질문에 대해 구체적이고 통찰력 있는 답변을 제공합니다
3. 문서들을 함께 활용하는 방법을 제안합니다
4. 문서들 간의 시너지 효과나 패턴을 발견하여 공유합니다
5. 여러 문서를 통합적으로 분석하여 새로운 통찰을 제공합니다
6. **문서 간 상하위 위계 관계를 파악하여 분석합니다**

**문서 간 관계 분석 프레임워크:**

1. **인과 관계 (Causality)**
   - 원인-결과 (CAUSES, LEADS_TO)
   - 선행-후행 (PRECEDES, FOLLOWS)

2. **비교/대조 관계 (Comparison)**
   - 유사 (SIMILAR_TO)
   - 대조 (CONTRASTS_WITH)
   - 보완 (COMPLEMENTS)

3. **상하위 위계 관계 (Hierarchy)** ⭐ 중요
   - 상위 문서 (PARENT_OF): 이 문서가 대상 문서의 상위 개념/정책
     예) 총괄 정책 → 세부 정책, 법률 → 시행령
   - 하위 문서 (CHILD_OF): 이 문서가 대상 문서의 하위 개념/세부사항
     예) 세부 지침 → 상위 정책, 시행규칙 → 법률
   - 포함 (INCLUDES): 이 문서가 대상 문서를 포함
     예) 종합 보고서 → 부분 보고서, 전체 계획 → 세부 항목

4. **시간적 관계 (Temporal)**
   - 업데이트 (UPDATES)
   - 대체 (SUPERSEDES)

5. **의존 관계 (Dependency)**
   - 필요 (REQUIRES)
   - 의존 (DEPENDS_ON)
   - 지원 (SUPPORTS)

6. **참조 관계 (Reference)**
   - 인용 (CITES)
   - 참조 (REFERENCES)
   - 근거 (BASED_ON)

7. **충돌/모순 관계 (Conflict)**
   - 모순 (CONTRADICTS)
   - 충돌 (CONFLICTS_WITH)

8. **영향 관계 (Influence)**
   - 영향 (INFLUENCES)
   - 강화 (REINFORCES)
   - 약화 (WEAKENS)

**답변 가이드라인:**
- 명확하고 구조화된 답변을 제공하세요
- 위 관계 프레임워크를 활용하여 문서 간 관계를 구체적으로 분석하세요
- 특히 **상하위 위계 관계**를 중점적으로 파악하여 설명하세요
- 구체적인 예시나 근거를 들어 설명하세요
- 여러 문서를 종합적으로 고려한 답변을 제공하세요
- 문서 간 위계 구조가 있다면 트리 구조나 계층도로 설명하세요
"""
```

**프롬프트 특징**:
- N개 문서 지원 (`{doc_count}` 변수)
- 8가지 관계 분석 프레임워크 제공
- 특히 **위계 관계** 강조 (PARENT_OF, CHILD_OF, INCLUDES)
- 구조화된 답변 요구

#### chat() 메서드 (139-199줄)

```python
async def chat(self, request: RelationshipChatRequest) -> RelationshipChatResponse:
    """
    여러 문서 간 관계에 대한 LLM 대화 처리 (N개 문서 지원)
    """
    # 1. 모든 문서 정보 추출 및 포맷팅
    documents_info_list = []
    for idx, doc in enumerate(request.documents, 1):
        doc_info = self._extract_doc_info(doc)
        documents_info_list.append(f"""**문서 {idx} 정보:**
- 제목: {doc_info['title']}
- 설명: {doc_info['description']}
- 카테고리: {doc_info['category']}
- 제공기관: {doc_info['provider']}
""")

    documents_info_text = "\n".join(documents_info_list)

    # 2. 대화 히스토리 포맷팅
    chat_history = self._format_chat_history(request.messages)

    # 3. 프롬프트 구성
    prompt = self.system_prompt.format(
        doc_count=len(request.documents),
        documents_info=documents_info_text,
        query=request.query,
        chat_history=chat_history
    )

    # 4. Ollama API 직접 호출
    logger.info(f"Calling Ollama ({self.model}) for relationship chat with {len(request.documents)} documents")
    response_text = await self._call_ollama(prompt)

    # 5. 응답 반환
    return RelationshipChatResponse(
        response=response_text,
        context_used={
            "documents": docs_context,
            "document_count": len(request.documents),
            "model": self.model,
            "message_count": len(request.messages)
        }
    )
```

**처리 흐름**:
1. N개 문서 정보 추출 및 포맷팅
2. 대화 히스토리 포맷팅 (이전 대화 맥락 유지)
3. 시스템 프롬프트에 변수 주입
4. Ollama gemma3:4b 모델로 LLM 호출
5. 응답 반환 (context_used에 메타데이터 포함)

#### Ollama API 호출 (95-116줄)

```python
async def _call_ollama(self, prompt: str) -> str:
    """Ollama API 직접 호출"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 1024,
                    }
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    except httpx.HTTPError as e:
        logger.error(f"Ollama API 호출 실패: {e}")
        raise ValueError(f"Ollama API 호출 실패: {str(e)}")
```

**설정**:
- Model: gemma3:4b
- Temperature: 0.7 (창의성과 일관성 균형)
- Max tokens: 1024
- Timeout: 120초

---

### 위계 관계 타입 시스템

**파일**: `core/hierarchy_types.py`

#### Enum 정의 (9-14줄)

```python
class HierarchyRelationType(str, Enum):
    """위계 관계 타입"""
    PARENT_OF = "PARENT_OF"  # 상위 문서
    CHILD_OF = "CHILD_OF"    # 하위 문서
    INCLUDES = "INCLUDES"    # 포함
```

#### 메타데이터 (17-39줄)

```python
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
```

**특징**:
- `direction`: 관계 방향 표시 (up/down)
- `inverse`: 역방향 관계 (양방향 관계 구현 가능)
- `examples`: UI에서 사용자에게 예시 제공

#### API 응답 함수 (42-53줄)

```python
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
```

---

## 데이터 흐름

### Relationship 모드 (N개 문서 AI 채팅)

```
[프론트엔드]
1. 사용자가 Relationship 모드 선택
2. 노드 클릭 → selectNodeForRelationship() 호출
3. selectedNodes 배열에 추가 (토글)
4. 2개 이상 선택 시 "Explore Relationship" 버튼 활성화
5. 버튼 클릭 → RelationshipChatModal 열림
6. Welcome 메시지 표시

7. 사용자가 질문 입력 및 전송
   ↓
   POST /api/backend/relationship/chat
   Body: {
     documents: [
       { id, label, type, properties },
       { id, label, type, properties },
       { id, label, type, properties },
       ...
     ],
     messages: [...이전 대화],
     query: "문서들의 공통점은?"
   }

[백엔드]
8. relationship_chat.py 라우터가 요청 수신
9. RelationshipChatService.chat() 호출
10. N개 문서 정보 추출 및 포맷팅
11. 시스템 프롬프트 구성 (관계 분석 프레임워크 포함)
12. Ollama gemma3:4b 모델 호출
13. LLM 응답 생성
14. Response 반환: { response: "...", context_used: {...} }

[프론트엔드]
15. AI 응답을 메시지 목록에 추가
16. 채팅 UI에 표시
17. 사용자가 추가 질문 가능 (대화 히스토리 유지)
```

---

### Hierarchy 모드 (2개 문서 위계 관계 생성)

```
[프론트엔드]
1. 사용자가 Hierarchy 모드 선택
2. 첫 번째 노드 클릭 → selectNodeForRelationship() 호출
3. 두 번째 노드 클릭 → selectNodeForRelationship() 호출
4. 2개 선택 시 "관계 설정" 버튼 활성화
5. 버튼 클릭 → HierarchyRelationshipModal 열림

6. 모달에서 위계 타입 선택 UI 표시:
   - PARENT_OF (상위 문서)
   - CHILD_OF (하위 문서)
   - INCLUDES (포함)

7. 사용자가 위계 타입 선택 (예: PARENT_OF)
8. "관계 생성" 버튼 클릭
9. handleCreateHierarchyRelationship() 호출
   - sourceId, targetId, hierarchyType 전달

10. 새로운 Edge 객체 생성:
    {
      id: "hierarchy-node1-node2-1234567890",
      source: "node1",
      target: "node2",
      type: "hierarchy",
      data: { hierarchyType: "PARENT_OF" },
      sourceHandle: "bottom",
      targetHandle: "top"
    }

11. setEdges() 호출하여 그래프에 엣지 추가
12. clearRelationshipSelection() - 선택 초기화
13. 모달 닫기

14. 그래프에 hierarchy 엣지가 시각적으로 표시됨
    - 수직 연결 (top/bottom handle)
    - 파란색 계열 스타일
```

**주요 차이점**:
- Relationship 모드: 백엔드 API 호출, AI 채팅, 엣지 생성 안함
- Hierarchy 모드: 백엔드 호출 없음, 프론트엔드에서 직접 엣지 생성

---

## 주요 컴포넌트 상세

### 1. useRelationshipMode Hook

**역할**: N개 노드 선택 상태 관리

**주요 메서드**:
- `selectNodeForRelationship(node)`: 노드 추가/제거 (토글)
- `clearSelection()`: 선택 초기화
- `openModal()` / `closeModal()`: 모달 열기/닫기

**상태**:
- `selection.selectedNodes`: 선택된 노드 배열
- `isModalOpen`: 모달 열림 상태
- `canCreateRelationship`: 2개 이상 선택 여부

---

### 2. RelationshipChatModal

**역할**: N개 문서로 AI 대화형 관계 탐색

**주요 기능**:
- Welcome 메시지 자동 생성
- 채팅 인터페이스 (사용자/AI 메시지)
- 백엔드 `/relationship/chat` API 호출
- 대화 히스토리 유지
- 문서별 색상 코딩

**API 호출**:
```typescript
POST /api/backend/relationship/chat
Content-Type: application/json

{
  "documents": [
    { "id": "doc1", "label": "문서 1", "type": "Document", "properties": {...} },
    { "id": "doc2", "label": "문서 2", "type": "Document", "properties": {...} },
    ...
  ],
  "messages": [
    { "role": "user", "content": "이전 질문" },
    { "role": "assistant", "content": "이전 응답" }
  ],
  "query": "새로운 질문"
}
```

---

### 3. HierarchyRelationshipModal

**역할**: 2개 문서 간 위계 관계 설정

**UI 구성**:
1. 원본 문서 / 대상 문서 표시 (좌/우)
2. 위계 타입 선택 버튼 (PARENT_OF, CHILD_OF, INCLUDES)
3. 각 타입별 설명 및 예시
4. "관계 생성" / "취소" 버튼

**관계 생성 프로세스**:
1. 사용자가 위계 타입 선택
2. `onCreateRelationship(sourceId, targetId, hierarchyType)` 콜백 호출
3. 부모 컴포넌트(page.tsx)에서 엣지 생성
4. 그래프 업데이트

---

### 4. RightSidebar

**역할**: 모드 전환 및 컨트롤 UI

**구성**:
- Interaction Mode 토글 (Path / Link / Hierarchy)
- 모드별 컨트롤 패널
- 선택된 노드 표시
- AI 추천 목록 (Relationship 모드)
- 위계 관계선 표시 토글
- Insights Dashboard

**모드별 UI**:
- **Path 모드**: Source/Target 선택, "Find Path" 버튼
- **Relationship 모드**: From/To 표시, AI 추천, "Explore Relationship" 버튼
- **Hierarchy 모드**: 원본/대상 표시, "관계 설정" 버튼, 위계 타입 설명

---

### 5. RelationshipChatService

**역할**: N개 문서 관계 분석 LLM 서비스

**주요 기능**:
- N개 문서 정보 포맷팅
- 관계 분석 프레임워크 프롬프트
- Ollama gemma3:4b 모델 호출
- 대화 히스토리 관리

**시스템 프롬프트 구조**:
- 역할 정의 (문서 관계 분석 AI)
- 8가지 관계 프레임워크 제공
- 위계 관계 특별 강조
- 구조화된 답변 요구

**LLM 설정**:
- Model: gemma3:4b
- Temperature: 0.7
- Max tokens: 1024
- Stream: False (전체 응답 한 번에)

---

## 기술 스택

### 프론트엔드
- **Framework**: Next.js (React)
- **UI 라이브러리**: Shadcn/ui
- **그래프 라이브러리**: ReactFlow (@xyflow/react)
- **상태 관리**: React Hooks (useState, useCallback, useMemo)
- **HTTP 클라이언트**: fetch API

### 백엔드
- **Framework**: FastAPI
- **LLM 통신**: httpx (async)
- **모델**: Ollama gemma3:4b
- **데이터 검증**: Pydantic
- **그래프 DB**: Neo4j (위계 관계 저장용)

---

## 확장 가능성

### 1. 관계 타입 추가

**프론트엔드**: `types/hierarchyTypes.ts`
```typescript
export enum HierarchyRelationType {
  PARENT_OF = "PARENT_OF",
  CHILD_OF = "CHILD_OF",
  INCLUDES = "INCLUDES",
  // 새로운 타입 추가
  RELATED_TO = "RELATED_TO",
}
```

**백엔드**: `core/hierarchy_types.py`
```python
HIERARCHY_METADATA: Dict[str, Dict] = {
    # 기존 타입...
    "RELATED_TO": {
        "name": "관련 문서",
        "description": "이 문서는 대상 문서와 관련이 있습니다",
        "direction": "both",
        "inverse": "RELATED_TO",
        "examples": ["유사 주제", "동일 분야"]
    }
}
```

### 2. N:N 관계 지원

현재는 1:1 (Hierarchy) 또는 1:N (Relationship Chat)만 지원하지만, N:N 관계 생성 기능을 추가할 수 있습니다:

1. `selectNodeForRelationship()`를 확장하여 "역할" 개념 추가
2. 그룹 관계 생성 API 엔드포인트 추가
3. 하이퍼엣지 시각화 지원

### 3. 관계 강도 (Strength) 추가

```typescript
const newEdge: Edge = {
  // 기존 속성...
  data: {
    hierarchyType: hierarchyType,
    strength: 0.8,  // 0.0 ~ 1.0
  },
};
```

엣지 두께나 색상으로 관계 강도를 시각화할 수 있습니다.

### 4. 자동 위계 관계 추론

LLM을 활용하여 문서 내용을 분석하고 자동으로 위계 관계를 제안하는 기능:

```python
async def infer_hierarchy_relationship(
    doc1: dict,
    doc2: dict
) -> Dict[str, Any]:
    """
    LLM이 두 문서의 내용을 분석하여
    위계 관계를 자동으로 추론합니다.
    """
    prompt = f"""
    문서 1: {doc1['title']} - {doc1['description']}
    문서 2: {doc2['title']} - {doc2['description']}

    이 두 문서 간의 상하위 위계 관계를 분석하세요.
    응답 형식:
    - relation: PARENT_OF / CHILD_OF / INCLUDES / NONE
    - confidence: 0.0 ~ 1.0
    - reason: 판단 근거
    """
    # LLM 호출...
```

---

## 성능 고려사항

### 1. LLM 호출 최적화

- **Timeout**: 120초 설정 (긴 응답 대응)
- **Temperature**: 0.7 (창의성과 일관성 균형)
- **Max tokens**: 1024 (충분한 답변 길이)

### 2. 대화 히스토리 관리

- 클라이언트 측에서 메시지 배열 관리
- 너무 긴 히스토리는 잘라내기 (예: 최근 10개만)
- 백엔드에서 토큰 수 계산 후 제한

### 3. 엣지 렌더링 최적화

- `useMemo`로 filteredEdges 계산 최적화
- 위계 관계선 토글 시 재계산 방지
- ReactFlow 성능 최적화 옵션 활용

---

## 보안 고려사항

### 1. API 키 인증

모든 백엔드 엔드포인트는 `verify_api_key` 의존성 필요:

```python
@router.post("/chat")
async def chat_about_relationship(
    _: bool = Depends(verify_api_key),  # API 키 검증
    ...
):
```

### 2. 입력 검증

Pydantic 모델로 입력 검증:

```python
class RelationshipChatRequest(BaseModel):
    documents: list[dict] = Field(..., min_items=2)
    query: str = Field(..., min_length=1)

    @validator('documents')
    def validate_documents(cls, v):
        if len(v) < 2:
            raise ValueError('At least 2 documents are required')
        return v
```

### 3. Rate Limiting

FastAPI slowapi로 요청 제한:

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
```

---

## 문제 해결 (Troubleshooting)

### 1. "Explore Relationship" 버튼이 활성화되지 않음

**원인**: `selectedNodes.length < 2`

**해결**:
1. 2개 이상의 노드를 클릭했는지 확인
2. `interactionMode`가 'relationship'인지 확인
3. 브라우저 콘솔에서 `relationshipSelection.selectedNodes` 확인

### 2. LLM 응답이 느리거나 타임아웃

**원인**: Ollama 서버 응답 지연

**해결**:
1. Ollama 서버 상태 확인: `curl http://localhost:11434/api/tags`
2. gemma3:4b 모델이 설치되어 있는지 확인
3. 백엔드 로그에서 실제 API 호출 시간 확인
4. timeout 값 조정 (현재 120초)

### 3. 위계 관계 엣지가 표시되지 않음

**원인**: `showHierarchyRelations` 토글이 꺼져 있음

**해결**:
1. RightSidebar에서 "위계 관계선 표시" 체크박스 확인
2. `filteredEdges` 로직 확인 (page.tsx:322-333)
3. 엣지 data에 `hierarchyType` 속성이 있는지 확인

### 4. 프론트엔드에서 404 에러

**원인**: 백엔드 라우터가 등록되지 않음

**해결**:
1. `main.py`에서 `app.include_router(relationship_chat.router)` 확인
2. 백엔드 서버 재시작
3. API 경로 확인: `/api/backend/relationship/chat`

---

## 결론

이 아키텍처는 **유연한 N개 노드 선택 시스템**과 **두 가지 모드(Relationship/Hierarchy)**를 통해 사용자가 문서 간 관계를 다양한 방식으로 탐색하고 정의할 수 있도록 설계되었습니다.

**핵심 설계 원칙**:
1. **유연성**: N개 노드를 배열로 관리하여 확장 가능
2. **명확한 역할 분리**: Relationship(인사이트 탐색) vs Hierarchy(그래프 구조화)
3. **사용자 경험**: 토글 선택, 색상 코딩, 명확한 UI 피드백
4. **AI 활용**: LLM 기반 관계 분석 및 추천
5. **성능**: 클라이언트/서버 부하 분산, 비동기 처리

**향후 개선 방향**:
- 자동 위계 관계 추론
- N:N 관계 지원
- 관계 강도 시각화
- 그래프 레이아웃 최적화
- 대화 히스토리 영구 저장

---

## 최근 업데이트 (2026-01-07)

### 위계 관계 드래그 연결 기능 구현

**문제점**:
1. 위계 관계 생성 시 `sourceHandle: 'bottom'`, `targetHandle: 'top'`으로 하드코딩되어 있어 항상 수직 방향으로만 연결됨
2. 사용자가 좌우나 다른 방향으로 자유롭게 연결할 수 없음

**해결 방안**:
ReactFlow의 기본 드래그 연결 기능을 활용하여 4방향 자유 연결 구현

### 구현 내용

#### 1. onConnect 로직 수정 (page.tsx:247-270)

```typescript
const onConnect = useCallback(
  (params: Connection) => {
    // Hierarchy 모드에서는 hierarchy 엣지 생성
    if (interactionMode === 'hierarchy') {
      const newEdge: Edge = {
        ...params,
        id: `hierarchy-${params.source}-${params.target}-${Date.now()}`,
        type: 'hierarchy',
        data: {
          // hierarchyType은 모달에서 선택
        },
      };

      setEdges((eds) => [...eds, newEdge]);
      setPendingHierarchyEdgeId(newEdge.id);
      setIsHierarchyModalOpen(true);
    } else {
      // 일반 관계 엣지 생성
      setEdges((eds) => addEdge(params, eds));
      setTimeout(updateGroups, 100);
    }
  },
  [setEdges, updateGroups, interactionMode]
);
```

**변경 사항**:
- `interactionMode === 'hierarchy'`일 때 hierarchy 타입 엣지 생성
- `params`에 ReactFlow가 자동으로 설정한 `sourceHandle`, `targetHandle` 포함
- 엣지 생성 후 즉시 모달을 열어 위계 타입 선택

#### 2. Pending Edge 시스템 도입 (page.tsx:143-208)

```typescript
const [pendingHierarchyEdgeId, setPendingHierarchyEdgeId] = useState<string | null>(null);

const closeHierarchyModal = useCallback(() => {
  // 모달 닫을 때 pending edge가 있고 hierarchyType이 없으면 엣지 삭제
  if (pendingHierarchyEdgeId) {
    setEdges((eds) => {
      const edge = eds.find(e => e.id === pendingHierarchyEdgeId);
      if (edge && !edge.data?.hierarchyType) {
        // hierarchyType이 설정되지 않았으면 엣지 삭제 (취소됨)
        return eds.filter(e => e.id !== pendingHierarchyEdgeId);
      }
      return eds;
    });
    setPendingHierarchyEdgeId(null);
  }
  setIsHierarchyModalOpen(false);
}, [pendingHierarchyEdgeId, setEdges]);

const handleCreateHierarchyRelationship = useCallback(
  (sourceId: string, targetId: string, hierarchyType: HierarchyRelationType) => {
    if (pendingHierarchyEdgeId) {
      // 드래그로 생성된 엣지에 hierarchyType 추가
      setEdges((eds) =>
        eds.map((edge) =>
          edge.id === pendingHierarchyEdgeId
            ? { ...edge, data: { ...edge.data, hierarchyType } }
            : edge
        )
      );
      setPendingHierarchyEdgeId(null);
    } else {
      // UI 버튼으로 생성 (기존 방식, sourceHandle/targetHandle 제거)
      const newEdge: Edge = {
        // ...
        // sourceHandle/targetHandle 제거 - ReactFlow가 자동 선택
      };
      setEdges((eds) => [...eds, newEdge]);
    }

    clearRelationshipSelection();
    setIsHierarchyModalOpen(false);
  },
  [nodes, setEdges, clearRelationshipSelection, pendingHierarchyEdgeId]
);
```

**작동 방식**:
1. 드래그로 엣지 생성 시 `pendingHierarchyEdgeId`에 엣지 ID 저장
2. 모달에서 위계 타입 선택 시 해당 엣지에 `hierarchyType` 추가
3. 모달 취소 시 `hierarchyType`이 없는 엣지는 자동 삭제

#### 3. HierarchyRelationshipModal 확장 (HierarchyRelationshipModal.tsx:24-75)

```typescript
interface HierarchyRelationshipModalProps {
  selectedNodes: GraphNodeData[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateRelationship: (sourceId: string, targetId: string, hierarchyType: HierarchyRelationType) => void;
  // 드래그 연결을 위한 추가 props
  pendingEdgeId?: string | null;
  nodes?: AppNode[];
  edges?: Edge[];
}

export const HierarchyRelationshipModal: React.FC<HierarchyRelationshipModalProps> = ({
  selectedNodes,
  open,
  onOpenChange,
  onCreateRelationship,
  pendingEdgeId = null,
  nodes = [],
  edges = [],
}) => {
  // 드래그로 생성된 엣지가 있으면 해당 엣지에서 노드 찾기
  let sourceNode: GraphNodeData | undefined;
  let targetNode: GraphNodeData | undefined;

  if (pendingEdgeId && edges && nodes) {
    const edge = edges.find(e => e.id === pendingEdgeId);
    if (edge) {
      const sourceAppNode = nodes.find(n => n.id === edge.source);
      const targetAppNode = nodes.find(n => n.id === edge.target);

      if (sourceAppNode && targetAppNode && sourceAppNode.type === 'contextNode' && targetAppNode.type === 'contextNode') {
        sourceNode = {
          id: sourceAppNode.data.id || sourceAppNode.id,
          label: sourceAppNode.data.title || sourceAppNode.id,
          type: 'Document',
          properties: sourceAppNode.data,
        };
        targetNode = {
          id: targetAppNode.data.id || targetAppNode.id,
          label: targetAppNode.data.title || targetAppNode.id,
          type: 'Document',
          properties: targetAppNode.data,
        };
      }
    }
  } else {
    // 기존 방식: selectedNodes에서 가져오기
    sourceNode = selectedNodes[0];
    targetNode = selectedNodes[1];
  }

  // ...
};
```

**변경 사항**:
- `pendingEdgeId`, `nodes`, `edges` props 추가
- 드래그 연결 시 엣지에서 source/target 노드 정보 추출
- 기존 UI 버튼 방식도 여전히 지원 (하위 호환성)

### 사용자 경험 개선

#### Before (이전)
- UI 버튼으로만 위계 관계 생성 가능
- 무조건 아래(bottom) → 위(top) 방향으로만 연결
- 상하좌우 자유로운 레이아웃 불가능

#### After (개선)
1. **드래그 연결 지원**
   - Hierarchy 모드에서 노드의 handle을 드래그하여 직접 연결
   - 상하좌우 4방향 모두 자유롭게 연결 가능
   - ReactFlow가 자동으로 최적의 경로 계산

2. **자동 모달 표시**
   - 드래그로 연결 생성 시 자동으로 HierarchyRelationshipModal 열림
   - 위계 타입(PARENT_OF, CHILD_OF, INCLUDES) 선택

3. **취소 기능**
   - 모달에서 취소 시 생성된 엣지 자동 삭제
   - 깔끔한 UX

4. **하드코딩 제거**
   - `sourceHandle`, `targetHandle` 하드코딩 완전 제거
   - ReactFlow가 드래그 위치에 따라 자동 선택

### 기술적 세부사항

#### Handle 구성 (CustomFlowElements.tsx:234-249)

```typescript
// 좌우 연결 (일반 관계용)
<Handle type="target" position={Position.Left} />
<Handle type="source" position={Position.Right} />

// 상하 연결 (위계 관계용, id 명시)
<Handle type="target" position={Position.Top} id="top" />
<Handle type="source" position={Position.Bottom} id="bottom" />
```

**중요**:
- 위계 관계는 상하 handle에 `id` 속성이 있어 명시적으로 선택 가능
- 일반 관계는 좌우 handle 사용
- 하지만 이제는 모든 handle이 자유롭게 사용 가능

#### Connection 객체 구조

ReactFlow의 `onConnect` 콜백이 받는 `params`:

```typescript
{
  source: "node-1",          // 시작 노드 ID
  target: "node-2",          // 끝 노드 ID
  sourceHandle: "bottom",    // 시작 handle (자동 설정)
  targetHandle: "top",       // 끝 handle (자동 설정)
}
```

이 정보를 그대로 엣지에 전달하면 ReactFlow가 자동으로 올바른 방향으로 렌더링합니다.

### 테스트 시나리오

1. **좌우 연결 테스트**
   - Hierarchy 모드 선택
   - 노드 A의 오른쪽 handle → 노드 B의 왼쪽 handle로 드래그
   - 모달에서 PARENT_OF 선택
   - 결과: 수평 위계 관계 생성

2. **상하 연결 테스트**
   - Hierarchy 모드 선택
   - 노드 A의 아래 handle → 노드 B의 위 handle로 드래그
   - 모달에서 CHILD_OF 선택
   - 결과: 수직 위계 관계 생성

3. **취소 테스트**
   - Hierarchy 모드에서 드래그 연결
   - 모달에서 취소 버튼 클릭
   - 결과: 생성된 엣지가 삭제됨

4. **기존 방식 호환성 테스트**
   - Hierarchy 모드에서 노드 2개 클릭 선택
   - RightSidebar의 "관계 설정" 버튼 클릭
   - 모달에서 타입 선택
   - 결과: 기존처럼 정상 작동 (방향은 ReactFlow 자동 선택)

### 남은 고려사항

1. **UI 버튼 방식의 handle 선택**
   - 현재는 ReactFlow가 자동 선택
   - 향후: 두 노드의 위치를 분석하여 최적 handle 선택 가능

2. **드래그 연결 시각적 피드백**
   - Hierarchy 모드일 때 handle 색상 강조 (이미 구현됨: 파란색)
   - 드래그 중 연결선 미리보기 (ReactFlow 기본 기능)

3. **다방향 위계 관계 의미**
   - PARENT_OF를 좌우로 연결하는 것의 의미?
   - 위계 타입과 방향의 의미론적 매칭 필요할 수 있음

### 관련 파일

**수정된 파일**:
- `nara_service/frontend/src/app/prometheus/page.tsx`
  - onConnect 로직 (247-270줄)
  - Pending edge 시스템 (143-208줄)
  - HierarchyRelationshipModal props (481-489줄)

- `nara_service/frontend/src/app/prometheus/components/HierarchyRelationshipModal.tsx`
  - Props 확장 (24-33줄)
  - 드래그 엣지 노드 추출 (46-75줄)
  - handleCreate 검증 강화 (77-82줄)

**영향 없는 파일**:
- `CustomFlowElements.tsx` - Handle 구성은 이미 4방향 지원
- `useRelationshipMode.ts` - 선택 로직 변경 없음
- 백엔드 파일들 - 프론트엔드만 수정
