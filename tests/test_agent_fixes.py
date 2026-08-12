import pytest
import os
import tempfile
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.app.agent.agent_runtime.tool_executor import ToolExecutor
from backend.app.agent.security.secret_redactor import SecretRedactor
from backend.app.tools.write_tool import _extract_bare_specifiers, validate_file_content, check_path_casing
from backend.app.agent.agent_runtime.command_generator import TerminalCommandGenerator
from backend.app.tools.terminal_tool import is_server_start_command

@pytest.mark.asyncio
async def test_tool_argument_validation():
    # Test strict argument validation inside ToolExecutor
    executor = ToolExecutor(workspace_root=".")
    
    # Run todo_write without required 'todos' arg
    res = await executor.execute(
        tool_call_id="call_1",
        tool_name="todo_write",
        arguments={}
    )
    
    assert not res.success
    # The error should be a serialized JSON payload
    data = json.loads(res.error)
    assert data["error"] == "Missing required argument: todos"
    assert data["tool"] == "todo_write"
    assert data["retryable"] is True

def test_environment_safety_rules():
    # Verify .env.example and env.example are allowed, but actual secrets are blocked
    assert not SecretRedactor.is_secret_file(".env.example")
    assert not SecretRedactor.is_secret_file("env.example")
    assert SecretRedactor.is_secret_file(".env")
    assert SecretRedactor.is_secret_file(".env.local")
    assert SecretRedactor.is_secret_file(".env.development")
    assert SecretRedactor.is_secret_file(".env.production")
    assert SecretRedactor.is_secret_file(".env.test")

def test_ts_alias_imports():
    # Import parser should exclude `@/` prefix specifiers from bare node packages checklist
    content = """
    import { Button } from "@/components/ui/button";
    import axios from "axios";
    import fs from "node:fs";
    """
    specifiers = _extract_bare_specifiers(content)
    assert "axios" in specifiers
    assert "@" not in specifiers
    assert "@/components/ui/button" not in specifiers
    assert "node:fs" not in specifiers

def test_windows_powershell_command_generation():
    # Verify Unix commands translate correctly to PowerShell
    cmd_tail = "npm run build 2>&1 | tail -30"
    trans_tail = TerminalCommandGenerator.generate_command(cmd_tail, target_shell="powershell")
    assert "Select-Object -Last 30" in trans_tail
    
    cmd_grep = "cat file.txt | grep 'hello'"
    trans_grep = TerminalCommandGenerator.generate_command(cmd_grep, target_shell="powershell")
    assert "Select-String -Pattern \"hello\"" in trans_grep
    
    cmd_rm = "rm -rf folder_name"
    trans_rm = TerminalCommandGenerator.generate_command(cmd_rm, target_shell="powershell")
    assert "Remove-Item -Recurse -Force folder_name" in trans_rm

def test_nextjs_client_component_directive():
    # Next.js App Router Page validation
    page_without_directive = """
    import { useState } from 'react';
    export default function Page() {
        const [state, setState] = useState(0);
        return <div>{state}</div>;
    }
    """
    err = validate_file_content("src/app/dashboard/page.tsx", page_without_directive)
    assert err == "Missing 'use client' directive in Next.js component containing client hooks."

    page_with_directive = """
    'use client';
    import { useState } from 'react';
    export default function Page() {
        const [state, setState] = useState(0);
        return <div>{state}</div>;
    }
    """
    err2 = validate_file_content("src/app/dashboard/page.tsx", page_with_directive)
    assert err2 is None

def test_case_insensitive_path_collision():
    # Verify that case-insensitive path collision check prevents conflicting casings
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory with specific casing
        nav_dir = os.path.join(tmpdir, "src", "components", "navigation")
        os.makedirs(nav_dir, exist_ok=True)
        navbar_path = os.path.join(nav_dir, "Navbar.tsx")
        with open(navbar_path, "w") as f:
            f.write("export const Navbar = () => null;")
            
        # Try to resolve src/components/Navigation/Navbar.tsx (uppercase Navigation)
        resolved_path, collision = check_path_casing(tmpdir, "src/components/Navigation/Navbar.tsx")
        assert resolved_path.replace("\\", "/") == "src/components/navigation/Navbar.tsx"
        assert collision is True

def test_server_command_detection():
    # Verify dev server start command recognition
    assert is_server_start_command("npm run dev")
    assert is_server_start_command("next dev")
    assert is_server_start_command("python backend/launcher.py")
    assert not is_server_start_command("npm run build")
    assert not is_server_start_command("pytest")
