"""Port: interacts with git repositories."""
from abc import ABC, abstractmethod
from pathlib import Path


class IGitClient(ABC):

    @abstractmethod
    def clone(self, repo_url: str, dest: Path, branch: str = "main") -> None:
        """Clone *repo_url* at *branch* into *dest*. Raises on failure."""

    @abstractmethod
    def pull(self, repo_dir: Path, branch: str = "main") -> None:
        """Pull latest changes in an already-cloned repo. Raises on failure."""

    @abstractmethod
    def is_cloned(self, dest: Path) -> bool:
        """Return True if *dest* is already a valid git repository."""

    @abstractmethod
    def current_branch(self, repo_dir: Path) -> str:
        """Return the active branch name."""
