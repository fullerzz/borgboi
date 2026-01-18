"""Abstract base for repository storage backends.

This module defines the interface that all storage backends must implement,
enabling consistent access to repository metadata regardless of the
underlying storage mechanism.
"""

from abc import ABC, abstractmethod

from borgboi.models import BorgBoiRepo


class RepositoryStorage(ABC):
    """Abstract base class for repository storage backends.

    All storage implementations must provide these operations for managing
    repository metadata. Implementations should be thread-safe if used
    in multi-threaded contexts.
    """

    @abstractmethod
    def get(self, name: str) -> BorgBoiRepo:
        """Retrieve a repository by name.

        Args:
            name: The unique repository name

        Returns:
            The repository metadata

        Raises:
            RepositoryNotFoundError: If the repository doesn't exist
            StorageError: If retrieval fails
        """

    @abstractmethod
    def get_by_path(self, path: str, hostname: str | None = None) -> BorgBoiRepo:
        """Retrieve a repository by its path.

        Args:
            path: The repository path
            hostname: Optional hostname to disambiguate if multiple hosts
                     have repositories at the same path

        Returns:
            The repository metadata

        Raises:
            RepositoryNotFoundError: If the repository doesn't exist
            StorageError: If retrieval fails
        """

    @abstractmethod
    def list_all(self) -> list[BorgBoiRepo]:
        """List all repositories in storage.

        Returns:
            List of all repository metadata objects

        Raises:
            StorageError: If listing fails
        """

    @abstractmethod
    def save(self, repo: BorgBoiRepo) -> None:
        """Save or update repository metadata.

        If the repository already exists, it will be updated.
        If it doesn't exist, it will be created.

        Args:
            repo: The repository metadata to save

        Raises:
            ValidationError: If the repository data is invalid
            StorageError: If saving fails
        """

    @abstractmethod
    def delete(self, name: str) -> None:
        """Delete a repository by name.

        Args:
            name: The unique repository name

        Raises:
            RepositoryNotFoundError: If the repository doesn't exist
            StorageError: If deletion fails
        """

    @abstractmethod
    def exists(self, name: str) -> bool:
        """Check if a repository exists.

        Args:
            name: The unique repository name

        Returns:
            True if the repository exists, False otherwise

        Raises:
            StorageError: If the check fails
        """

    def get_by_name_or_path(
        self,
        name: str | None = None,
        path: str | None = None,
        hostname: str | None = None,
    ) -> BorgBoiRepo:
        """Retrieve a repository by name or path.

        Convenience method that accepts either name or path.

        Args:
            name: Optional repository name
            path: Optional repository path
            hostname: Optional hostname for path lookups

        Returns:
            The repository metadata

        Raises:
            ValueError: If neither name nor path is provided
            RepositoryNotFoundError: If the repository doesn't exist
            StorageError: If retrieval fails
        """
        if name is not None:
            return self.get(name)
        if path is not None:
            return self.get_by_path(path, hostname)
        raise ValueError("Either name or path must be provided")
