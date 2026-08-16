"""
Git Worktree Manager — Local agent workspace isolation.

Allows agents to work on isolated branches and checkout folders
without duplicating git history or interfering with each other's edits.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil

logger = logging.getLogger("agent_runtime.workspace.worktree")


class WorktreeError(Exception):
    pass


class GitWorktreeManager:
    """Manages the creation, diff collection, and cleanup of Git worktrees."""

    def __init__(self, repo_root: str) -> None:
        self.repo_root = os.path.abspath(repo_root)

    async def _run_git(self, args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
        """Run a git command in the repository or worktree."""
        target_cwd = cwd or self.repo_root
        cmd = ["git"] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=target_cwd
            )
            stdout_bytes, stderr_bytes = await proc.communicate()
            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            exit_code = proc.returncode or 0
            return exit_code, stdout, stderr
        except Exception as e:
            raise WorktreeError(f"Failed to execute git command {' '.join(cmd)}: {e}")

    async def create_worktree(self, worktree_path: str, branch_name: str, base_commit: str = "HEAD") -> None:
        """Create a new git worktree at the target path on a new branch.

        Args:
            worktree_path: Directory path where the worktree should be placed.
            branch_name: Name of the new branch to create.
            base_commit: Starting commit/branch for the new branch.
        """
        abs_worktree_path = os.path.abspath(worktree_path)
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(abs_worktree_path), exist_ok=True)

        logger.info(f"Creating git worktree at {abs_worktree_path} on branch {branch_name} from {base_commit}")
        
        # git worktree add -b <branch_name> <path> <base_commit>
        exit_code, stdout, stderr = await self._run_git([
            "worktree", "add", "-b", branch_name, abs_worktree_path, base_commit
        ])
        
        if exit_code != 0:
            # Fall back to adding worktree without -b if branch already exists
            logger.warning(f"Failed to create new branch '{branch_name}'. Trying to add worktree for existing branch: {stderr}")
            exit_code, stdout, stderr = await self._run_git([
                "worktree", "add", abs_worktree_path, branch_name
            ])
            if exit_code != 0:
                raise WorktreeError(f"Failed to add git worktree: {stderr}")

    async def cleanup_worktree(self, worktree_path: str) -> None:
        """Prune and delete a git worktree.

        Args:
            worktree_path: The directory path of the worktree to clean up.
        """
        abs_worktree_path = os.path.abspath(worktree_path)
        logger.info(f"Cleaning up git worktree at {abs_worktree_path}")

        # 1. Force remove the worktree via git
        exit_code, stdout, stderr = await self._run_git([
            "worktree", "remove", "--force", abs_worktree_path
        ])
        if exit_code != 0:
            logger.warning(f"Git worktree remove returned non-zero code: {stderr}")

        # 2. Prune old worktree metadata
        await self._run_git(["worktree", "prune"])

        # 3. Clean up the physical directory on disk if it still exists
        if os.path.exists(abs_worktree_path):
            try:
                await asyncio.to_thread(shutil.rmtree, abs_worktree_path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to physically delete worktree directory {abs_worktree_path}: {e}")

    async def get_diff(self, worktree_path: str) -> str:
        """Retrieve the git diff of the changes made inside the worktree.

        Args:
            worktree_path: The worktree directory path.
        """
        abs_worktree_path = os.path.abspath(worktree_path)
        exit_code, stdout, stderr = await self._run_git(["diff", "HEAD"], cwd=abs_worktree_path)
        if exit_code != 0:
            raise WorktreeError(f"Failed to get diff from worktree: {stderr}")
        return stdout

    async def commit_changes(self, worktree_path: str, message: str) -> str:
        """Add and commit changes inside the worktree.

        Args:
            worktree_path: The worktree directory path.
            message: Commit message.
        """
        abs_worktree_path = os.path.abspath(worktree_path)
        
        # git add .
        exit_code, stdout, stderr = await self._run_git(["add", "."], cwd=abs_worktree_path)
        if exit_code != 0:
            raise WorktreeError(f"Failed to git add changes: {stderr}")

        # git commit -m message
        exit_code, stdout, stderr = await self._run_git(["commit", "-m", message], cwd=abs_worktree_path)
        if exit_code != 0 and "nothing to commit" not in stdout.lower() and "nothing to commit" not in stderr.lower():
            raise WorktreeError(f"Failed to git commit changes: {stderr or stdout}")
            
        # Get committed SHA
        exit_code, stdout, stderr = await self._run_git(["rev-parse", "HEAD"], cwd=abs_worktree_path)
        return stdout.strip()
