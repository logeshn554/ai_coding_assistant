"""
Tool validation, authorization, and execution layer.

This module sits between the agent and the actual tools,
ensuring all tool calls are validated before execution.

Key features:
  - Path validation against allowed_paths (file ownership)
  - Schema validation
  - Permission checking
  - Timeout enforcement
  - Comprehensive error handling
"""

import asyncio
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from .interfaces import (
    ToolCall,
    ToolDefinition,
    ToolResult,
    IToolValidator,
    IToolExecutor,
    ToolCallError,
)


class PathValidator:
    """Validates file paths against allowed paths."""

    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalize a path for comparison."""
        try:
            return os.path.normpath(os.path.abspath(path))
        except Exception:
            return path

    @staticmethod
    def is_within_allowed_paths(
        file_path: str, 
        allowed_paths: List[str],
        workspace_root: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if file_path is within one of the allowed paths.

        Args:
            file_path: The path to check
            allowed_paths: List of allowed base paths (can include wildcards)
            workspace_root: Workspace root for relative path resolution

        Returns:
            (is_allowed, error_message)
        """
        if not allowed_paths:
            # No restriction
            return True, None

        try:
            # Resolve relative paths against workspace root
            if workspace_root and not os.path.isabs(file_path):
                resolved_file = os.path.join(workspace_root, file_path)
            else:
                resolved_file = file_path

            normalized_file = PathValidator.normalize_path(resolved_file)

            for allowed in allowed_paths:
                # Resolve allowed paths
                if workspace_root and not os.path.isabs(allowed):
                    resolved_allowed = os.path.join(workspace_root, allowed)
                else:
                    resolved_allowed = allowed

                # Handle wildcards like "tests/*.py" or "src/**/*.py"
                if "*" in allowed or "?" in allowed or "*" in resolved_allowed:
                    import fnmatch
                    norm_rel = file_path.replace("\\", "/")
                    norm_allowed = allowed.replace("\\", "/")
                    if fnmatch.fnmatch(norm_rel, norm_allowed) or fnmatch.fnmatch(normalized_file.replace("\\", "/"), resolved_allowed.replace("\\", "/")):
                        return True, None
                else:
                    # Direct path check
                    normalized_allowed = PathValidator.normalize_path(resolved_allowed)
                    
                    # Check if file is under allowed directory
                    try:
                        Path(normalized_file).relative_to(normalized_allowed)
                        return True, None
                    except ValueError:
                        # Not under this allowed path
                        pass
                    
                    # Also check if it's exactly the allowed file
                    if normalized_file == normalized_allowed:
                        return True, None

            return False, (
                f"PATH_NOT_ALLOWED: {file_path} not in allowed paths: {allowed_paths}"
            )

        except Exception as e:
            return False, f"PATH_VALIDATION_ERROR: {str(e)}"

    @staticmethod
    def validate_write_safety(
        file_path: str, 
        allowed_paths: List[str],
        workspace_root: Optional[str] = None,
        forbidden_patterns: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive write safety validation.

        Checks:
          - File is within allowed paths
          - File doesn't match forbidden patterns (e.g., .git, secrets)

        Args:
            file_path: File path to validate
            allowed_paths: List of allowed paths
            workspace_root: Workspace root
            forbidden_patterns: Patterns that are always forbidden

        Returns:
            (is_safe, error_message)
        """
        # Default forbidden patterns
        if forbidden_patterns is None:
            forbidden_patterns = [
                r".*\.git.*",
                r".*node_modules.*",
                r".*\.env.*",
                r".*\.ssh.*",
                r".*\/etc\/.*",
                r".*\/sys\/.*",
                r".*secrets.*",
                r".*\.key.*",
                r".*private.*",
            ]

        # Check forbidden patterns first
        normalized_file = PathValidator.normalize_path(file_path)
        for pattern in forbidden_patterns:
            try:
                if re.match(pattern, normalized_file):
                    return False, f"FORBIDDEN_PATH: {file_path} matches forbidden pattern {pattern}"
            except re.error:
                pass

        # Check allowed paths
        is_allowed, error = PathValidator.is_within_allowed_paths(
            file_path, allowed_paths, workspace_root
        )
        
        return is_allowed, error


class ToolValidator(IToolValidator):
    """Validates tool calls before execution."""

    async def validate(
        self, 
        tool_call: ToolCall, 
        tool_def: ToolDefinition, 
        allowed_paths: List[str],
        workspace_root: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive validation of a tool call.

        Checks:
          - Tool exists
          - Schema compliance
          - Argument types
          - File paths within allowed_paths (CRITICAL)
          - Timeout feasibility
          - Permission level

        Args:
            tool_call: The tool call to validate
            tool_def: Tool definition
            allowed_paths: Allowed paths for file operations
            workspace_root: Workspace root for relative path resolution

        Returns:
            (is_valid, error_message)
        """

        # 1. Schema validation
        schema = tool_def.input_schema
        errors = self._validate_schema(tool_call.arguments, schema)
        if errors:
            return False, f"SCHEMA_VALIDATION_ERROR: {errors}"

        # 2. Path validation for file operation tools (CRITICAL)
        is_path_valid = await self._validate_file_paths(
            tool_call, tool_def, allowed_paths, workspace_root
        )
        if not is_path_valid[0]:
            return is_path_valid

        # 3. Timeout validation
        if tool_def.timeout_seconds < 1:
            return False, f"INVALID_TIMEOUT: {tool_def.timeout_seconds}"

        # 4. Permission check
        if tool_def.permission_level == "admin" and not self._is_admin_context():
            return False, f"PERMISSION_DENIED: {tool_def.name} requires admin"

        return True, None

    async def _validate_file_paths(
        self, 
        tool_call: ToolCall, 
        tool_def: ToolDefinition,
        allowed_paths: List[str],
        workspace_root: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate file paths in tool arguments against allowed paths.

        This is the critical check for file ownership.
        """
        file_operation_tools = {
            "write_file": ["path"],
            "create_file": ["path"],
            "edit_file": ["path"],
            "delete_file": ["path"],
            "rename_file": ["old_path", "new_path"],
        }

        # Check if this is a file operation tool
        if tool_def.name not in file_operation_tools:
            return True, None

        # Get field names to check
        field_names = file_operation_tools[tool_def.name]

        # Validate each file path
        for field_name in field_names:
            file_path = tool_call.arguments.get(field_name)
            if file_path:
                # For write operations, use strict validation
                is_write_op = tool_def.name in ["write_file", "create_file", "edit_file"]
                
                if is_write_op:
                    is_safe, error = PathValidator.validate_write_safety(
                        file_path, allowed_paths, workspace_root
                    )
                else:
                    is_safe, error = PathValidator.is_within_allowed_paths(
                        file_path, allowed_paths, workspace_root
                    )

                if not is_safe:
                    return False, error

        return True, None

    def _validate_schema(self, arguments: Dict[str, Any], schema: Dict[str, Any]) -> str:
        """Validate arguments against JSON schema."""
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields
        for req_field in required:
            if req_field not in arguments:
                return f"Missing required field: {req_field}"

        # Type checking on provided fields
        for field_name, field_value in arguments.items():
            if field_name not in properties:
                return f"Unknown field: {field_name}"

            field_schema = properties[field_name]
            expected_type = field_schema.get("type")

            if not self._check_type(field_value, expected_type):
                return f"Field {field_name} has wrong type. Expected {expected_type}, got {type(field_value).__name__}"

        return ""

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_map.get(expected_type)
        if python_type is None:
            return True  # Unknown type, assume OK

        return isinstance(value, python_type)

    def _is_admin_context(self) -> bool:
        """Check if current context is admin (stub for now)."""
        # In real implementation, check user roles, tokens, etc.
        return False


class ToolExecutor(IToolExecutor):
    """Executes validated tool calls."""

    def __init__(self, tools_registry: Dict[str, ToolDefinition], workspace_root: Optional[str] = None):
        self.tools = tools_registry
        self.validator = ToolValidator()
        self.workspace_root = workspace_root

    async def execute(
        self, 
        tool_call: ToolCall, 
        allowed_paths: List[str]
    ) -> ToolResult:
        """
        Execute a tool call with validation and error handling.

        Returns a ToolResult with status and output.
        Never raises - always returns structured result.
        """
        result = ToolResult(
            tool_call_id=tool_call.tool_call_id,
            tool_name=tool_call.tool_name,
            status="unknown",
        )

        # 1. Get tool definition
        if tool_call.tool_name not in self.tools:
            result.status = "error"
            result.error = f"TOOL_NOT_FOUND: {tool_call.tool_name}"
            return result

        tool_def = self.tools[tool_call.tool_name]

        # 2. Validate tool call (INCLUDING PATH VALIDATION)
        is_valid, validation_error = await self.validator.validate(
            tool_call, tool_def, allowed_paths, self.workspace_root
        )
        if not is_valid:
            result.status = "validation_error"
            result.error = validation_error
            return result

        # 3. Execute with timeout
        try:
            result.result = await asyncio.wait_for(
                self._execute_tool(tool_def, tool_call.arguments),
                timeout=tool_def.timeout_seconds,
            )
            result.status = "success"
        except asyncio.TimeoutError:
            result.status = "timeout"
            result.error = f"Tool execution timed out after {tool_def.timeout_seconds}s"
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        return result

    async def _execute_tool(
        self, tool_def: ToolDefinition, arguments: Dict[str, Any]
    ) -> Any:
        """Execute the actual tool function."""
        # Check if executor is async or sync
        if asyncio.iscoroutinefunction(tool_def.executor):
            return await tool_def.executor(**arguments)
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: tool_def.executor(**arguments)
            )
