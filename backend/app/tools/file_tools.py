"""Backward-compatible re-exports from the split file tool modules.

All functions previously defined here are now in dedicated modules:
  - read_tool.py        -> read_file
  - write_tool.py       -> write_or_edit_file (+ helpers)
  - list_tool.py        -> list_directory
  - live_server_tool.py -> open_with_live_server, find_free_port

This shim re-exports every public symbol so existing imports
(e.g. ``from .file_tools import write_or_edit_file``) continue to work.
"""
from __future__ import annotations

from .read_tool import read_file
from .list_tool import list_directory
from .write_tool import (
    write_or_edit_file,
    _build_edit_error_hint,
    _whitespace_near_match,
    _check_missing_packages,
    _extract_bare_specifiers,
)
from .live_server_tool import open_with_live_server, find_free_port

__all__ = [
    "read_file",
    "list_directory",
    "write_or_edit_file",
    "open_with_live_server",
    "find_free_port",
    "_build_edit_error_hint",
    "_whitespace_near_match",
    "_check_missing_packages",
    "_extract_bare_specifiers",
]
