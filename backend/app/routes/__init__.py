from .auth import router as auth_router
from .workspace import router as workspace_router
from .profiles import router as profiles_router
from .permissions import router as permissions_router
from .settings import router as settings_router
from .files import router as files_router
from .git import router as git_router
from .packages import router as packages_router
from .debug import router as debug_router
from .extensions import router as extensions_router
from .testing import router as testing_router
from .chat import router as chat_router
from .terminal import router as terminal_router
from .workspace_symbols import router as workspace_symbols_router
from .lsp import router as lsp_router
from .sessions import router as sessions_router
from .skills import router as skills_router
from .health import router as health_router
from .completions import router as completions_router
from .memory import router as memory_router

all_routers = [
    auth_router,
    workspace_router,
    profiles_router,
    permissions_router,
    settings_router,
    files_router,
    git_router,
    packages_router,
    debug_router,
    extensions_router,
    testing_router,
    chat_router,
    sessions_router,
    terminal_router,
    workspace_symbols_router,
    lsp_router,
    skills_router,
    health_router,
    completions_router,
    memory_router,
]
