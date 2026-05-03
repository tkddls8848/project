"""Relationship Chat API Router - NotebookLM Style"""
from fastapi import APIRouter, HTTPException, Depends
import logging

from app.models import RelationshipChatRequest, RelationshipChatResponse
from app.auth import verify_api_key
from app.domain.common.dependencies import get_chat_service
from app.services.relationship_chat_service import RelationshipChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/relationship", tags=["relationship-chat"])


@router.post("/chat", response_model=RelationshipChatResponse)
async def chat_about_relationship(
    request: RelationshipChatRequest,
    _: bool = Depends(verify_api_key),
    chat_service: RelationshipChatService = Depends(get_chat_service)
) -> RelationshipChatResponse:
    """
    두 문서 간의 관계에 대해 LLM과 대화

    - **source_doc**: 첫 번째 문서 정보
    - **target_doc**: 두 번째 문서 정보
    - **messages**: 이전 대화 히스토리
    - **query**: 사용자 질문

    Note: Ollama gemma3:4b 모델 사용
    """
    try:
        response = await chat_service.chat(request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in relationship chat: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process chat request"
        )
