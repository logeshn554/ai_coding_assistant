# Phase 6: Prompt Compiler

## Goal
Optimize compiled model prompts through relevance sorting and duplicate context filtering.

## Achievements
*   Implemented `PromptCompiler` in `agent_os/compiler/prompt_compiler.py`.
*   Supported keyword relevance sorting prioritizing AST symbols matching task directives.
*   Filtered out code signatures already present in the active memory context to reduce token counts.
*   Supported template formats (Claude XML blocks, OpenAI JSON/markdown).

## Verification
*   `test_prompt_compiler.py`
