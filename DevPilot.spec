# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['backend\\desktop_run.py'],
    pathex=['.'],
    binaries=[],
    datas=[('frontend/dist', 'frontend/dist'), ('backend/app', 'backend/app'), ('agent_os', 'agent_os'), ('parallel_agent_system', 'parallel_agent_system')],
    hiddenimports=['uvicorn', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'app.main', 'aiosqlite', 'sqlalchemy.ext.asyncio', 'filelock'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DevPilot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
