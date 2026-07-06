"""Worktree allocation + branch naming policy (Phase 4).

Like the tmux client, git access goes through a narrow :class:`GitClient` seam
(argument-array subprocess, never a shell string) so tests can fake it and a
non-git project degrades cleanly.

Safety posture: by default this module **plans** worktrees (computes a
deterministic branch name and isolated path) but does **not** run any mutating
git command. Actual `git worktree add` happens only when explicitly requested
and a real repo is present. No destructive git commands are ever issued, and
`git init` is never run.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import WorktreeMode


class GitClient:
    def __init__(self, binary: str = "git", timeout: float = 5.0):
        self.binary = binary
        self.timeout = timeout

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def _run(self, args, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.binary, *args],
            capture_output=True, text=True, timeout=self.timeout, check=False, cwd=cwd,
        )

    def is_repo(self, path: str) -> bool:
        if not self.available():
            return False
        try:
            res = self._run(["rev-parse", "--is-inside-work-tree"], cwd=str(path))
        except (OSError, subprocess.SubprocessError):
            return False
        return res.returncode == 0 and res.stdout.strip() == "true"

    def add_worktree(self, repo: str, worktree_path: str, branch: str) -> bool:
        """Create an isolated worktree on a new branch. Non-destructive.

        Only called when the caller explicitly opts into creation.
        """
        try:
            res = self._run(["worktree", "add", "-b", branch, worktree_path, "HEAD"], cwd=str(repo))
            return res.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 40) -> str:
    slug = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return slug[:max_len].strip("-") or "task"


def branch_name(track_id: str, task_id: str, title: str) -> str:
    """Deterministic, safe branch name: ``conductor/<track>/<task>-<slug>``."""
    return f"conductor/{track_id}/{task_id}-{slugify(title)}"


@dataclass
class WorktreeAllocation:
    mode: WorktreeMode
    branch: str
    workspace: str
    worktree_path: Optional[str]
    is_git_repo: bool

    def to_dict(self):
        return {
            "mode": self.mode.value,
            "branch": self.branch,
            "workspace": self.workspace,
            "worktree_path": self.worktree_path,
            "is_git_repo": self.is_git_repo,
        }


def allocate_worktree(project_root: Path, track_id: str, task_id: str, title: str,
                      git: Optional[GitClient] = None, create: bool = False) -> WorktreeAllocation:
    """Allocate (or plan) an isolated workspace for a task.

    - Non-git project root → ``not_git_repo``: use the current root as workspace,
      no git commands run.
    - Git repo → ``git_planned`` (branch + worktree path computed) or, if
      ``create=True`` and the add succeeds, ``git_worktree``.
    """
    git = git if git is not None else GitClient()
    project_root = Path(project_root)
    branch = branch_name(track_id, task_id, title)

    if not git.is_repo(str(project_root)):
        return WorktreeAllocation(
            mode=WorktreeMode.NOT_GIT_REPO,
            branch=branch,
            workspace=str(project_root),
            worktree_path=None,
            is_git_repo=False,
        )

    planned_path = str(project_root / ".conductor" / "worktrees" / track_id / task_id)
    if create and git.add_worktree(str(project_root), planned_path, branch):
        return WorktreeAllocation(
            mode=WorktreeMode.GIT_WORKTREE,
            branch=branch,
            workspace=planned_path,
            worktree_path=planned_path,
            is_git_repo=True,
        )

    return WorktreeAllocation(
        mode=WorktreeMode.GIT_PLANNED,
        branch=branch,
        workspace=str(project_root),
        worktree_path=planned_path,
        is_git_repo=True,
    )
