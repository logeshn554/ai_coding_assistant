"""Live Server Tool – launches a static HTTP server to preview HTML files.

Exposes ``open_with_live_server(session, args)`` and ``find_free_port()``
as the agent-facing functions.
"""
from __future__ import annotations

import asyncio
import os
import socket
import random
from typing import Any, Dict


def find_free_port(start_port: int = 5500) -> int:
    """Find an available free TCP port using randomized selection to mitigate TOCTOU collisions."""
    ports = list(range(start_port, start_port + 1000))
    random.shuffle(ports)
    for port in ports[:50]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


async def open_with_live_server(session: Any, args: Dict[str, Any]) -> str:
    """Launch or reuse a Live Server for an HTML file or static site in the workspace.

    Args:
        session: Active AgentSession providing workspace_root & send_ws_message.
        args:
            path (str, optional): Relative path of the HTML file to serve.
                If omitted, auto-detects ``index.html`` in the workspace.
            port (int, optional): Port to run the server on (default 5500).

    Returns:
        Message containing the Live Server localhost preview URL.
    """
    rel_path = args.get("path") or args.get("file") or args.get("filepath") or ""

    if not rel_path or not rel_path.endswith((".html", ".htm")):
        found_html = None
        for root, _, files in os.walk(session.workspace_root):
            for file in files:
                if file.endswith((".html", ".htm")):
                    rel_p = os.path.relpath(
                        os.path.join(root, file), session.workspace_root
                    ).replace("\\", "/")
                    if file == "index.html":
                        found_html = rel_p
                        break
                    elif not found_html:
                        found_html = rel_p
            if found_html and found_html.endswith("index.html"):
                break
        rel_path = found_html or "index.html"

    from ..processes import global_process_manager

    # Check if Live Server is already running for this workspace
    running_procs = global_process_manager.get_running_processes()
    for p in running_procs:
        if p.cwd == session.workspace_root and (
            "http.server" in p.command or "Live Server" in (p.name or "")
        ):
            port = p.port or 5500
            live_url = f"http://localhost:{port}/{rel_path}".rstrip("/")
            res_msg = (
                f"🚀 **Live Server is already running!**\n\n"
                f"🔗 **Preview URL**: [{live_url}]({live_url})\n\n"
                f"Serving file: `{rel_path}` at `http://localhost:{port}/`"
            )
            await session.send_ws_message({"type": "text_delta", "content": f"\n{res_msg}\n"})
            return res_msg

    # Find an available free port
    requested_port = args.get("port") or 5500
    port = find_free_port(requested_port)
    command = f"python -m http.server {port}"

    proc = await global_process_manager.start_process(
        command, session.workspace_root, name="Live Server (Static HTML)"
    )
    _monitor_task = asyncio.create_task(session.monitor_and_stream_events(proc))
    _tasks = getattr(session, "_monitor_tasks", None)
    if _tasks is not None:
        _tasks.append(_monitor_task)

    live_url = f"http://localhost:{port}/{rel_path}".rstrip("/")
    res_msg = (
        f"🚀 **Live Server Started!**\n\n"
        f"🔗 **Preview URL**: [{live_url}]({live_url})\n\n"
        f"Serving HTML file `{rel_path}` at `http://localhost:{port}/`"
    )

    await session.send_ws_message({"type": "text_delta", "content": f"\n{res_msg}\n"})
    return res_msg
