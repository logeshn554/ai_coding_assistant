# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None
project_root = os.path.abspath(SPECPATH)

added_files = [
    (os.path.join(project_root, 'frontend', 'dist'), os.path.join('frontend', 'dist')),
    (os.path.join(project_root, 'assets', 'loopix.ico'), 'assets'),
    (os.path.join(project_root, 'assets', 'loopix.png'), 'assets'),
]

hidden_imports = [
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
]

a = Analysis(
    [os.path.join(project_root, 'backend', 'desktop_run.py')],
    pathex=[project_root, os.path.join(project_root, 'backend')],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Loopix-Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'assets', 'loopix.ico'),
)
