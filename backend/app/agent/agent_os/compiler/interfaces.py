from abc import ABC, abstractmethod
from typing import Any


class ICompiler(ABC):
    """Abstract syntax tree and semantic parsing compiler."""
    @abstractmethod
    def parse_ast(self, code: str) -> Any:
        pass

    @abstractmethod
    def analyze_references(self, file_path: str) -> Any:
        pass


class ICodeBuilder(ABC):
    """Code generation and syntactic building engine."""
    @abstractmethod
    def build(self, module_ast: Any) -> str:
        pass


class IPromptCompiler(ABC):
    """Structured Prompt Compiler interface for AgentOS."""
    @abstractmethod
    def compile_prompt(
        self,
        task: str,
        repository_objects: list[dict[str, Any]],
        context: str,
        artifacts: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        system_prompt: str,
        model_name: str = "default"
    ) -> str:
        pass

    @abstractmethod
    def estimate_tokens(self, prompt: str) -> int:
        pass
