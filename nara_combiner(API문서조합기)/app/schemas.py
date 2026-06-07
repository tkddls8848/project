from pydantic import BaseModel


class Service(BaseModel):
    api_id: str
    name: str
    agency: str
    domain: str
    keywords: list[str]
    description: str
    endpoints: list[dict]


class ComposeRequest(BaseModel):
    service_ids: list[str]
    question: str = "이 API들을 조합하면 어떤 행정 서비스 계획을 만들 수 있나?"


class ComposeResponse(BaseModel):
    service_ids: list[str]
    domains: list[str]
    warning: str | None = None
    suggestion: str
    elapsed_ms: int
    model: str
