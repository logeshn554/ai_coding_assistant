"""Tests for Phase 2 — Planning Engine."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from app.agent.planning_engine import PlanningEngine
from app.agent.intent_router import IntentType


@pytest.fixture
def engine():
    return PlanningEngine()


class TestPlanningEngine:
    def test_implement_spec_plan(self, engine):
        plan = engine.generate(
            goal="implement GDD.md",
            intent=IntentType.IMPLEMENT_SPEC,
            referenced_files=["GDD.md"],
            spec_file="GDD.md",
            workspace_has_files=True,
        )
        assert len(plan.steps) > 0
        # First step must read the spec
        assert "GDD.md" in plan.steps[0]["task"]
        # Must have a validate step
        step_types = [s["type"] for s in plan.steps]
        assert "validate" in step_types

    def test_bug_fix_plan_with_file_refs(self, engine):
        plan = engine.generate(
            goal="fix the bug in auth.py",
            intent=IntentType.BUG_FIX,
            referenced_files=["auth.py"],
            spec_file=None,
            workspace_has_files=True,
        )
        assert len(plan.steps) > 0
        # First step must read the referenced file
        assert "auth.py" in plan.steps[0]["task"]
        # Must have a test step
        step_types = [s["type"] for s in plan.steps]
        assert "test" in step_types

    def test_bug_fix_plan_no_file_refs(self, engine):
        plan = engine.generate(
            goal="fix the login error",
            intent=IntentType.BUG_FIX,
            referenced_files=[],
            spec_file=None,
            workspace_has_files=True,
        )
        assert len(plan.steps) > 0
        # First step must be a search
        assert plan.steps[0]["type"] == "search"

    def test_new_project_plan(self, engine):
        plan = engine.generate(
            goal="create a React todo app",
            intent=IntentType.NEW_PROJECT,
            referenced_files=[],
            spec_file=None,
            workspace_has_files=False,
        )
        assert len(plan.steps) > 0
        # First step must check workspace
        assert "list" in plan.steps[0]["task"].lower() or "workspace" in plan.steps[0]["task"].lower()

    def test_explain_returns_empty_plan(self, engine):
        plan = engine.generate(
            goal="explain how decorators work",
            intent=IntentType.EXPLAIN,
            referenced_files=[],
            spec_file=None,
            workspace_has_files=True,
        )
        # Explain doesn't need a formal plan
        assert len(plan.steps) == 0

    def test_continue_returns_empty_plan(self, engine):
        plan = engine.generate(
            goal="continue",
            intent=IntentType.CONTINUE,
            referenced_files=[],
            spec_file=None,
            workspace_has_files=True,
        )
        assert len(plan.steps) == 0

    def test_steps_have_required_fields(self, engine):
        plan = engine.generate(
            goal="implement spec.md",
            intent=IntentType.IMPLEMENT_SPEC,
            referenced_files=["spec.md"],
            spec_file="spec.md",
            workspace_has_files=True,
        )
        for step in plan.steps:
            assert "id" in step
            assert "task" in step
            assert "type" in step
            assert "deps" in step
            assert "status" in step

    def test_deps_are_sequential(self, engine):
        plan = engine.generate(
            goal="implement spec.md",
            intent=IntentType.IMPLEMENT_SPEC,
            referenced_files=["spec.md"],
            spec_file="spec.md",
            workspace_has_files=True,
        )
        # Each step (after first) should depend on the previous
        for i, step in enumerate(plan.steps[1:], 1):
            assert len(step["deps"]) > 0, f"Step {step['id']} has no deps"

    def test_plan_to_prompt_block(self, engine):
        plan = engine.generate(
            goal="fix the bug in login.py",
            intent=IntentType.BUG_FIX,
            referenced_files=["login.py"],
            spec_file=None,
            workspace_has_files=True,
        )
        block = plan.to_prompt_block()
        assert "EXECUTION PLAN" in block
        assert "Step 1" in block
