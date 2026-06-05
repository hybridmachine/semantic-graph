"""Application error types."""


class SemanticGraphError(Exception):
    """Base error for all semantic-graph errors."""


class ProjectNotFoundError(SemanticGraphError):
    """Raised when a project is not found."""


class GraphEngineError(SemanticGraphError):
    """Raised on graph engine failures."""


class LLMProviderError(SemanticGraphError):
    """Raised on LLM provider failures."""
