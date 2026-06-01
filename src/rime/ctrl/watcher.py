"""Git-based config watcher for the ctrl-plane.

Polls a local git repository for new commits. When a change is detected
the caller is responsible for triggering a reconcile.

Design notes
------------
- The ops repo (rime-ops) is assumed to already be cloned locally.
  The watcher just runs ``git pull`` and compares commit hashes.
- Pulling is intentionally synchronous — if the remote is unreachable
  we log a warning and retry on the next interval rather than crashing.
- No external git library required: we shell out to git, which is always
  available in the deployment environment.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("ctrl.watcher")


class GitWatcher:
    """Watches a local git repository for upstream changes.

    Args:
        repo_path: Absolute path to the cloned ops repository.
        remote: Git remote name (default: ``origin``).
        branch: Branch to track (default: ``main``).
    """

    def __init__(
        self,
        repo_path: Path,
        remote: str = "origin",
        branch: str = "main",
    ) -> None:
        self.repo_path = repo_path
        self.remote = remote
        self.branch = branch
        self._last_commit: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def current_commit(self) -> str:
        """Return the SHA of the current HEAD commit.

        Raises:
            RuntimeError: If the git command fails (not a repo, etc.).
        """
        return self._run_git("rev-parse", "HEAD").strip()

    def pull(self) -> bool:
        """Pull the latest changes from the remote.

        Returns:
            True if new commits were pulled, False if already up to date.

        Note:
            Returns False (no change) if the remote is unreachable, so the
            caller can safely call this in a loop without crashing.
        """
        before = self.current_commit()
        try:
            self._run_git("pull", self.remote, self.branch)
        except RuntimeError as exc:
            logger.warning("git pull failed, will retry later: %s", exc)
            return False

        after = self.current_commit()
        changed = before != after
        if changed:
            logger.info(
                "New commits pulled: %s → %s", before[:8], after[:8]
            )
        return changed

    def has_changes(self) -> bool:
        """Pull and return True if new commits arrived since last check.

        Convenience wrapper around ``pull()`` that also updates the internal
        last-seen commit so repeated calls only return True once per change.
        """
        changed = self.pull()
        if changed:
            self._last_commit = self.current_commit()
        return changed

    def initialise(self) -> None:
        """Record the current HEAD so the first ``has_changes`` call is clean.

        Call this once before entering the poll loop to avoid treating the
        initial state as a change.
        """
        self._last_commit = self.current_commit()
        logger.info("Watcher initialised at commit %s", self._last_commit[:8])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_git(self, *args: str) -> str:
        """Run a git command in the repo directory and return stdout.

        Raises:
            RuntimeError: If the command exits with a non-zero return code.
        """
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {result.stderr.strip()}"
            )
        return result.stdout
