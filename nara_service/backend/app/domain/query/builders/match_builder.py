"""
Cypher Match Builder - Pure Functions

Builds Cypher MATCH patterns for relationship traversals.

Design Decision:
- Pure functions for MATCH pattern generation
- Handles relationship filters with target node constraints
- Generates unique aliases to avoid collisions

CODING_RULES Compliance:
- Rule 1: FP First - Pure functions only
- Rule 1: KISS - Clear and simple pattern generation
"""
from typing import Dict, Any, Tuple, List
from app.domain.query.models.filters import RelationshipFilter
from app.domain.query.builders.filter_builder import CypherFilterBuilder


class CypherMatchBuilder:
    """
    Cypher MATCH pattern builder

    All methods are static pure functions.
    """

    @staticmethod
    def build_relationship_pattern(
        rel_filter: RelationshipFilter,
        source_alias: str,
        target_alias: str,
        rel_alias: str
    ) -> str:
        """
        Build MATCH pattern for a single relationship

        Args:
            rel_filter: Relationship filter specification
            source_alias: Source node alias (e.g., "d")
            target_alias: Target node alias (e.g., "target_0")
            rel_alias: Relationship alias (e.g., "rel_0")

        Returns:
            MATCH pattern string

        Example:
            >>> rel_filter = RelationshipFilter(
            ...     rel_type="BELONGS_TO",
            ...     target_label="Category",
            ...     target_field="name",
            ...     operator=FilterOperator.EQUALS,
            ...     value="교육"
            ... )
            >>> pattern = CypherMatchBuilder.build_relationship_pattern(
            ...     rel_filter, "d", "cat", "rel"
            ... )
            >>> pattern
            "MATCH (d)-[rel:BELONGS_TO]->(cat:Category)"

        Design Decision:
        - Uses directed relationships (->)
        - Labels and types are explicitly specified
        - Aliases allow for complex queries with multiple relationships
        """
        rel_type = rel_filter.rel_type
        target_label = rel_filter.target_label

        pattern = f"MATCH ({source_alias})-[{rel_alias}:{rel_type}]->({target_alias}:{target_label})"
        return pattern

    @staticmethod
    def build_relationship_patterns(
        rel_filters: List[RelationshipFilter],
        source_alias: str
    ) -> Tuple[List[str], str, Dict[str, Any]]:
        """
        Build MATCH patterns and WHERE clauses for multiple relationships

        Args:
            rel_filters: List of relationship filter specifications
            source_alias: Source node alias (e.g., "d")

        Returns:
            (MATCH patterns list, combined WHERE clause, all parameters)

        Example:
            >>> rel_filters = [
            ...     RelationshipFilter(
            ...         rel_type="BELONGS_TO",
            ...         target_label="Category",
            ...         target_field="name",
            ...         operator=FilterOperator.EQUALS,
            ...         value="교육"
            ...     )
            ... ]
            >>> patterns, where, params = CypherMatchBuilder.build_relationship_patterns(
            ...     rel_filters, "d"
            ... )
            >>> patterns
            ["MATCH (d)-[rel_0:BELONGS_TO]->(target_0:Category)"]
            >>> where
            "target_0.name = $rel_filter_0_name"
            >>> params
            {"rel_filter_0_name": "교육"}

        Design Decision:
        - Each relationship gets unique aliases (target_0, rel_0, etc.)
        - WHERE clauses are combined with AND
        - Empty filters return empty lists/strings
        """
        if not rel_filters:
            return [], "", {}

        patterns = []
        where_clauses = []
        all_params = {}

        for idx, rel_filter in enumerate(rel_filters):
            target_alias = f"target_{idx}"
            rel_alias = f"rel_{idx}"
            param_prefix = f"rel_filter_{idx}"

            # Build MATCH pattern
            pattern = CypherMatchBuilder.build_relationship_pattern(
                rel_filter, source_alias, target_alias, rel_alias
            )
            patterns.append(pattern)

            # Build WHERE clause for target node
            where_clause, params = CypherFilterBuilder.build_relationship_filter_clause(
                rel_filter, target_alias, param_prefix
            )
            where_clauses.append(where_clause)
            all_params.update(params)

        # Combine WHERE clauses
        combined_where = " AND ".join(where_clauses) if where_clauses else ""

        return patterns, combined_where, all_params

    @staticmethod
    def build_path_pattern(
        source_alias: str,
        target_alias: str,
        rel_types: List[str] = None,
        min_hops: int = 1,
        max_hops: int = 5,
        direction: str = "->"
    ) -> str:
        """
        Build variable-length path pattern

        Args:
            source_alias: Source node alias
            target_alias: Target node alias
            rel_types: Optional list of relationship types
            min_hops: Minimum path length
            max_hops: Maximum path length
            direction: Relationship direction ("->", "<-", "-")

        Returns:
            Path pattern string

        Example:
            >>> pattern = CypherMatchBuilder.build_path_pattern("d1", "d2", ["RELATED_TO"], 1, 3)
            >>> pattern
            "MATCH (d1)-[:RELATED_TO*1..3]->(d2)"

        Design Decision:
        - Variable-length paths for flexible traversal
        - Configurable hop limits to prevent runaway queries
        - Optional relationship type filtering
        """
        # Build relationship type filter
        rel_type_str = ""
        if rel_types:
            rel_type_str = ":" + "|".join(rel_types)

        # Build hop range
        hop_range = f"*{min_hops}..{max_hops}"

        # Determine arrow direction
        if direction == "->":
            arrow_left, arrow_right = "-", "->"
        elif direction == "<-":
            arrow_left, arrow_right = "<-", "-"
        else:  # "-" (undirected)
            arrow_left, arrow_right = "-", "-"

        pattern = f"MATCH ({source_alias}){arrow_left}[{rel_type_str}{hop_range}]{arrow_right}({target_alias})"
        return pattern

    @staticmethod
    def build_optional_match_pattern(
        source_alias: str,
        rel_filter: RelationshipFilter,
        target_alias: str,
        rel_alias: str
    ) -> str:
        """
        Build OPTIONAL MATCH pattern

        Args:
            source_alias: Source node alias
            rel_filter: Relationship filter specification
            target_alias: Target node alias
            rel_alias: Relationship alias

        Returns:
            OPTIONAL MATCH pattern string

        Example:
            >>> pattern = CypherMatchBuilder.build_optional_match_pattern("d", rel_filter, "opt", "r")
            >>> pattern
            "OPTIONAL MATCH (d)-[r:BELONGS_TO]->(opt:Category)"

        Design Decision:
        - OPTIONAL MATCH for nullable relationships
        - Useful for LEFT JOIN-like queries
        """
        base_pattern = CypherMatchBuilder.build_relationship_pattern(
            rel_filter, source_alias, target_alias, rel_alias
        )
        # Replace "MATCH" with "OPTIONAL MATCH"
        optional_pattern = base_pattern.replace("MATCH", "OPTIONAL MATCH", 1)
        return optional_pattern
