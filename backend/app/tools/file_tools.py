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

from .list_tool import list_directory
from .live_server_tool import find_free_port, open_with_live_server
from .read_tool import read_file
from .write_tool import (
    _build_edit_error_hint,
    _check_missing_packages,
    _extract_bare_specifiers,
    _whitespace_near_match,
    write_or_edit_file,
)

__all__ = [
    "_build_edit_error_hint",
    "_check_missing_packages",
    "_extract_bare_specifiers",
    "_whitespace_near_match",
    "find_free_port",
    "list_directory",
    "open_with_live_server",
    "read_file",
    "write_or_edit_file",
]
