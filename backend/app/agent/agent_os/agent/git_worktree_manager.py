"""
Git worktree manager for isolated parallel agent execution.

Each agent gets its own worktree from a common base commit, enabling:
  - Parallel execution without conflicts
  - Automatic merge after completion
  - Conflict detection and resolution
  - Easy rollback per agent
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .workspace import Workspace


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""
    agent_id: str
    branch: str
    worktree_path: str
    base_commit: str
    created_at: datetime
    status: str  # active, merged, abandoned


class GitWorktreeManager:
    """Manages isolated git worktrees for parallel agents."""

    def __init__(self, repository_root: str):
        """
        Initialize worktree manager.

        Args:
            repository_root: Path to git repository root
        """
        self.repository_root = repository_root
        self.workspace = Workspace(repository_root)
        self.worktrees: dict[str, WorktreeInfo] = {}

    async def create_worktree(self, agent_id: str) -> tuple[bool, str]:
        """
        Create isolated worktree for agent.

        Args:
            agent_id: Unique agent identifier

        Returns:
            (success, worktree_path or error_message)
        """
        try:
            # Get current branch and commit
            result = await self.workspace.run_command("git rev-parse --abbrev-ref HEAD")
            if not result["success"]:
                return False, f"Failed to get current branch: {result['stderr']}"

            current_branch = result["stdout"].strip()

            result = await self.workspace.run_command("git rev-parse HEAD")
            if not result["success"]:
                return False, f"Failed to get current commit: {result['stderr']}"

            base_commit = result["stdout"].strip()

            # Create worktree
            worktree_name = f"worktree-{agent_id}"
            worktree_path = Path(self.repository_root).parent / "worktrees" / worktree_name
            branch_name = f"agent/{agent_id}"

            cmd = f"git worktree add -b {branch_name} {worktree_path} {base_commit}"
            result = await self.workspace.run_command(cmd)

            if not result["success"]:
                return False, f"Failed to create worktree: {result['stderr']}"

            # Record worktree info
            self.worktrees[agent_id] = WorktreeInfo(
                agent_id=agent_id,
                branch=branch_name,
                worktree_path=str(worktree_path),
                base_commit=base_commit,
                created_at=datetime.utcnow(),
                status="active",
            )

            return True, str(worktree_path)

        except Exception as e:
            return False, f"Exception creating worktree: {e!s}"

    async def remove_worktree(self, agent_id: str, prune: bool = True) -> tuple[bool, str]:
        """
        Remove worktree for agent.

        Args:
            agent_id: Agent identifier
            prune: Whether to prune after removal

        Returns:
            (success, message)
        """
        if agent_id not in self.worktrees:
            return False, f"Worktree not found for agent {agent_id}"

        worktree_info = self.worktrees[agent_id]
        worktree_path = worktree_info.worktree_path

        try:
            # Remove worktree
            cmd = f"git worktree remove {worktree_path}"
            result = await self.workspace.run_command(cmd)

            if not result["success"]:
                return False, f"Failed to remove worktree: {result['stderr']}"

            # Prune if requested
            if prune:
                cmd = "git worktree prune"
                result = await self.workspace.run_command(cmd)

            # Remove from tracking
            del self.worktrees[agent_id]

            return True, "Worktree removed successfully"

        except Exception as e:
            return False, f"Exception removing worktree: {e!s}"

    async def merge_worktree(self, agent_id: str) -> tuple[bool, dict[str, any]]:
        """
        Merge worktree back to main branch.

        Args:
            agent_id: Agent identifier

        Returns:
            (success, result_dict with merge info or conflicts)
        """
        if agent_id not in self.worktrees:
            return False, {"error": f"Worktree not found for agent {agent_id}"}

        worktree_info = self.worktrees[agent_id]

        try:
            # Get current branch
            result = await self.workspace.run_command("git rev-parse --abbrev-ref HEAD")
            if not result["success"]:
                return False, {"error": f"Failed to get branch: {result['stderr']}"}

            main_branch = result["stdout"].strip()

            # Checkout main branch
            result = await self.workspace.run_command(f"git checkout {main_branch}")
            if not result["success"]:
                return False, {"error": f"Failed to checkout {main_branch}: {result['stderr']}"}

            # Try to merge agent's branch
            result = await self.workspace.run_command(
                f"git merge {worktree_info.branch} --no-edit"
            )

            if result["success"]:
                # Merge succeeded
                worktree_info.status = "merged"
                return True, {
                    "status": "merged",
                    "message": "Merged successfully",
                }
            else:
                # Check for conflicts
                result = await self.workspace.run_command("git status --porcelain")
                conflicts = [line for line in result["stdout"].split("\n") if line.startswith("UU")]

                if conflicts:
                    return False, {
                        "status": "conflict",
                        "conflicts": conflicts,
                        "branch": worktree_info.branch,
                        "message": "Merge conflicts detected",
                    }
                else:
                    return False, {
                        "status": "failed",
                        "error": result["stderr"],
                    }

        except Exception as e:
            return False, {"error": f"Exception during merge: {e!s}"}

    async def detect_conflicts(self, agent_id_1: str, agent_id_2: str) -> tuple[bool, list[str]]:
        """
        Detect conflicts between two agents' worktrees.

        Args:
            agent_id_1: First agent
            agent_id_2: Second agent

        Returns:
            (has_conflicts, list_of_conflicting_files)
        """
        if agent_id_1 not in self.worktrees or agent_id_2 not in self.worktrees:
            return False, []

        wt1 = self.worktrees[agent_id_1]
        wt2 = self.worktrees[agent_id_2]

        try:
            # Check for file overlap
            result = await self.workspace.run_command(
                f"git diff {wt1.branch}...{wt2.branch} --name-only"
            )

            if not result["success"]:
                return False, []

            # If both modified same files, conflict
            files = result["stdout"].strip().split("\n")

            conflicting_files = []
            for file in files:
                if file:
                    # Check if modified by both
                    result = await self.workspace.run_command(
                        f"git log {wt1.branch} --oneline -- {file} | wc -l"
                    )
                    edits_1 = int(result["stdout"].strip()) if result["success"] else 0

                    result = await self.workspace.run_command(
                        f"git log {wt2.branch} --oneline -- {file} | wc -l"
                    )
                    edits_2 = int(result["stdout"].strip()) if result["success"] else 0

                    if edits_1 > 0 and edits_2 > 0:
                        conflicting_files.append(file)

            return len(conflicting_files) > 0, conflicting_files

        except Exception:
            return False, []

    async def resolve_conflict_auto(
        self,
        agent_id: str,
        strategy: str = "ours"
    ) -> tuple[bool, str]:
        """
        Attempt automatic conflict resolution.

        Args:
            agent_id: Agent identifier
            strategy: Resolution strategy (ours, theirs, manual)

        Returns:
            (success, message)
        """
        if agent_id not in self.worktrees:
            return False, "Worktree not found"

        try:
            if strategy == "ours":
                # Keep agent's changes
                cmd = "git checkout --ours ."
            elif strategy == "theirs":
                # Keep main branch changes
                cmd = "git checkout --theirs ."
            else:
                return False, "Strategy not supported for auto resolution"

            result = await self.workspace.run_command(cmd)
            if not result["success"]:
                return False, f"Failed to resolve: {result['stderr']}"

            # Stage resolution
            result = await self.workspace.run_command("git add .")
            if not result["success"]:
                return False, f"Failed to stage: {result['stderr']}"

            return True, f"Conflicts resolved using {strategy} strategy"

        except Exception as e:
            return False, f"Exception resolving conflicts: {e!s}"

    async def get_worktree_diff(self, agent_id: str) -> tuple[bool, str]:
        """
        Get diff for agent's worktree.

        Args:
            agent_id: Agent identifier

        Returns:
            (success, diff_output)
        """
        if agent_id not in self.worktrees:
            return False, "Worktree not found"

        worktree_info = self.worktrees[agent_id]

        try:
            result = await self.workspace.run_command(
                f"git diff {worktree_info.base_commit}...{worktree_info.branch}"
            )

            if result["success"]:
                return True, result["stdout"]
            else:
                return False, result["stderr"]

        except Exception as e:
            return False, str(e)

    def get_worktree_info(self, agent_id: str) -> WorktreeInfo | None:
        """Get information about agent's worktree."""
        return self.worktrees.get(agent_id)

    def list_active_worktrees(self) -> list[WorktreeInfo]:
        """List all active worktrees."""
        return [wt for wt in self.worktrees.values() if wt.status == "active"]

    async def cleanup_worktrees(self) -> int:
        """
        Clean up all inactive worktrees.

        Returns:
            Number of worktrees cleaned up
        """
        inactive = [wt for wt in self.worktrees.values() if wt.status != "active"]
        cleaned = 0

        for worktree in inactive:
            success, _ = await self.remove_worktree(worktree.agent_id)
            if success:
                cleaned += 1

        return cleaned
