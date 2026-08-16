"""
Test Graph — Maps system files and classes to their corresponding unit/integration test suites.

Enables incremental/targeted testing based on impact analysis of modified code.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("devpilot.brain.test_graph")


class TestGraph:
    """Manages mappings between source components and verification tests."""

    def __init__(self) -> None:
        # Key: source_file_path -> Set of test_file_paths or test_command_args
        self._mappings: dict[str, set[str]] = {}

    def associate_test(self, source_file: str, test_file: str) -> None:
        """Register that test_file verifies source_file."""
        if source_file not in self._mappings:
            self._mappings[source_file] = set()
        self._mappings[source_file].add(test_file)
        logger.debug(f"Associated test '{test_file}' with source file '{source_file}'")

    def get_tests_for_file(self, source_file: str) -> list[str]:
        """Retrieve tests related to a specific source file."""
        return list(self._mappings.get(source_file, set()))

    def scan_project_tests(self, file_list: list[str]) -> None:
        """Attempt to auto-associate source files with test files by name matching."""
        # Simple heuristic: "foo.py" is tested by "test_foo.py" or "foo_test.py"
        test_files = [f for f in file_list if "test_" in f or "_test" in f]
        source_files = [f for f in file_list if f not in test_files]

        for s_file in source_files:
            s_name = s_file.split("/")[-1].split(".")[0]
            for t_file in test_files:
                t_name = t_file.split("/")[-1].split(".")[0]
                if s_name in t_name or t_name in s_name:
                    self.associate_test(s_file, t_file)


# ── Singleton ───────────────────────────────────────────────────────────────

test_graph = TestGraph()
