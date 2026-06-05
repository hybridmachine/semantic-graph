"""Abstract base extractor."""

from abc import ABC, abstractmethod


class ExtractorBase(ABC):
    """Base interface for all content extractors."""

    @abstractmethod
    def extract(self, content: str) -> dict[str, object]:
        """Extract entities and relationships from content."""
        ...
