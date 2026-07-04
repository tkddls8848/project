from pydantic import BaseModel, Field

DEFAULT_QUESTION = "이 API들을 조합하면 어떤 행정 서비스 계획을 만들 수 있나?"


class Service(BaseModel):
    api_id: str
    name: str
    agency: str
    domain: str
    keywords: list[str]
    description: str
    endpoints: list[dict]


class ComposeRequest(BaseModel):
    service_ids: list[str] = Field(..., min_length=1, max_length=10)
    question: str = Field(default=DEFAULT_QUESTION, min_length=1, max_length=500)


class ComposeResponse(BaseModel):
    service_ids: list[str]
    domains: list[str]
    warning: str | None = None
    # 요청 ID 중 카탈로그에서 찾지 못한 항목 (일부 누락은 200 + missing으로 보고)
    missing: list[str] = Field(default_factory=list)
    suggestion: str
    # suggestion이 길이 예산(COMBINER_MAX_SUGGESTION_CHARS)으로 잘렸는지 여부
    truncated: bool = False
    elapsed_ms: int
    model: str
