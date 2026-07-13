"""Utility module providing a stub implementation for bug scanning.

The original codebase expects an ``app.tools.scan_for_bugs`` module with an
``async def scan_for_bugs(...)`` function.  Several adapters and the database
initialisation call ``await scan_for_bugs()``.  In the production version this
would invoke an external CLI or a sophisticated analysis tool.  For the purpose
of getting the test suite to run we provide a minimal, async‑compatible stub
that returns an empty bug report.

The stub is deliberately simple but type‑annotated so that callers can rely on
the expected return shape.  It also includes a synchronous wrapper ``scan_for_bugs_sync``
for any legacy callers that might invoke the function without ``await``.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

__all__ = [
    "scan_for_bugs",
    "scan_for_bugs_sync",
    "generate_bug_report_async",
    "generate_bug_report_sync",
]


def _empty_report() -> Dict[str, Any]:
    """Return a canonical empty bug report.

    The structure mirrors what a real implementation would produce – a mapping
    with a ``bugs`` key containing a list of bug descriptors.  Additional keys
    can be added later without breaking existing callers.
    """
    return {"bugs": []}


async def scan_for_bugs(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Asynchronous stub for bug scanning.

    The function accepts arbitrary positional and keyword arguments to remain
    compatible with any future signature.  It simply returns an empty report
    after yielding control back to the event loop, ensuring that ``await``
    behaves as expected.
    """
    # Simulate a tiny async pause – this makes the function behave like a
    # real async call without adding noticeable latency.
    await asyncio.sleep(0)
    return _empty_report()


def scan_for_bugs_sync(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Synchronous wrapper for environments that call the function without ``await``.

    It simply returns the canonical empty report.
    """
    return _empty_report()


def format_bug_report(report_dict: Dict[str, Any]) -> str:
    """Formats a bug report dictionary into a concise text summary."""
    if not isinstance(report_dict, dict):
        return "No bugs found."
    bugs = report_dict.get("bugs", [])
    if not bugs:
        return "No bugs found."
    
    report_lines = []
    for bug in bugs:
        file_path = bug.get("file", "unknown")
        line_no = bug.get("line", "?")
        message = bug.get("message", "").strip()
        report_lines.append(f"{file_path}:{line_no} - {message}")
    
    return "\n".join(report_lines)


async def generate_bug_report_async(*args: Any, **kwargs: Any) -> str:
    """Asynchronously generates a formatted bug report string."""
    res = await scan_for_bugs(*args, **kwargs)
    return format_bug_report(res)


def generate_bug_report_sync(*args: Any, **kwargs: Any) -> str:
    """Synchronously generates a formatted bug report string."""
    res = scan_for_bugs_sync(*args, **kwargs)
    return format_bug_report(res)
