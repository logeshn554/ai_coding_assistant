"""
Tests for failure classification and stuck detection (Phase 5a-5b).
"""

import pytest

from agent_os.agent.failure_handling import (
    FailureClassifier,
    FailureType,
    RecoveryStrategy,
    StuckDetector,
    FailureFingerprint,
)


class TestFailureClassifier:
    """Test failure classification."""

    def test_rate_limit_classification(self):
        """Test rate limit classification."""
        error = "Error 429: Too many requests - rate limit exceeded"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.RATE_LIMIT

    def test_timeout_classification(self):
        """Test timeout classification."""
        error = "Command timed out after 30 seconds"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.TOOL_TIMEOUT

    def test_permission_classification(self):
        """Test permission error classification."""
        error = "Permission denied: Cannot access /etc/passwd"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.PERMISSION_ERROR

    def test_network_classification(self):
        """Test network error classification."""
        error = "ConnectionError: Unable to connect to API - network unreachable"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.NETWORK_ERROR

    def test_workspace_classification(self):
        """Test workspace error classification."""
        error = "FileNotFoundError: No such file or directory"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.WORKSPACE_ERROR

    def test_test_failure_classification(self):
        """Test test failure classification."""
        error = "FAILED: test_foo.py::test_something"
        failure_type = FailureClassifier.classify(
            error,
            context={"tool_name": "run_tests"}
        )
        assert failure_type == FailureType.TEST_FAILURE

    def test_dependency_classification(self):
        """Test dependency error classification."""
        error = "ModuleNotFoundError: No module named 'numpy'"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.DEPENDENCY_ERROR

    def test_code_error_classification(self):
        """Test code error classification."""
        error = "SyntaxError: invalid syntax at line 42"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.CODE_ERROR

    def test_merge_conflict_classification(self):
        """Test merge conflict classification."""
        error = "Merge conflict in file.py"
        failure_type = FailureClassifier.classify(error)
        assert failure_type == FailureType.MERGE_CONFLICT

    def test_recovery_strategy_for_rate_limit(self):
        """Test recovery strategy for rate limit."""
        strategy = FailureClassifier.get_recovery_strategy(FailureType.RATE_LIMIT)
        assert strategy == RecoveryStrategy.RETRY

    def test_recovery_strategy_for_code_error(self):
        """Test recovery strategy for code error."""
        strategy = FailureClassifier.get_recovery_strategy(FailureType.CODE_ERROR)
        assert strategy == RecoveryStrategy.REPAIR

    def test_recovery_strategy_for_workspace_error(self):
        """Test recovery strategy for workspace error."""
        strategy = FailureClassifier.get_recovery_strategy(FailureType.WORKSPACE_ERROR)
        assert strategy == RecoveryStrategy.RECREATE_WORKSPACE

    def test_recovery_strategy_for_stuck(self):
        """Test recovery strategy for stuck."""
        strategy = FailureClassifier.get_recovery_strategy(FailureType.STUCK)
        assert strategy == RecoveryStrategy.ABORT


class TestFailureFingerprint:
    """Test failure fingerprinting."""

    def test_fingerprint_consistency(self):
        """Test that same failures produce same fingerprint."""
        fp1 = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test failed",
            file_path="/workspace/test.py",
            line_number=42,
            command="pytest",
        )

        fp2 = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test failed",
            file_path="/workspace/test.py",
            line_number=42,
            command="pytest",
        )

        assert fp1.hash() == fp2.hash()
        assert fp1 == fp2

    def test_fingerprint_difference(self):
        """Test that different failures produce different fingerprints."""
        fp1 = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test 1 failed",
            file_path="/workspace/test1.py",
            line_number=42,
            command="pytest",
        )

        fp2 = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test 2 failed",
            file_path="/workspace/test2.py",
            line_number=43,
            command="pytest",
        )

        assert fp1.hash() != fp2.hash()
        assert fp1 != fp2

    def test_create_fingerprint(self):
        """Test creating a fingerprint."""
        fingerprint = FailureClassifier.create_fingerprint(
            FailureType.TEST_FAILURE,
            "Test failed at line 123 in 2024-01-15T10:30:45",
            file_path="/workspace/test.py",
            line_number=123,
            command="pytest"
        )

        assert fingerprint.failure_type == str(FailureType.TEST_FAILURE)
        assert "line n" in fingerprint.normalized_error.lower()
        assert "2024" not in fingerprint.normalized_error


class TestStuckDetector:
    """Test stuck detection."""

    def test_stuck_detection_not_stuck(self):
        """Test that single failure doesn't mark as stuck."""
        detector = StuckDetector(max_repeated_failures=3)

        fingerprint = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test failed",
            file_path=None,
            line_number=None,
            command=None,
        )

        is_stuck = detector.record_failure(fingerprint)
        assert not is_stuck

    def test_stuck_detection_repeated_failures(self):
        """Test that repeated failures mark as stuck."""
        detector = StuckDetector(max_repeated_failures=3)

        fingerprint = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test failed",
            file_path=None,
            line_number=None,
            command=None,
        )

        # Record failure 3 times
        detector.record_failure(fingerprint)
        detector.record_failure(fingerprint)
        is_stuck = detector.record_failure(fingerprint)

        assert is_stuck

    def test_stuck_detection_different_failures(self):
        """Test that different failures don't mark as stuck."""
        detector = StuckDetector(max_repeated_failures=3)

        fp1 = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test 1 failed",
            file_path=None,
            line_number=None,
            command=None,
        )

        fp2 = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test 2 failed",
            file_path=None,
            line_number=None,
            command=None,
        )

        # Record different failures
        detector.record_failure(fp1)
        detector.record_failure(fp2)
        detector.record_failure(fp1)

        # No single failure repeated 3 times yet
        assert not detector.record_failure(fp2)

    def test_stuck_detector_status(self):
        """Test getting detector status."""
        detector = StuckDetector(max_repeated_failures=3)

        fingerprint = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test failed",
            file_path=None,
            line_number=None,
            command=None,
        )

        detector.record_failure(fingerprint)
        detector.record_failure(fingerprint)

        status = detector.get_status()
        assert status["total_unique_failures"] == 1
        assert len(status["repeated_failures"]) > 0

    def test_stuck_detector_reset(self):
        """Test resetting detector."""
        detector = StuckDetector()

        fingerprint = FailureFingerprint(
            failure_type="test_failure",
            normalized_error="test failed",
            file_path=None,
            line_number=None,
            command=None,
        )

        detector.record_failure(fingerprint)
        detector.reset()

        status = detector.get_status()
        assert status["total_unique_failures"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
