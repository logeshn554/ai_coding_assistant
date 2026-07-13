import re
import difflib
import uuid

def generate_hunks(original_content: str, proposed_content: str) -> list:
    """
    Computes unified diff and returns parsed hunks with unique IDs.
    """
    orig_lines = original_content.splitlines()
    prop_lines = proposed_content.splitlines()
    
    diff = list(difflib.unified_diff(
        orig_lines,
        prop_lines,
        fromfile='original',
        tofile='proposed',
        lineterm=''
    ))
    
    hunks = []
    current_hunk = None
    hunk_regex = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
    
    for line in diff:
        if line.startswith('---') or line.startswith('+++'):
            continue
            
        m = hunk_regex.match(line)
        if m:
            if current_hunk:
                hunks.append(current_hunk)
            
            old_start = int(m.group(1))
            old_lines = int(m.group(2)) if m.group(2) else 1
            new_start = int(m.group(3))
            new_lines = int(m.group(4)) if m.group(4) else 1
            
            current_hunk = {
                "id": f"hunk_{uuid.uuid4().hex[:8]}",
                "old_start": old_start,
                "old_lines": old_lines,
                "new_start": new_start,
                "new_lines": new_lines,
                "lines": []
            }
        elif current_hunk is not None:
            current_hunk["lines"].append(line)
            
    if current_hunk:
        hunks.append(current_hunk)
        
    return hunks

def apply_hunks(original_content: str, hunks: list, decisions: dict) -> str:
    """
    Applies only the hunks that have been accepted (decision == True).
    Sorts hunks by old_start descending to process from bottom to top,
    preventing index shift issues.
    """
    lines = original_content.splitlines()
    
    # Sort hunks from bottom to top
    sorted_hunks = sorted(hunks, key=lambda h: h["old_start"], reverse=True)
    
    for hunk in sorted_hunks:
        hunk_id = hunk["id"]
        accept = decisions.get(hunk_id, False)
        
        if accept:
            # Ranges in unified diff are 1-indexed, so convert to 0-indexed
            old_idx = hunk["old_start"] - 1
            old_len = hunk["old_lines"]
            
            # Reconstruct the new lines from hunk lines:
            # Keep lines starting with '+' (remove the '+') and lines starting with ' ' (remove the ' ')
            new_lines = []
            for hl in hunk["lines"]:
                if hl.startswith('+'):
                    new_lines.append(hl[1:])
                elif hl.startswith(' '):
                    new_lines.append(hl[1:])
            # Replace old range with new lines
            lines[old_idx : old_idx + old_len] = new_lines
            
    return "\n".join(lines)

def generate_bug_report() -> str:
    """
    Scans the entire workspace for bugs using the `scan_for_bugs` tool
    and returns a concise bug report.
    """
    try:
        from .tools.scan_for_bugs import generate_bug_report_sync
        return generate_bug_report_sync()
    except Exception as e:
        return f"Bug scan failed: {e}"