from abc import ABC, abstractmethod
from typing import Any, List, Dict

class IRepository(ABC):
    """File access and workspace indexing interface."""
    @abstractmethod
    def read_file(self, path: str) -> str:
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        pass

    @abstractmethod
    def create_file(self, file_path: str, content: str = "") -> bool:
        pass

    @abstractmethod
    def edit_file(self, file_path: str, target: str, replacement: str) -> bool:
        pass

    @abstractmethod
    def list_files(self) -> List[str]:
        pass

    @abstractmethod
    def scan_workspace(self, workspace_root: str) -> None:
        pass

    @abstractmethod
    def find_file(self, pattern: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_function(self, name: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_class(self, name: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_references(self, symbol: str) -> List[Dict[str, Any]]:
        pass

    def store_lsp_diagnostics(self, path: str, diagnostics: List[Dict[str, Any]]) -> None:
        pass

    def get_lsp_diagnostics(self, path: str) -> List[Dict[str, Any]]:
        return []

    def get_symbol_diagnostics(self, symbol_name: str) -> List[Dict[str, Any]]:
        return []

    # camelCase compatibility aliases
    def scanWorkspace(self, workspace_root: str) -> None:
        return self.scan_workspace(workspace_root)

    def findFile(self, pattern: str) -> List[Dict[str, Any]]:
        return self.find_file(pattern)

    def findFunction(self, name: str) -> List[Dict[str, Any]]:
        return self.find_function(name)

    def findClass(self, name: str) -> List[Dict[str, Any]]:
        return self.find_class(name)

    def findReferences(self, symbol: str) -> List[Dict[str, Any]]:
        return self.find_references(symbol)


class ISourceControl(ABC):
    """Source control and git tracking operations."""
    @abstractmethod
    def get_diff(self) -> str:
        pass

    @abstractmethod
    def commit_changes(self, message: str) -> str:
        pass


class IRepositoryKnowledgeGraph(ABC):
    """Repository Knowledge Graph interface querying dependencies, call graphs, and impact maps."""
    @abstractmethod
    def get_dependencies(self, path: str) -> Dict[str, List[str]]:
        pass

    @abstractmethod
    def get_call_graph(self, function_name: str) -> Dict[str, List[Dict[str, Any]]]:
        pass

    @abstractmethod
    def get_impact_analysis(self, symbol_name: str) -> Dict[str, List[str]]:
        pass

    @abstractmethod
    def get_related_symbols(self, symbol_name: str) -> List[str]:
        pass

