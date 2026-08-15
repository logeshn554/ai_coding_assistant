# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import winpty

block_cipher = None
project_root = os.path.abspath(SPECPATH)

winpty_dir = os.path.dirname(winpty.__file__)

added_files = [
    (os.path.join(project_root, 'frontend', 'dist'), os.path.join('frontend', 'dist')),
    (os.path.join(project_root, 'assets', 'devpilot.ico'), 'assets'),
    (os.path.join(project_root, 'assets', 'devpilot.png'), 'assets'),
    (winpty_dir, 'winpty'),
]

hidden_imports = [
    'winpty',
    'winpty.ptyprocess',
    'winpty.enums',
    'uvicorn',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'aiosqlite',
    'sqlalchemy.dialects.sqlite.aiosqlite',
    'backend.app.main',
    'backend.app.db',
    'backend.app.state',
    'backend.app.routes',
    'backend.app.agent',
    'backend.app.infrastructure',
    'websockets',
    'websockets.legacy',
    'websockets.legacy.server',
    'webview',
    'webview.platforms.edgechromium',
    'clr_loader',
    'pythonnet',
    'agent_os',
    'agent_os.agent_os',
    'agent_os.infrastructure',
    'agent_os.infrastructure.observability',
    'agent_os.infrastructure.metrics',
    'agent_os.infrastructure.distributed_tracing',
    'agent_os.kernel',
    'agent_os.kernel.health_monitor',
    'agent_os.kernel.kernel',
    'agent_os.providers',
    'agent_os.providers.base',
    'agent_os.providers.common_adapter',
    'agent_os.providers.interfaces',
    'agent_os.providers.model_router',
    'agent_os.agent',
    'agent_os.agent.workspace',
    'agent_runtime',
    'agent_runtime.llm',
    'agent_runtime.llm.openai_provider',
    'autonomous',
    'parallel_agent_system',
]

a = Analysis(
    [os.path.join(project_root, 'backend', 'desktop_run.py')],
    pathex=[
        project_root, 
        os.path.join(project_root, 'backend'),
        os.path.join(project_root, 'backend', 'app', 'agent')
    ],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DevPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed desktop application (no cmd prompt window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'assets', 'devpilot.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DevPilot',
)
