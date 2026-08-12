"""
Phase 10: Professional Git, Collaboration & Change Management.

Provides AI Change Attribution (User vs AI vs Generated code), 3-way merge conflict
resolution (ours, theirs, base), and Prepare Change PR summaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ChangeAttribution:
    user_modified_files: List[str] = field(default_factory=list)
    ai_modified_files: List[str] = field(default_factory=list)
    generated_files: List[str] = field(default_factory=list)


@dataclass
class MergeConflictSection:
    file_path: str
    ours_content: str
    theirs_content: str
    base_content: Optional[str] = None
    suggested_resolution: Optional[str] = None


@dataclass
class PrepareChangeSummary:
    task_goal: str
    branch_name: str
    commit_message: str
    pr_description: str
    files_changed_count: int
    verification_passed: bool


class GitCollaborationEngine:
    """Manages AI change attribution, conflict resolution, and PR summaries."""

    @classmethod
    def attribute_changes(
        cls,
        working_tree_files: List[str],
        ai_tracked_files: List[str],
    ) -> ChangeAttribution:
        """Distinguish AI-modified files from pre-existing user modifications."""
        ai_set = set(ai_tracked_files)
        user_files = [f for f in working_tree_files if f not in ai_set]
        ai_files = [f for f in working_tree_files if f in ai_set]
        gen_files = [f for f in ai_files if "generated" in f.lower() or f.endswith(".min.js")]

        return ChangeAttribution(
            user_modified_files=user_files,
            ai_modified_files=ai_files,
            generated_files=gen_files,
        )

    @classmethod
    def parse_merge_conflict(cls, file_path: str, conflict_text: str) -> MergeConflictSection:
        """Parse 3-way git merge conflict blocks (<<<<<<< ours ======= >>>>>>> theirs)."""
        pattern = r"<<<<<<< (.*?)\n(.*?)\n=======\n(.*?)\n>>>>>>> (.*?)"
        match = re.search(pattern, conflict_text, re.DOTALL)

        if match:
            ours = match.group(2)
            theirs = match.group(3)
            # Combine non-conflicting lines as resolution proposal
            resolution = f"# Resolved Merge Conflict ({file_path})\n{ours}\n{theirs}"
            return MergeConflictSection(
                file_path=file_path,
                ours_content=ours,
                theirs_content=theirs,
                suggested_resolution=resolution,
            )

        return MergeConflictSection(
            file_path=file_path,
            ours_content=conflict_text,
            theirs_content=conflict_text,
            suggested_resolution=conflict_text,
        )

    @classmethod
    def generate_prepare_change_summary(
        cls,
        task_goal: str,
        files_changed: List[str],
        verification_passed: bool,
    ) -> PrepareChangeSummary:
        """Generate PR-ready summary and commit message."""
        commit_msg = f"feat(ai): {task_goal.lower().strip('.')}"
        pr_desc = (
            f"## Summary of AI Changes\n"
            f"**Goal:** {task_goal}\n"
            f"**Files Modified:** {len(files_changed)}\n"
            f"**Verification Status:** {'✓ Passed' if verification_passed else '⚠ Failed'}\n\n"
            f"### Changed Files:\n" + "\n".join(f"- `{f}`" for f in files_changed)
        )

        return PrepareChangeSummary(
            task_goal=task_goal,
            branch_name="feature/ai-agent-update",
            commit_message=commit_msg,
            pr_description=pr_desc,
            files_changed_count=len(files_changed),
            verification_passed=verification_passed,
        )
