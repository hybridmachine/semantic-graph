"""Application error types."""


class SemanticGraphError(Exception):
    """Base error for all semantic-graph errors."""


class ProjectNotFoundError(SemanticGraphError):
    """Raised when a project is not found."""


class GraphEngineError(SemanticGraphError):
    """Raised on graph engine failures."""


class LLMProviderError(SemanticGraphError):
    """Raised on LLM provider failures."""


class PathTraversalError(SemanticGraphError):
    """Raised when a resolved path escapes the allowed root directory."""


class PathSecurityError(SemanticGraphError):
    """Raised for general path-security violations (e.g. system directories)."""


class ValidationError(SemanticGraphError):
    """Raised when input validation fails before reaching Pydantic."""
