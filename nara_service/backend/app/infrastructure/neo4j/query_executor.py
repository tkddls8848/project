"""
Neo4j Query Executor

Responsible for executing Cypher queries against Neo4j database.

Design Decision:
- This class ONLY executes queries, it does NOT build them
- Query building is Domain layer's responsibility
- Side effects (I/O) are isolated to this layer
- Follows CODING_RULES Rule 1: FP First - Isolate side effects to boundaries

CODING_RULES Compliance:
- Rule 1: FP First - I/O isolated to infrastructure boundary
- Rule 5: Error Handling - Specific exception types
- Rule 2: Architecture - Infrastructure layer, no business logic
"""
import logging
from typing import Any, Dict, List, Optional
from neo4j.exceptions import Neo4jError, ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


class Neo4jConnectionError(Exception):
    """
    Neo4j connection error

    Wraps Neo4j-specific errors for abstraction.
    """
    pass


class Neo4jQueryError(Exception):
    """
    Neo4j query execution error

    Raised when query syntax or execution fails.
    """
    pass


class Neo4jQueryExecutor:
    """
    Neo4j query executor - Infrastructure layer

    Responsibilities:
    - Execute read queries
    - Execute write queries
    - Connection management delegation
    - Error wrapping

    Non-responsibilities:
    - Query building (Domain layer)
    - Business logic (Application layer)
    """

    def __init__(self, neo4j_service):
        """
        Initialize executor

        Args:
            neo4j_service: Neo4jService singleton instance

        Design Decision:
        - Dependency injection for testability
        - neo4j_service handles connection pooling
        """
        self.neo4j_service = neo4j_service

    def execute_read(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute read-only query

        Args:
            query: Cypher query string (built by Domain layer)
            parameters: Query parameters (for parameterized queries)

        Returns:
            List of result records as dictionaries

        Raises:
            Neo4jConnectionError: Connection issues
            Neo4jQueryError: Query execution issues

        Example:
            >>> query = "MATCH (d:Document) WHERE d.title = $title RETURN d"
            >>> params = {"title": "교육"}
            >>> results = executor.execute_read(query, params)
            >>> results[0]["d"]["title"]
            "교육"

        Design Decision:
        - Returns list of dicts for easy consumption
        - All errors are wrapped in custom exceptions
        - Logging for observability
        """
        if parameters is None:
            parameters = {}

        try:
            logger.debug(f"Executing read query: {query[:100]}...")
            logger.debug(f"Parameters: {parameters}")

            with self.neo4j_service.get_session() as session:
                result = session.run(query, **parameters)
                records = [dict(record) for record in result]

                logger.debug(f"Query returned {len(records)} records")
                return records

        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Neo4j connection error: {e}", exc_info=True)
            raise Neo4jConnectionError(f"Cannot connect to Neo4j: {e}") from e

        except Neo4jError as e:
            logger.error(f"Neo4j query error: {e}", exc_info=True)
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise Neo4jQueryError(f"Query execution failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error in query execution: {e}", exc_info=True)
            raise Neo4jQueryError(f"Unexpected error: {e}") from e

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute write query

        Args:
            query: Cypher write query (CREATE, MERGE, DELETE, etc.)
            parameters: Query parameters

        Returns:
            Single result record or None

        Raises:
            Neo4jConnectionError: Connection issues
            Neo4jQueryError: Query execution issues

        Example:
            >>> query = "CREATE (d:Document {title: $title}) RETURN d"
            >>> params = {"title": "New Document"}
            >>> result = executor.execute_write(query, params)
            >>> result["d"]["title"]
            "New Document"

        Design Decision:
        - Write operations typically return single record (e.g., created node)
        - Separate method for semantic clarity (read vs write)
        """
        if parameters is None:
            parameters = {}

        try:
            logger.debug(f"Executing write query: {query[:100]}...")
            logger.debug(f"Parameters: {parameters}")

            with self.neo4j_service.get_session() as session:
                result = session.run(query, **parameters)
                single_result = result.single()

                if single_result:
                    return dict(single_result)
                return None

        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Neo4j connection error: {e}", exc_info=True)
            raise Neo4jConnectionError(f"Cannot connect to Neo4j: {e}") from e

        except Neo4jError as e:
            logger.error(f"Neo4j write error: {e}", exc_info=True)
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise Neo4jQueryError(f"Write query failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error in write execution: {e}", exc_info=True)
            raise Neo4jQueryError(f"Unexpected error: {e}") from e

    def execute_read_single(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute read query expecting single result

        Args:
            query: Cypher query
            parameters: Query parameters

        Returns:
            Single result record or None

        Example:
            >>> query = "MATCH (d:Document {id: $id}) RETURN d"
            >>> result = executor.execute_read_single(query, {"id": "123"})
            >>> result["d"] if result else None

        Design Decision:
        - Convenience method for common single-result pattern
        - Returns None instead of empty list for clarity
        """
        results = self.execute_read(query, parameters)
        return results[0] if results else None

    def execute_count(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute count query

        Args:
            query: Cypher query with COUNT() aggregation
            parameters: Query parameters

        Returns:
            Count value

        Example:
            >>> query = "MATCH (d:Document) RETURN count(d) as count"
            >>> count = executor.execute_count(query)
            >>> count
            42

        Design Decision:
        - Specialized method for count queries
        - Returns int directly for convenience
        - Expects result to have "count" field
        """
        if parameters is None:
            parameters = {}

        result = self.execute_read_single(query, parameters)
        if not result:
            return 0

        # Try to find count in result (could be "count", "cnt", or similar)
        for key in result:
            if "count" in key.lower() or key.lower() == "cnt":
                return int(result[key])

        # If no count field found, raise error
        raise ValueError(f"Count query must return a count field, got: {result.keys()}")
