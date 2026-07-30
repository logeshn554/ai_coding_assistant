import os

def get_positive_int_env(name: str, default: int) -> int:
    """Safely retrieves a positive integer value from environment variables."""
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError:
        return default

    return parsed if parsed > 0 else default

# Character limits are approximate context controls and are not exact token counts.
# Do not assume four characters always equal one token. Character limits are only a safe approximation.
READ_FILE_MAX_CHARS = get_positive_int_env("READ_FILE_MAX_CHARS", 60000)
TOOL_RESULT_MAX_CHARS = get_positive_int_env("TOOL_RESULT_MAX_CHARS", 60000)
CODING_ORIGINAL_MAX_CHARS = get_positive_int_env("CODING_ORIGINAL_MAX_CHARS", 50000)
HISTORY_MAX_CHARS = get_positive_int_env("HISTORY_MAX_CHARS", 400000)
CODE_CHUNK_MAX_CHARS = get_positive_int_env("CODE_CHUNK_MAX_CHARS", 80000)
MAX_CODE_CHUNKS = get_positive_int_env("MAX_CODE_CHUNKS", 3)
CODEBASE_SCAN_MAX_CHARS = get_positive_int_env("CODEBASE_SCAN_MAX_CHARS", 120000)
MEMORY_SUMMARY_MAX_CHARS = get_positive_int_env("MEMORY_SUMMARY_MAX_CHARS", 30000)
MAX_TARGET_FILES_WITH_CONTENT = get_positive_int_env("MAX_TARGET_FILES_WITH_CONTENT", 5)
MAX_SINGLE_PROMPT_CHARS = get_positive_int_env("MAX_SINGLE_PROMPT_CHARS", 350000)
