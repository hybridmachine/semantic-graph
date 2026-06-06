"""Repository pattern implementations.

Each model has a dedicated repository class with standard CRUD operations
plus model-specific query methods.
"""

from semantic_graph.storage.repositories.base import BaseRepository
from semantic_graph.storage.repositories.edge import EdgeRepository
from semantic_graph.storage.repositories.file_manifest import (
    FileManifestEntryRepository,
)
from semantic_graph.storage.repositories.node import NodeRepository
from semantic_graph.storage.repositories.processing_job import (
    ProcessingJobRepository,
)
from semantic_graph.storage.repositories.project import ProjectRepository

__all__ = [
    "BaseRepository",
    "EdgeRepository",
    "FileManifestEntryRepository",
    "NodeRepository",
    "ProcessingJobRepository",
    "ProjectRepository",
]
