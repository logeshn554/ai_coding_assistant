import asyncio
from typing import List
from .files import read_workspace_file, write_workspace_file, list_workspace_dir

async def async_read_workspace_file(workspace_root: str, relative_path: str) -> str:
    """
    Asynchronously reads file contents from the workspace.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        read_workspace_file,
        workspace_root,
        relative_path
    )

async def async_write_workspace_file(workspace_root: str, relative_path: str, content: str) -> None:
    """
    Asynchronously writes file contents to the workspace (triggers backup if enabled).
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        write_workspace_file,
        workspace_root,
        relative_path,
        content
    )

async def async_list_workspace_dir(workspace_root: str, relative_path: str = "") -> List[dict]:
    """
    Asynchronously lists workspace folder contents.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        list_workspace_dir,
        workspace_root,
        relative_path
    )
