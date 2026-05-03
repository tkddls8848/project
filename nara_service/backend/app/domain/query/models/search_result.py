"""
Search Result Models

Pydantic models for search results.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any


class DocumentInfo(BaseModel):
    """
    Document information

    Represents a single document in search results.
    """
    id: Optional[str] = Field(None, description="Document API ID")
    title: Optional[str] = Field(None, description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    url: Optional[str] = Field(None, description="Document URL")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Update timestamp")
    provider: Optional[str] = Field(None, description="Provider name")
    category: Optional[str] = Field(None, description="Category name")
    keywords: List[str] = Field(default_factory=list, description="Keywords")
    properties: dict = Field(default_factory=dict, description="Additional properties")


class SearchResult(BaseModel):
    """
    Search result container

    Contains list of documents with pagination info.
    """
    documents: List[DocumentInfo] = Field(default_factory=list, description="Document list")
    total: int = Field(0, description="Total count")
    limit: int = Field(50, description="Results per page")
    offset: int = Field(0, description="Offset for pagination")
