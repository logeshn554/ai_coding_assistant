# Phase 11: Learning Engine

## Goal
Store successful fixes and patterns in SQLite, implementing Jaccard similarity searches.

## Achievements
*   Implemented `LearningEngine` in `agent_os/learning/engine.py`.
*   Supported 5 database tables (fixes, summaries, patterns, conventions, run benchmarks).
*   Implemented syntactic Jaccard overlap similarity lookups matching token keyword hits.
*   Enforced database containment: conversational raw chat transcripts are strictly ignored.

## Verification
*   `test_learning.py`
