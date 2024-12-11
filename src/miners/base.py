"""
Abstract Base Class for Repository Miners.

Defines the interface for repository data mining implementations.
All repository miners (GitHub, GitLab, etc.) should implement this interface.
"""

from abc import ABC, abstractmethod

from miners.models import RepositoryData


class RepositoryMiner(ABC):
    """
    Abstract base class for repository miners.

    Defines the contract for mining repository data from different sources.
    Implementations should handle:
    - Authentication with the repository service
    - Data extraction
    - Data transformation to common models
    - Data persistence
    """

    @abstractmethod
    async def mine_repository(self, repo_name: str) -> RepositoryData:
        """
        Extract all relevant data from a repository.

        Args:
            repo_name (str): Full repository name/identifier

        Returns:
            RepositoryData: Collected repository data

        Raises:
            Exception: If mining fails
        """
        pass
