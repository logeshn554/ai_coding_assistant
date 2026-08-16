import os
import re
import json

from .context_config import TOOL_RESULT_MAX_CHARS

def truncate_text(
    text: str,
    max_chars: int,
    *,
    label: str = "content",
    preserve_tail_chars: int = 0,
) -> str:
    """Truncates text to a maximum limit, ensuring clean cuts at newlines and optional tail preservation."""
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    n = len(text)
    if n <= max_chars:
        return text

    if preserve_tail_chars < 0:
        preserve_tail_chars = 0

    if preserve_tail_chars >= max_chars:
        preserve_tail_chars = max_chars // 2

    head_limit = max_chars - preserve_tail_chars

    # Try to find a nearby newline to cut cleanly
    # We look for a newline in the last 200 characters of the head slice
    head_text = text[:head_limit]
    if head_limit > 200:
        nl_idx = head_text.rfind('\n', head_limit - 200, head_limit)
        if nl_idx != -1:
            head_text = head_text[:nl_idx + 1]
            head_limit = len(head_text)

    retained_chars = len(head_text)
    tail_text = ""
    if preserve_tail_chars > 0:
        # Get tail
        tail_start = n - preserve_tail_chars
        tail_text = text[tail_start:]
        # Try to align tail start with a newline if possible
        if len(tail_text) > 200:
            nl_idx = tail_text.find('\n', 0, 200)
            if nl_idx != -1:
                tail_text = tail_text[nl_idx + 1:]
        retained_chars += len(tail_text)

    omitted_chars = n - retained_chars

    notice = f"\n\n[{label} truncated: original={n} chars, retained={retained_chars} chars, omitted={omitted_chars} chars]\n\n"

    if tail_text:
        return f"{head_text.rstrip()}{notice}{tail_text.lstrip()}"
    else:
        return f"{head_text.rstrip()}{notice}"

def estimate_text_size(value: object) -> int:
    """Safely estimates the character size of strings, dictionaries, lists, and tuples."""
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (int, float, bool)):
        return len(str(value))
    try:
        return len(json.dumps(value, separators=(',', ':'), default=str))
    except Exception:
        return len(str(value))

def compact_json(value: object, max_chars: int, label: str) -> str:
    """Serializes an object into compact JSON and applies truncation."""
    try:
        serialized = json.dumps(value, separators=(',', ':'), default=str)
    except Exception as e:
        serialized = f"{{\"error\": \"Failed to serialize: {str(e)}\"}}"
    return truncate_text(serialized, max_chars, label=label)

def is_base64_data(text: str) -> bool:
    """Checks if a string is a base64 encoded data URI or raw base64 string."""
    if not isinstance(text, str):
        return False
    if text.startswith("data:") and ";base64," in text:
        return True
    if len(text) > 1000 and " " not in text and "\n" not in text:
        clean_text = text.strip()
        if len(clean_text) % 4 == 0:
            if re.match(r'^[A-Za-z0-9+/]+={0,2}$', clean_text):
                return True
    return False

def prepare_tool_result_for_history(
    result: object,
    *,
    tool_name: str,
    max_chars: int | None = None,
) -> str:
    """Converts a tool result into a truncated, clean text format for history."""
    limit = max_chars or TOOL_RESULT_MAX_CHARS
    
    if result is None:
        return ""
        
    if isinstance(result, str):
        text = result
    elif isinstance(result, (dict, list)):
        text = json.dumps(result, separators=(',', ':'), default=str)
    else:
        text = str(result)
        
    if is_base64_data(text):
        return f"[Tool result '{tool_name}' omitted: detected binary/base64 payload of size {len(text)} chars]"
        
    if len(text) <= limit:
        return text
        
    # Preserve beginning and a small tail for logs/verbose output
    preserve_tail = min(limit // 5, 10000)
    return truncate_text(text, limit, label=f"tool result '{tool_name}'", preserve_tail_chars=preserve_tail)

def build_memory_summary(memory: dict, max_chars: int | None = None, indent: int | None = None) -> str:
    """Creates a size-bounded JSON serialization of memory, excluding raw file contents."""
    from .context_config import MEMORY_SUMMARY_MAX_CHARS
    limit = max_chars or MEMORY_SUMMARY_MAX_CHARS

    if not memory or not isinstance(memory, dict):
        return "{}"

    exclude_keys = {
        "file_contents",
        "file_contents_dict",
        "original",
        "raw_content",
        "full_text",
        "tool_payload",
        "large logs",
        "collaboration_log"
    }

    cleaned_memory = {}
    omissions_occurred = False

    for k, v in memory.items():
        if k in exclude_keys:
            omissions_occurred = True
            continue

        if isinstance(v, dict):
            cleaned_sub = {}
            for sub_k, sub_v in v.items():
                if sub_k in exclude_keys or estimate_text_size(sub_v) > 10000:
                    omissions_occurred = True
                    cleaned_sub[sub_k] = f"[omitted key '{sub_k}' due to size/content constraints]"
                else:
                    cleaned_sub[sub_k] = sub_v
            cleaned_memory[k] = cleaned_sub
        elif isinstance(v, str) and len(v) > 5000:
            omissions_occurred = True
            cleaned_memory[k] = truncate_text(v, 2000, label=f"memory key '{k}'")
        else:
            cleaned_memory[k] = v

    try:
        if indent is not None:
            serialized = json.dumps(cleaned_memory, indent=indent, default=str)
        else:
            serialized = json.dumps(cleaned_memory, separators=(',', ':'), default=str)
    except Exception as e:
        serialized = f"{{\"error\":\"Failed to serialize memory: {str(e)}\"}}"

    if omissions_occurred:
        serialized = f"{serialized[:-1]},\"_omissions\":true}}"

    return truncate_text(serialized, limit, label="memory summary")

def build_relevant_file_context(
    *,
    path: str,
    content: str,
    task_description: str,
    max_chars: int,
) -> str:
    """Extracts line-numbered targeted excerpts of the file matching identifiers from the task description."""
    if not content:
        return f"FILE: {path}\nContent is empty."

    # Extract alphanumeric words of length >= 3 from the task description as potential identifiers
    identifiers = set(re.findall(r"\b[A-Za-z0-9_]{3,}\b", task_description))
    
    common_stops = {
        "the", "and", "for", "class", "def", "function", "import", "from",
        "file", "code", "change", "create", "modify", "write", "read", "update",
        "implement", "general", "purpose", "software", "engineer", "senior",
        "task", "test", "helper", "relevance", "priority", "aware", "context"
    }
    identifiers = {i for i in identifiers if i.lower() not in common_stops}

    lines = content.splitlines()
    total_lines = len(lines)
    
    matching_line_indices = []
    for idx, line in enumerate(lines):
        line_words = set(re.findall(r"\b[A-Za-z0-9_]{3,}\b", line))
        if line_words.intersection(identifiers):
            matching_line_indices.append(idx)

    # Fallback head-and-tail view if no matches found
    if not matching_line_indices:
        half_limit = max_chars // 2
        head_lines = []
        tail_lines = []
        
        current_len = 0
        for idx in range(total_lines):
            line_str = f"{idx + 1}: {lines[idx]}\n"
            if current_len + len(line_str) > half_limit:
                break
            head_lines.append(line_str)
            current_len += len(line_str)
            
        current_len = 0
        for idx in range(total_lines - 1, -1, -1):
            if idx < len(head_lines):
                break
            line_str = f"{idx + 1}: {lines[idx]}\n"
            if current_len + len(line_str) > half_limit:
                break
            tail_lines.insert(0, line_str)
            current_len += len(line_str)
            
        head_text = "".join(head_lines)
        tail_text = "".join(tail_lines)
        
        omitted = total_lines - len(head_lines) - len(tail_lines)
        omitted_note = f"\n... [Omitted {omitted} lines of code] ...\n\n" if omitted > 0 else ""
        
        return (
            f"FILE: {path}\n"
            f"CONTEXT TYPE: targeted excerpts (fallback head-and-tail)\n"
            f"OMITTED SECTIONS: {'yes' if omitted > 0 else 'no'}\n\n"
            f"{head_text}"
            f"{omitted_note}"
            f"{tail_text}"
        )

    WINDOW_SIZE = 5
    windows = []
    for m_idx in matching_line_indices:
        start = max(0, m_idx - WINDOW_SIZE)
        end = min(total_lines - 1, m_idx + WINDOW_SIZE)
        windows.append((start, end))

    merged_windows = []
    if windows:
        windows.sort(key=lambda x: x[0])
        current_start, current_end = windows[0]
        for start, end in windows[1:]:
            if start <= current_end + 1:
                current_end = max(current_end, end)
            else:
                merged_windows.append((current_start, current_end))
                current_start, current_end = start, end
        merged_windows.append((current_start, current_end))

    output_parts = []
    current_char_count = 0
    omitted_any = False
    last_end = -1

    for start, end in merged_windows:
        if last_end != -1 and start > last_end + 1:
            sep = f"\n... [Omitted {start - last_end - 1} lines] ...\n\n"
            output_parts.append(sep)
            current_char_count += len(sep)
            omitted_any = True

        window_lines = []
        for idx in range(start, end + 1):
            line_str = f"{idx + 1}: {lines[idx]}\n"
            window_lines.append(line_str)
            
        window_text = "".join(window_lines)
        if current_char_count + len(window_text) > max_chars - 100:
            omitted_any = True
            output_parts.append(f"\n... [Truncated remaining excerpts due to size limits] ...\n")
            break
            
        output_parts.append(window_text)
        current_char_count += len(window_text)
        last_end = end

    if last_end != -1 and last_end < total_lines - 1:
        sep = f"\n... [Omitted {total_lines - last_end - 1} lines] ...\n"
        output_parts.append(sep)
        omitted_any = True

    excerpts_text = "".join(output_parts)
    
    return (
        f"FILE: {path}\n"
        f"CONTEXT TYPE: targeted excerpts\n"
        f"OMITTED SECTIONS: {'yes' if omitted_any else 'no'}\n\n"
        f"{excerpts_text}"
    )

def deduplicate_blocks(blocks: list[dict]) -> list[dict]:
    """Identifies and deduplicates substantial duplicate text blocks across context components."""
    import hashlib
    seen_hashes = {}
    deduped = []
    
    for block in blocks:
        role = block.get("role", "")
        content = block.get("content", "")
        source = block.get("source", "history")
        
        if not isinstance(content, str) or len(content) < 150:
            deduped.append(block)
            continue
            
        norm_content = content.replace("\r\n", "\n").strip()
        h = hashlib.sha256(norm_content.encode("utf-8")).hexdigest()
        
        if h in seen_hashes:
            prev_source = seen_hashes[h]
            ref_msg = f"[duplicate content omitted; already included from {prev_source}]"
            new_block = dict(block)
            new_block["content"] = ref_msg
            deduped.append(new_block)
        else:
            seen_hashes[h] = source
            deduped.append(block)
            
    return deduped

class ContextBudgetError(ValueError):
    """Custom exception raised when fixed context alone exceeds prompt budget limits."""
    pass

def assemble_prompt_context(
    *,
    system_text: str,
    task_text: str,
    history: list[dict],
    file_contexts: list[dict],
    memory_summary: str,
    tool_context: list[dict],
    max_chars: int = 350000,
) -> dict:
    """Assembles the final size-bounded LLM prompt context using dynamic segment budgeting and deduplication."""
    safety_margin = int(max_chars * 0.05)
    usable_budget = max_chars - safety_margin

    fixed_chars = len(system_text or "") + len(task_text or "")
    if fixed_chars >= usable_budget:
        raise ContextBudgetError("Fixed system instructions and task description alone exceed the context budget.")

    # Deduplicate blocks
    blocks = []
    for i, h in enumerate(history or []):
        blocks.append({"role": h.get("role"), "content": h.get("content", ""), "source": f"history_{i}", "original": h})
    for i, t in enumerate(tool_context or []):
        blocks.append({"role": t.get("role"), "content": t.get("content", ""), "source": f"tool_{i}", "original": t})
    for i, f in enumerate(file_contexts or []):
        blocks.append({"role": "file", "content": f.get("content", ""), "source": f"file_{f.get('path')}", "original": f})

    deduped_blocks = deduplicate_blocks(blocks)

    deduped_history = []
    deduped_tools = []
    deduped_files = []

    for b in deduped_blocks:
        src = b["source"]
        orig = b["original"]
        block_copy = dict(orig)
        block_copy["content"] = b["content"]
        
        if src.startswith("history_"):
            deduped_history.append(block_copy)
        elif src.startswith("tool_"):
            deduped_tools.append(block_copy)
        elif src.startswith("file_"):
            deduped_files.append(block_copy)

    history_size = estimate_text_size(deduped_history)
    code_size = estimate_text_size(deduped_files)
    tool_size = estimate_text_size(deduped_tools)
    memory_size = len(memory_summary or "")

    target_history = int(max_chars * 0.30)
    target_code = int(max_chars * 0.40)
    target_tools = int(max_chars * 0.15)
    target_memory = int(max_chars * 0.10)

    leftovers = 0
    allocations = {}
    
    if memory_size <= target_memory:
        allocations["memory"] = memory_size
        leftovers += (target_memory - memory_size)
    else:
        allocations["memory"] = target_memory

    if tool_size <= target_tools:
        allocations["tool"] = tool_size
        leftovers += (target_tools - tool_size)
    else:
        allocations["tool"] = target_tools

    if code_size <= target_code:
        allocations["code"] = code_size
        leftovers += (target_code - code_size)
    else:
        allocations["code"] = target_code

    if history_size <= target_history:
        allocations["history"] = history_size
        leftovers += (target_history - history_size)
    else:
        allocations["history"] = target_history

    exceeding = {}
    if memory_size > target_memory:
        exceeding["memory"] = memory_size - target_memory
    if tool_size > target_tools:
        exceeding["tool"] = tool_size - target_tools
    if code_size > target_code:
        exceeding["code"] = code_size - target_code
    if history_size > target_history:
        exceeding["history"] = history_size - target_history

    if exceeding and leftovers > 0:
        total_excess = sum(exceeding.values())
        for sec, excess in exceeding.items():
            share = int(leftovers * (excess / total_excess))
            allocations[sec] += share

    final_history = deduped_history
    history_truncated = False
    if history_size > allocations.get("history", target_history):
        history_truncated = True
        budget = allocations.get("history", target_history)
        history_text = json.dumps(deduped_history, default=str)
        truncated_history_text = truncate_text(history_text, budget, label="history context")
        try:
            final_history = json.loads(truncated_history_text)
        except Exception:
            final_history = [{"role": "system", "content": truncated_history_text}]

    final_files = []
    files_truncated = False
    for f in deduped_files:
        path = f.get("path", "")
        content = f.get("content", "")
        f_size = len(content)
        file_budget = allocations.get("code", target_code) // max(len(deduped_files), 1)
        if f_size > file_budget:
            files_truncated = True
            truncated_content = truncate_text(content, file_budget, label=f"file {path}")
            final_files.append({"path": path, "content": truncated_content})
        else:
            final_files.append(f)

    final_tools = deduped_tools
    tools_truncated = False
    if tool_size > allocations.get("tool", target_tools):
        tools_truncated = True
        tool_text = json.dumps(deduped_tools, default=str)
        truncated_tool_text = truncate_text(tool_text, allocations.get("tool", target_tools), label="tool context")
        try:
            final_tools = json.loads(truncated_tool_text)
        except Exception:
            final_tools = [{"role": "tool", "content": truncated_tool_text}]

    final_memory = memory_summary
    memory_truncated = False
    if memory_size > allocations.get("memory", target_memory):
        memory_truncated = True
        final_memory = truncate_text(memory_summary, allocations.get("memory", target_memory), label="memory context")

    prompt_parts = []
    prompt_parts.append(system_text)
    prompt_parts.append(f"\nTask description:\n{task_text}\n")
    if final_memory:
        prompt_parts.append(f"\nShared Memory:\n{final_memory}\n")
    if final_history:
        prompt_parts.append(f"\nConversation History:\n{json.dumps(final_history, indent=2, default=str)}\n")
    if final_files:
        prompt_parts.append("\nCodebase File Contexts:\n")
        for f in final_files:
            prompt_parts.append(f"FILE: {f.get('path')}\n{f.get('content')}\n---\n")
    if final_tools:
        prompt_parts.append(f"\nTool execution history:\n{json.dumps(final_tools, indent=2, default=str)}\n")

    final_prompt = "".join(prompt_parts)
    if len(final_prompt) > max_chars:
        final_prompt = final_prompt[:max_chars]

    truncated_sections = []
    if history_truncated:
        truncated_sections.append("history")
    if files_truncated:
        truncated_sections.append("file_contexts")
    if tools_truncated:
        truncated_sections.append("tool_context")
    if memory_truncated:
        truncated_sections.append("memory")

    return {
        "prompt": final_prompt,
        "stats": {
            "total_chars": len(final_prompt),
            "history_chars": estimate_text_size(final_history),
            "file_context_chars": estimate_text_size(final_files),
            "tool_chars": estimate_text_size(final_tools),
            "memory_chars": len(final_memory),
            "truncated_sections": truncated_sections
        }
    }
