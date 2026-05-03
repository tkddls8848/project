"""
Cypher Filter Builder - Pure Functions

Builds Cypher WHERE clauses from filter specifications.

Design Decision:
- All functions are pure (input → output, no side effects)
- Static methods only (no instance state)
- Parameterized queries to prevent injection
- DRY: Single source of truth for operator mapping

CODING_RULES Compliance:
- Rule 1: FP First - Pure functions, isolated side effects
- Rule 1: DRY - Extract upon 2nd repetition
- Rule 4: Type Safety - Strong typing with Pydantic models
"""
from typing import Dict, Any, Tuple, List
from app.domain.query.models.filters import NodeFilter, FilterOperator, RelationshipFilter


class CypherFilterBuilder:
    """
    Cypher WHERE clause builder

    All methods are static pure functions.
    """

    @staticmethod
    def build_node_filter(
        filter_spec: NodeFilter,
        node_alias: str,
        param_prefix: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build WHERE clause for a single node filter

        Args:
            filter_spec: Filter specification
            node_alias: Node alias in Cypher (e.g., "d")
            param_prefix: Parameter prefix (e.g., "filter_0")

        Returns:
            (WHERE clause, parameters dict)

        Example:
            >>> filter_spec = NodeFilter(field="title", operator=FilterOperator.CONTAINS, value="교육")
            >>> clause, params = CypherFilterBuilder.build_node_filter(filter_spec, "d", "f0")
            >>> clause
            "d.title CONTAINS $f0_title"
            >>> params
            {"f0_title": "교육"}

        Design Decision:
        - Parameterized queries prevent Cypher injection
        - Lambda functions for lazy evaluation
        - Each operator has explicit handling for clarity
        """
        field = filter_spec.field
        operator = filter_spec.operator
        value = filter_spec.value

        param_name = f"{param_prefix}_{field}"

        # Operator mapping with lambda for lazy evaluation
        operator_map = {
            FilterOperator.EQUALS: lambda: (
                f"{node_alias}.{field} = ${param_name}",
                {param_name: value}
            ),
            FilterOperator.NOT_EQUALS: lambda: (
                f"{node_alias}.{field} <> ${param_name}",
                {param_name: value}
            ),
            FilterOperator.CONTAINS: lambda: (
                f"{node_alias}.{field} CONTAINS ${param_name}",
                {param_name: value}
            ),
            FilterOperator.IN: lambda: (
                f"{node_alias}.{field} IN ${param_name}",
                {param_name: value if isinstance(value, list) else [value]}
            ),
            FilterOperator.NOT_IN: lambda: (
                f"NOT {node_alias}.{field} IN ${param_name}",
                {param_name: value if isinstance(value, list) else [value]}
            ),
            FilterOperator.GREATER_THAN: lambda: (
                f"{node_alias}.{field} > ${param_name}",
                {param_name: value}
            ),
            FilterOperator.LESS_THAN: lambda: (
                f"{node_alias}.{field} < ${param_name}",
                {param_name: value}
            ),
            FilterOperator.GREATER_EQUAL: lambda: (
                f"{node_alias}.{field} >= ${param_name}",
                {param_name: value}
            ),
            FilterOperator.LESS_EQUAL: lambda: (
                f"{node_alias}.{field} <= ${param_name}",
                {param_name: value}
            ),
        }

        builder = operator_map.get(operator)
        if not builder:
            raise ValueError(f"Unsupported operator: {operator}")

        return builder()

    @staticmethod
    def build_filters_clause(
        filters: List[NodeFilter],
        node_alias: str,
        param_prefix: str = "filter"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build combined WHERE clause from multiple filters

        Args:
            filters: List of filter specifications
            node_alias: Node alias in Cypher (e.g., "d")
            param_prefix: Parameter prefix (e.g., "filter")

        Returns:
            (Combined WHERE clause, All parameters)

        Example:
            >>> filters = [
            ...     NodeFilter(field="title", operator=FilterOperator.CONTAINS, value="교육"),
            ...     NodeFilter(field="status", operator=FilterOperator.EQUALS, value="active")
            ... ]
            >>> clause, params = CypherFilterBuilder.build_filters_clause(filters, "d")
            >>> clause
            "d.title CONTAINS $filter_0_title AND d.status = $filter_1_status"

        Design Decision:
        - AND combination (most common use case)
        - Empty filters return empty string (valid Cypher)
        - Each filter gets unique parameter prefix to avoid collisions
        """
        if not filters:
            return "", {}

        clauses = []
        all_params = {}

        for idx, filter_spec in enumerate(filters):
            clause, params = CypherFilterBuilder.build_node_filter(
                filter_spec, node_alias, f"{param_prefix}_{idx}"
            )
            clauses.append(clause)
            all_params.update(params)

        combined_clause = " AND ".join(clauses)
        return combined_clause, all_params

    @staticmethod
    def build_relationship_filter_clause(
        rel_filter: RelationshipFilter,
        target_alias: str,
        param_prefix: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build WHERE clause for relationship target node

        Args:
            rel_filter: Relationship filter specification
            target_alias: Target node alias (e.g., "target_0")
            param_prefix: Parameter prefix

        Returns:
            (WHERE clause, parameters dict)

        Example:
            >>> rel_filter = RelationshipFilter(
            ...     rel_type="BELONGS_TO",
            ...     target_label="Category",
            ...     target_field="name",
            ...     operator=FilterOperator.EQUALS,
            ...     value="교육"
            ... )
            >>> clause, params = CypherFilterBuilder.build_relationship_filter_clause(
            ...     rel_filter, "cat", "rel_0"
            ... )
            >>> clause
            "cat.name = $rel_0_name"

        Design Decision:
        - Reuses node filter logic for DRY
        - Relationship filters are just node filters on the target
        """
        # Create a temporary NodeFilter for the target node
        node_filter = NodeFilter(
            field=rel_filter.target_field,
            operator=rel_filter.operator,
            value=rel_filter.value
        )

        return CypherFilterBuilder.build_node_filter(
            node_filter, target_alias, param_prefix
        )
