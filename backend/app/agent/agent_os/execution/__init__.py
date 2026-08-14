from agent_os.execution.interfaces import ISandbox, IExecutionEngine, ITransaction, ITransactionalExecutionEngine, IFileLockManager
from agent_os.execution.engine import TransactionalExecutionEngine
from agent_os.execution.lock_manager import FileLockManager
from agent_os.execution.sandbox import DockerSandbox, create_sandbox
# NOTE: LocalSandbox has been removed — it provided no real security boundary
# (ran subprocess.run(shell=True) on the host OS). Use DockerSandbox instead.

__all__ = [
    "ISandbox",
    "IExecutionEngine",
    "ITransaction",
    "ITransactionalExecutionEngine",
    "TransactionalExecutionEngine",
    "IFileLockManager",
    "FileLockManager",
    "DockerSandbox",
    "create_sandbox"
]
