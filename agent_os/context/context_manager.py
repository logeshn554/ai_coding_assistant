from typing import Any, Dict, List, Optional
from agent_os.context.virtual_memory import VirtualMemoryContextManager

class WorkspaceContextManager(VirtualMemoryContextManager):
    """Manages workspace files, active symbols, conversation history, and editor/git states."""
    def __init__(self, workspace_root: str = "", token_budget: int = 2000) -> None:
        super().__init__(token_budget)
        self._workspace_root = workspace_root
        self._retrieved_files: Dict[str, str] = {}
        self._conversation_history: List[Dict[str, str]] = []
        self._active_symbols: List[str] = []
        self._current_branch: str = "main"
        self._open_editors: List[str] = []

    @property
    def workspace_root(self) -> str:
        return self._workspace_root

    @workspace_root.setter
    def workspace_root(self, root: str) -> None:
        self._workspace_root = root

    @property
    def retrieved_files(self) -> Dict[str, str]:
        return self._retrieved_files

    def add_retrieved_file(self, path: str, content: str) -> None:
        self._retrieved_files[path] = content
        self.add_to_context(f"file:{path}", content)

    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        return self._conversation_history

    def add_message(self, role: str, content: str) -> None:
        self._conversation_history.append({"role": role, "content": content})
        self.add_to_context(f"history:{len(self._conversation_history)}", f"{role.upper()}: {content}")

    @property
    def active_symbols(self) -> List[str]:
        return self._active_symbols

    def add_active_symbol(self, symbol: str) -> None:
        if symbol not in self._active_symbols:
            self._active_symbols.append(symbol)

    @property
    def current_branch(self) -> str:
        return self._current_branch

    @current_branch.setter
    def current_branch(self, branch: str) -> None:
        self._current_branch = branch

    @property
    def open_editors(self) -> List[str]:
        return self._open_editors

    def add_open_editor(self, path: str) -> None:
        if path not in self._open_editors:
            self._open_editors.append(path)

    def remove_open_editor(self, path: str) -> None:
        if path in self._open_editors:
            self._open_editors.remove(path)

    def clear(self) -> None:
        super().clear()
        self._retrieved_files.clear()
        self._conversation_history.clear()
        self._active_symbols.clear()
        self._open_editors.clear()
