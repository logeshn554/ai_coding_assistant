"""Tests for Phase 5 — Intent Router."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from app.agent.intent_router import IntentRouter, IntentType


@pytest.fixture
def router():
    return IntentRouter()


class TestIntentRouter:
    def test_continue_intent(self, router):
        result = router.classify("continue")
        assert result.intent == IntentType.CONTINUE
        assert result.confidence >= 0.9

    def test_continue_resume(self, router):
        result = router.classify("resume the previous task")
        assert result.intent == IntentType.CONTINUE

    def test_search_intent(self, router):
        result = router.classify("find where the auth function is defined")
        assert result.intent == IntentType.SEARCH

    def test_explain_intent(self, router):
        result = router.classify("what is a decorator in Python?")
        assert result.intent == IntentType.EXPLAIN

    def test_review_intent(self, router):
        result = router.classify("review the auth.py file for security issues")
        assert result.intent == IntentType.REVIEW

    def test_bug_fix_intent(self, router):
        result = router.classify("fix the TypeError in auth.py")
        assert result.intent == IntentType.BUG_FIX

    def test_bug_fix_traceback(self, router):
        result = router.classify("fix the AttributeError: 'NoneType' object has no attribute 'user'")
        assert result.intent == IntentType.BUG_FIX

    def test_implement_spec(self, router):
        result = router.classify("implement BattleRoyale_GDD.md")
        assert result.intent == IntentType.IMPLEMENT_SPEC
        assert result.spec_file is not None
        assert "GDD.md" in result.spec_file

    def test_implement_spec_based_on(self, router):
        result = router.classify("build the app based on requirements.md")
        assert result.intent == IntentType.IMPLEMENT_SPEC
        assert result.needs_context is True
        assert result.needs_plan is True

    def test_new_project_intent(self, router):
        result = router.classify("create a new React app from scratch")
        assert result.intent == IntentType.NEW_PROJECT

    def test_refactor_intent(self, router):
        result = router.classify("refactor the authentication module")
        assert result.intent == IntentType.REFACTOR

    def test_general_fallback(self, router):
        result = router.classify("add a button to the header")
        # Could be GENERAL or AGENT-level — just ensure it's not None
        assert result.intent is not None
        assert isinstance(result.intent, IntentType)

    def test_file_references_extracted(self, router):
        result = router.classify("fix the bug in auth.py and user_service.py")
        assert any("auth.py" in f for f in result.referenced_files)

    def test_symbol_references_extracted(self, router):
        result = router.classify("fix the UserAuthenticator class")
        assert any("UserAuthenticator" in s for s in result.referenced_symbols)

    def test_needs_context_for_implement_spec(self, router):
        result = router.classify("implement spec.md")
        assert result.needs_context is True
        assert result.needs_plan is True

    def test_no_context_needed_for_continue(self, router):
        result = router.classify("continue")
        assert result.needs_context is False
        assert result.needs_plan is False
