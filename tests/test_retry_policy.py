"""Unit tests for RetryPolicy."""

import pytest
import tempfile
import os

from backend.app.worker.retry_policy import RetryPolicy, is_retryable


def test_retry_policy_default_classification():
    policy = RetryPolicy()

    # Retryable exceptions
    assert policy.is_retryable(TimeoutError("Read timed out"), attempt=1) is True
    assert policy.is_retryable(ConnectionError("Connection refused"), attempt=1) is True
    assert policy.is_retryable("RateLimitError: 429 Too Many Requests", attempt=1) is True
    assert policy.is_retryable("503 Service Unavailable", attempt=1) is True

    # Non-retryable exceptions
    assert policy.is_retryable(ValueError("Invalid argument"), attempt=1) is False
    assert policy.is_retryable(KeyError("missing_key"), attempt=1) is False
    assert policy.is_retryable(FileNotFoundError("no such file"), attempt=1) is False
    assert policy.is_retryable(RuntimeError("Active model profile missing API key"), attempt=1) is False


def test_retry_policy_max_attempts_exceeded():
    policy = RetryPolicy()
    # At attempt 1 and 2, TimeoutError is retryable
    assert policy.is_retryable(TimeoutError(), attempt=1) is True
    assert policy.is_retryable(TimeoutError(), attempt=2) is True
    # At attempt 3 (max_attempts = 3), it is NOT retryable
    assert policy.is_retryable(TimeoutError(), attempt=3) is False
    assert policy.is_retryable(TimeoutError(), attempt=4) is False


def test_retry_policy_backoff_calculation():
    policy = RetryPolicy()
    d1 = policy.get_backoff_delay(attempt=1)
    d2 = policy.get_backoff_delay(attempt=2)
    d3 = policy.get_backoff_delay(attempt=3)

    assert d1 == 2.0
    assert d2 == 4.0
    assert d3 == 8.0


def test_custom_yaml_config():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tf:
        tf.write("""
max_attempts: 5
backoff_base_seconds: 1.0
backoff_max_seconds: 10.0
retryable_error_types:
  - CustomTransientError
non_retryable_error_types:
  - CustomFatalError
""")
        temp_config = tf.name

    try:
        custom_policy = RetryPolicy(config_path=temp_config)
        assert custom_policy.max_attempts == 5
        assert custom_policy.backoff_base_seconds == 1.0
        assert custom_policy.is_retryable("CustomTransientError", attempt=1) is True
        assert custom_policy.is_retryable("CustomFatalError", attempt=1) is False
        assert custom_policy.is_retryable("CustomTransientError", attempt=4) is True
        assert custom_policy.is_retryable("CustomTransientError", attempt=5) is False
    finally:
        if os.path.exists(temp_config):
            os.remove(temp_config)


def test_module_level_is_retryable():
    assert is_retryable(TimeoutError(), attempt=1) is True
    assert is_retryable(ValueError(), attempt=1) is False
