"""Unit tests for GitWatcher.

All git subprocess calls are mocked — no real git repository needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from rime.ctrl.watcher import GitWatcher


FAKE_REPO = Path("/fake/rime-ops")
COMMIT_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
COMMIT_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


@pytest.fixture()
def watcher() -> GitWatcher:
    return GitWatcher(FAKE_REPO, remote="origin", branch="main")


# ---------------------------------------------------------------------------
# current_commit
# ---------------------------------------------------------------------------

class TestCurrentCommit:
    def test_returns_stripped_sha(self, watcher):
        with patch.object(watcher, "_run_git", return_value=COMMIT_A + "\n"):
            result = watcher.current_commit()
        assert result == COMMIT_A

    def test_raises_on_git_failure(self, watcher):
        with patch.object(watcher, "_run_git", side_effect=RuntimeError("not a repo")):
            with pytest.raises(RuntimeError, match="not a repo"):
                watcher.current_commit()


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------

class TestPull:
    def test_returns_true_when_new_commits_pulled(self, watcher):
        call_count = 0

        def fake_current_commit():
            nonlocal call_count
            call_count += 1
            return COMMIT_A if call_count == 1 else COMMIT_B

        with patch.object(watcher, "current_commit", side_effect=fake_current_commit), \
             patch.object(watcher, "_run_git"):
            result = watcher.pull()

        assert result is True

    def test_returns_false_when_already_up_to_date(self, watcher):
        with patch.object(watcher, "current_commit", return_value=COMMIT_A), \
             patch.object(watcher, "_run_git"):
            result = watcher.pull()

        assert result is False

    def test_returns_false_when_remote_unreachable(self, watcher):
        with patch.object(watcher, "current_commit", return_value=COMMIT_A), \
             patch.object(watcher, "_run_git", side_effect=RuntimeError("network error")):
            result = watcher.pull()

        assert result is False

    def test_calls_git_pull_with_correct_remote_and_branch(self, watcher):
        with patch.object(watcher, "current_commit", return_value=COMMIT_A), \
             patch.object(watcher, "_run_git") as mock_git:
            watcher.pull()

        mock_git.assert_called_once_with("pull", "origin", "main")


# ---------------------------------------------------------------------------
# has_changes
# ---------------------------------------------------------------------------

class TestHasChanges:
    def test_returns_true_on_new_commits(self, watcher):
        with patch.object(watcher, "pull", return_value=True), \
             patch.object(watcher, "current_commit", return_value=COMMIT_B):
            result = watcher.has_changes()

        assert result is True

    def test_returns_false_when_no_new_commits(self, watcher):
        with patch.object(watcher, "pull", return_value=False):
            result = watcher.has_changes()

        assert result is False

    def test_updates_last_commit_on_change(self, watcher):
        with patch.object(watcher, "pull", return_value=True), \
             patch.object(watcher, "current_commit", return_value=COMMIT_B):
            watcher.has_changes()

        assert watcher._last_commit == COMMIT_B

    def test_does_not_update_last_commit_when_unchanged(self, watcher):
        watcher._last_commit = COMMIT_A
        with patch.object(watcher, "pull", return_value=False):
            watcher.has_changes()

        assert watcher._last_commit == COMMIT_A


# ---------------------------------------------------------------------------
# initialise
# ---------------------------------------------------------------------------

class TestInitialise:
    def test_sets_last_commit(self, watcher):
        with patch.object(watcher, "current_commit", return_value=COMMIT_A):
            watcher.initialise()

        assert watcher._last_commit == COMMIT_A

    def test_raises_if_not_a_git_repo(self, watcher):
        with patch.object(
            watcher, "current_commit", side_effect=RuntimeError("not a git repo")
        ):
            with pytest.raises(RuntimeError):
                watcher.initialise()


# ---------------------------------------------------------------------------
# _run_git (subprocess integration)
# ---------------------------------------------------------------------------

class TestRunGit:
    def test_returns_stdout_on_success(self, watcher):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = COMMIT_A + "\n"

        with patch("rime.ctrl.watcher.subprocess.run", return_value=mock_result):
            result = watcher._run_git("rev-parse", "HEAD")

        assert result == COMMIT_A + "\n"

    def test_raises_on_non_zero_exit(self, watcher):
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: not a git repository"
        mock_result.stdout = ""

        with patch("rime.ctrl.watcher.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="not a git repository"):
                watcher._run_git("rev-parse", "HEAD")

    def test_runs_in_repo_directory(self, watcher):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("rime.ctrl.watcher.subprocess.run", return_value=mock_result) as mock_run:
            watcher._run_git("status")

        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == FAKE_REPO
