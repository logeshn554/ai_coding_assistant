"""Tests for Phase 4 — Task Memory."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from app.agent.task_memory import TaskMemory, TaskStep, TaskStatus


class TestTaskMemory:
    def test_reset_clears_state(self):
        tm = TaskMemory()
        tm.reset(goal="build a thing", intent="BUG_FIX")
        assert tm.goal == "build a thing"
        assert tm.intent == "BUG_FIX"
        assert tm.steps == []
        assert tm.files_written == []

    def test_add_step(self):
        tm = TaskMemory()
        step = tm.add_step("Read the spec file", step_type="context")
        assert step.id == 1
        assert step.task == "Read the spec file"
        assert step.status == TaskStatus.PENDING

    def test_next_pending_respects_deps(self):
        tm = TaskMemory()
        s1 = tm.add_step("Step 1", deps=[])
        s2 = tm.add_step("Step 2", deps=[1])

        # s1 is next (no deps)
        assert tm.next_pending().id == 1

        # Complete s1 → s2 becomes next
        s1.mark_completed()
        assert tm.next_pending().id == 2

    def test_all_completed(self):
        tm = TaskMemory()
        s1 = tm.add_step("Step 1")
        assert not tm.all_completed()
        s1.mark_completed()
        assert tm.all_completed()

    def test_record_write(self):
        tm = TaskMemory()
        tm.record_write("src/auth.py")
        assert "src/auth.py" in tm.files_written
        # No duplicates
        tm.record_write("src/auth.py")
        assert tm.files_written.count("src/auth.py") == 1

    def test_record_error(self):
        tm = TaskMemory()
        tm.record_error("SyntaxError at line 42")
        assert len(tm.errors) == 1

    def test_set_steps_from_planning_engine(self):
        tm = TaskMemory()
        steps = [
            {"id": 1, "task": "Read spec", "type": "context", "deps": [], "status": "pending"},
            {"id": 2, "task": "Write code", "type": "implement", "deps": [1], "status": "pending"},
        ]
        tm.set_steps(steps)
        assert len(tm.steps) == 2
        assert tm.steps[0].task == "Read spec"
        assert tm.steps[1].deps == [1]

    def test_to_dict_structure(self):
        tm = TaskMemory()
        tm.reset(goal="build something", intent="NEW_PROJECT")
        tm.add_step("Step 1")
        data = tm.to_dict()
        assert "goal" in data
        assert "steps" in data
        assert "files_written" in data
        assert data["goal"] == "build something"

    def test_to_summary_prompt(self):
        tm = TaskMemory()
        tm.reset(goal="implement GDD", intent="IMPLEMENT_SPEC")
        tm.add_step("Read spec")
        summary = tm.to_summary_prompt()
        assert "implement GDD" in summary
        assert "Read spec" in summary

    def test_pending_count(self):
        tm = TaskMemory()
        tm.add_step("Step 1")
        tm.add_step("Step 2")
        assert tm.pending_count() == 2
        tm.steps[0].mark_completed()
        assert tm.pending_count() == 1
