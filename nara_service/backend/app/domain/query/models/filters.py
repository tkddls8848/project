"""
Query Filter Models

Pydantic models for type-safe filter definitions.

Design Decision:
- Using Pydantic for runtime validation and IDE autocomplete
- Enum for operators ensures type safety
- Validators prevent invalid data at the boundary
"""
from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import Union, List, Optional


class FilterOperator(str, Enum):
    """
    Filter comparison operators

    Maps to Cypher query operators for Neo4j.
    """
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    CONTAINS = "contains"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"


class NodeFilter(BaseModel):
    """
    Node property filter

    Example:
        NodeFilter(
            field="title",
            operator=FilterOperator.CONTAINS,
            value="교육"
        )
    """
    field: str = Field(..., description="Field name to filter on")
    operator: FilterOperator = Field(..., description="Comparison operator")
    value: Union[str, int, float, List[str]] = Field(..., description="Comparison value")

    @validator("field")
    def validate_field(cls, v):
        """Validate field name is not empty"""
        if not v or not v.strip():
            raise ValueError("Field name cannot be empty")
        return v.strip()

    @validator("value")
    def validate_value(cls, v, values):
        """Validate value matches operator requirements"""
        operator = values.get("operator")

        if operator in [FilterOperator.IN, FilterOperator.NOT_IN]:
            if not isinstance(v, list):
                raise ValueError(f"Operator {operator} requires a list value")

        return v


class RelationshipFilter(BaseModel):
    """
    Relationship filter

    Example:
        RelationshipFilter(
            rel_type="BELONGS_TO",
            target_label="Category",
            target_field="name",
            operator=FilterOperator.EQUALS,
            value="교육"
        )
    """
    rel_type: str = Field(..., description="Relationship type")
    target_label: str = Field(..., description="Target node label")
    target_field: str = Field(..., description="Target field name")
    operator: FilterOperator = Field(..., description="Comparison operator")
    value: Union[str, List[str]] = Field(..., description="Comparison value")

    @validator("rel_type", "target_label", "target_field")
    def validate_not_empty(cls, v):
        """Validate fields are not empty"""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class SearchQuery(BaseModel):
    """
    Complete search query specification

    Example:
        SearchQuery(
            filters=[
                NodeFilter(field="title", operator=FilterOperator.CONTAINS, value="교육")
            ],
            relationship_filters=[
                RelationshipFilter(
                    rel_type="BELONGS_TO",
                    target_label="Category",
                    target_field="name",
                    operator=FilterOperator.EQUALS,
                    value="교육"
                )
            ],
            sort_by="created_at",
            sort_order="DESC",
            limit=50,
            offset=0
        )
    """
    filters: List[NodeFilter] = Field(default_factory=list, description="Node property filters")
    relationship_filters: List[RelationshipFilter] = Field(
        default_factory=list,
        description="Relationship filters"
    )
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="DESC", pattern="^(ASC|DESC)$", description="Sort order")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum results to return")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")

    @validator("sort_by")
    def validate_sort_by(cls, v):
        """Validate sort field is not empty"""
        if not v or not v.strip():
            raise ValueError("Sort field cannot be empty")
        return v.strip()
