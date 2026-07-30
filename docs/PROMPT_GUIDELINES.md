# AgentOS Prompt Engineering Guidelines

This document details guidelines for compiling prompts, budget limits, and formatting templates.

## 1. Budget Enforcements
*   **Characters vs. Tokens**: Use a 4-to-1 character-to-token ratio (`len(text) // 4`) for estimation.
*   **LRU Paging**: Hot context has higher priority and receives prompt budgets first. Warm and Cold items are cascadingly demoted or evicted.

## 2. Duplicate Filtering
*   Never repeat information. If a code file or diagnostic is printed in the memory context segment, omit it from the repository signature segment.

## 3. Formatting Structures
*   **Claude/Anthropic XML Blocks**: Place content inside explicit blocks:
    ```xml
    <system_prompt>...</system_prompt>
    <context>...</context>
    <task>...</task>
    ```
*   **OpenAI/GPT Markdown & JSON Blocks**: Structure inputs with headers and minified inline JSON lists to conserve context windows.
