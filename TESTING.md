# Testing & QA Guide — Loopix IDE

## Test Suite Overview

Loopix maintains a comprehensive, 100% passing test suite across all architectural phases.

## Test Commands

```bash
# Run full workspace test suite
pytest tests/ -v

# Run specific phase test suites
pytest tests/test_phase4_security.py -v
pytest tests/test_security_fuzzing.py -v
pytest tests/test_phase5_ide_experience.py -v
pytest tests/test_phases_6_to_11.py -v
pytest tests/test_evaluation_benchmark.py -v
pytest tests/test_adversarial_hardening.py -v
pytest tests/test_phases_12_to_19.py -v
```
