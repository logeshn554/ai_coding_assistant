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
