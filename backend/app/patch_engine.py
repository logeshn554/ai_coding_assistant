"""
Patch Engine — Parses and applies unified diff patches safely to workspace files.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from .files import safe_path, write_workspace_file

logger = logging.getLogger("loopix.patch_engine")


@dataclass
class DiffHunk:
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    lines: list[str]


class PatchEngine:
    """Parses standard unified diff syntax and applies hunks to source files."""

    @staticmethod
    def parse_hunks(diff_text: str) -> list[DiffHunk]:
        """Parse unified diff hunks from a diff string."""
        hunks: list[DiffHunk] = []
        hunk_header_re = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

        lines = diff_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            match = hunk_header_re.match(line)
            if match:
                old_start = int(match.group(1))
                old_lines = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_lines = int(match.group(4)) if match.group(4) else 1

                hunk_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("@@"):
                    hunk_lines.append(lines[i])
                    i += 1

                hunks.append(
                    DiffHunk(
                        old_start=old_start,
                        old_lines=old_lines,
                        new_start=new_start,
                        new_lines=new_lines,
                        lines=hunk_lines,
                    )
                )
            else:
                i += 1

        return hunks

    @classmethod
    def apply_patch(cls, original_content: str, diff_text: str) -> str:
        """Apply unified diff hunks to original text content."""
        hunks = cls.parse_hunks(diff_text)
        if not hunks:
            # If no hunk header, attempt direct replacement if replacement format is clean
            return original_content

        orig_lines = original_content.splitlines()
        result_lines = list(orig_lines)
        line_offset = 0

        for hunk in hunks:
            target_idx = hunk.old_start - 1 + line_offset
            target_idx = max(target_idx, 0)

            # Collect new lines replacement for this hunk
            new_sub_lines = []
            old_count = 0

            for h_line in hunk.lines:
                if h_line.startswith("+"):
                    new_sub_lines.append(h_line[1:])
                elif h_line.startswith("-"):
                    old_count += 1
                elif h_line.startswith(" "):
                    new_sub_lines.append(h_line[1:])
                    old_count += 1

            # Replace lines in result array
            result_lines[target_idx : target_idx + old_count] = new_sub_lines
            line_offset += len(new_sub_lines) - old_count

        return "\n".join(result_lines)

    @classmethod
    def apply_file_patch(cls, workspace_root: str, relative_path: str, diff_text: str) -> str:
        """Apply patch to a file in workspace root atomically."""
        abs_path = safe_path(workspace_root, relative_path)
        original_content = ""
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                original_content = f.read()

        patched_content = cls.apply_patch(original_content, diff_text)
        write_workspace_file(workspace_root, relative_path, patched_content)
        return patched_content


patch_engine = PatchEngine()
