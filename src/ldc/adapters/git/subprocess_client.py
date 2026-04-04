"""
Adapter: git operations via the system git binary (via subprocess).
Works on Windows with Git for Windows / GitBash.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ldc.ports.git_client import IGitClient


class SubprocessGitClient(IGitClient):

    def clone(self, repo_url: str, dest: Path, branch: str = "main") -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            ["git", "clone", "--branch", branch, "--depth", "1", repo_url, dest.name],
            cwd=str(dest.parent),
        )

    def pull(self, repo_dir: Path, branch: str = "main") -> None:
        self._run(["git", "fetch", "origin"], cwd=str(repo_dir))
        self._run(
            ["git", "checkout", branch], cwd=str(repo_dir)
        )
        self._run(
            ["git", "pull", "origin", branch, "--ff-only"],
            cwd=str(repo_dir),
        )

    def is_cloned(self, dest: Path) -> bool:
        git_dir = dest / ".git"
        return git_dir.exists()

    def current_branch(self, repo_dir: Path) -> str:
        result = self._run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_dir),
            capture=True,
        )
        return result.stdout.strip()

    # ------------------------------------------------------------------

    def _run(
        self,
        cmd: list,
        cwd: str,
        capture: bool = False,
    ) -> subprocess.CompletedProcess:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() if capture else ""
            raise RuntimeError(
                f"git command failed (exit {result.returncode}): {' '.join(cmd)}\n{stderr}"
            )
        return result
