/**
 * main.js — Electron main process for DevPilot (VS Code Architecture).
 *
 * Responsibilities:
 *  1. Open a native desktop window immediately (NO external web browser).
 *  2. Display a built-in startup splash screen while initializing.
 *  3. Automatically spawn and manage the background Python AI backend.
 *  4. Load the full DevPilot workbench directly in the desktop window.
 *  5. Handle native OS dialogs and clean process termination.
 */

const { app, BrowserWindow, ipcMain, dialog, Menu, session } = require('electron');
const path = require('path');
const http = require('http');
const { spawn, exec } = require('child_process');
const fs = require('fs');

// Configuration
const DEVPILOT_PORT = process.env.PORT || 8000;
const DEVPILOT_URL = `http://127.0.0.1:${DEVPILOT_PORT}`;
const BACKEND_POLL_INTERVAL = 300;
const BACKEND_TIMEOUT = 35_000;

let mainWindow = null;
let backendProcess = null;
const projectRoot = path.resolve(__dirname, '..');

// ─── Native Application Menu ─────────────────────────────────────────────────

function setApplicationMenu() {
  const isDev = process.env.NODE_ENV === 'development' || process.env.DEVPILOT_DEV === '1';

  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Open Folder…',
          accelerator: 'CmdOrCtrl+O',
          click: () => {
            if (mainWindow) mainWindow.webContents.send('menu:openFolder');
          },
        },
        { type: 'separator' },
        { role: 'quit', label: 'Quit DevPilot' },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'togglefullscreen' },
        ...(isDev ? [{ type: 'separator' }, { role: 'toggleDevTools' }] : []),
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'DevPilot Documentation',
          click: async () => {
            const { shell } = require('electron');
            await shell.openExternal('https://github.com/devpilot-ai/devpilot');
          },
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ─── Backend Process Management ──────────────────────────────────────────────

function findPythonExecutable() {
  const venvWin = path.join(projectRoot, 'venv', 'Scripts', 'python.exe');
  const venvUnix = path.join(projectRoot, 'venv', 'bin', 'python');

  if (process.platform === 'win32' && fs.existsSync(venvWin)) {
    return venvWin;
  }
  if (fs.existsSync(venvUnix)) {
    return venvUnix;
  }
  return 'python';
}

function startBackendServer() {
  const pythonPath = findPythonExecutable();
  console.log(`[DevPilot Electron] Starting background AI service: ${pythonPath}`);

  const args = [
    '-m',
    'uvicorn',
    'backend.app.main:app',
    '--host',
    '127.0.0.1',
    '--port',
    String(DEVPILOT_PORT),
    '--log-level',
    'warning'
  ];

  backendProcess = spawn(pythonPath, args, {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PYTHONPATH: `${projectRoot};${path.join(projectRoot, 'backend')}`,
    },
    stdio: ['ignore', 'pipe', 'pipe']
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.warn(`[Backend] ${data.toString().trim()}`);
  });

  backendProcess.on('exit', (code, signal) => {
    console.log(`[DevPilot Electron] Backend exited (code: ${code}, signal: ${signal})`);
    backendProcess = null;
  });
}

function killBackendServer() {
  if (!backendProcess || !backendProcess.pid) return;

  const pid = backendProcess.pid;
  console.log(`[DevPilot Electron] Stopping background backend (PID: ${pid})...`);

  if (process.platform === 'win32') {
    exec(`taskkill /pid ${pid} /T /F`, () => {});
  } else {
    try {
      backendProcess.kill('SIGTERM');
    } catch (_) {}
  }
  backendProcess = null;
}

// ─── Backend Ready Check ─────────────────────────────────────────────────────

async function waitForBackend(timeout = BACKEND_TIMEOUT) {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(`${DEVPILOT_URL}/api/health`, (res) => {
          res.destroy();
          if (res.statusCode === 200) {
            resolve();
          } else {
            reject(new Error(`Status ${res.statusCode}`));
          }
        });
        req.on('error', reject);
        req.setTimeout(800, () => {
          req.destroy();
          reject(new Error('timeout'));
        });
      });
      return true;
    } catch {
      await new Promise((r) => setTimeout(r, BACKEND_POLL_INTERVAL));
    }
  }

  return false;
}

// ─── IPC Handlers ────────────────────────────────────────────────────────────

ipcMain.handle('dialog:openFolder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Open Folder',
    properties: ['openDirectory'],
  });

  if (result.canceled || result.filePaths.length === 0) {
    return { cancelled: true };
  }

  return { path: result.filePaths[0] };
});

ipcMain.on('terminal:focus-change', (_event, isFocused) => {
  if (mainWindow) {
    mainWindow.webContents.setIgnoreMenuShortcuts(isFocused);
  }
});

ipcMain.handle('agentos:rollbackTask', async (_event, taskId) => {
  try {
    return new Promise((resolve) => {
      const req = http.request(`${DEVPILOT_URL}/api/files/rollback-task?task_id=${encodeURIComponent(taskId)}`, { method: 'POST' }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve(JSON.parse(body || '{}')));
      });
      req.on('error', () => resolve({ success: false, reason: 'Failed to connect to backend' }));
      req.end();
    });
  } catch (err) {
    return { success: false, reason: err.message };
  }
});

ipcMain.handle('agentos:getTaskDiff', async (_event, taskId) => {
  try {
    return new Promise((resolve) => {
      http.get(`${DEVPILOT_URL}/api/files/task-diff?task_id=${encodeURIComponent(taskId)}`, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve(JSON.parse(body || '{}')));
      }).on('error', () => resolve({ diffs: {} }));
    });
  } catch (err) {
    return { diffs: {} };
  }
});

// ─── Window Creation & Startup ───────────────────────────────────────────────

function getSplashHtml() {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 0;
      background: #0b0c14;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      height: 100vh; user-select: none;
    }
    .logo-container {
      display: flex; align-items: center; justify-content: center;
      width: 64px; height: 64px; border-radius: 16px;
      background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(168, 85, 247, 0.15));
      border: 1px solid rgba(59, 130, 246, 0.3);
      margin-bottom: 24px;
    }
    .spinner {
      width: 28px; height: 28px;
      border: 3px solid rgba(59, 130, 246, 0.2);
      border-top-color: #38bdf8;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .title { font-size: 22px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 6px; color: #ffffff; }
    .subtitle { font-size: 13px; color: #94a3b8; display: flex; align-items: center; gap: 8px; }
  </style>
</head>
<body>
  <div class="logo-container">
    <div class="spinner"></div>
  </div>
  <div class="title">DevPilot AI Editor</div>
  <div class="subtitle">Starting local AI engine & workspace...</div>
</body>
</html>`;
}

function createWindow() {
  const iconPath = path.join(projectRoot, 'assets', 'devpilot.ico');

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1000,
    minHeight: 650,
    title: 'DevPilot AI Editor',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    backgroundColor: '#0b0c14',
    show: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Display instantaneous native splash while engine loads
  mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(getSplashHtml())}`);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ─── App Lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  // Harden renderer: CSP prevents XSS from escalating to Node via preload bridge.
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const responseHeaders = { ...details.responseHeaders };
    responseHeaders['Content-Security-Policy'] = [
      "default-src 'self'; " +
      "script-src 'self'; " +
      "style-src 'self' 'unsafe-inline'; " +
      "img-src 'self' data: blob:; " +
      "font-src 'self' data:; " +
      `connect-src 'self' http://127.0.0.1:${DEVPILOT_PORT} http://localhost:${DEVPILOT_PORT} ws://127.0.0.1:${DEVPILOT_PORT} ws://localhost:${DEVPILOT_PORT}; ` +
      "object-src 'none'; frame-ancestors 'none'; base-uri 'self';"
    ];
    callback({ responseHeaders });
  });

  setApplicationMenu();
  createWindow();

  // Check if backend is already online, otherwise start it in the background
  let ready = await waitForBackend(800);
  if (!ready) {
    startBackendServer();
    ready = await waitForBackend(BACKEND_TIMEOUT);
  }

  if (!ready) {
    dialog.showErrorBox(
      'Initialization Error',
      `DevPilot could not initialize its AI backend service at ${DEVPILOT_URL}.\nPlease make sure Python is installed in the virtual environment.`
    );
    app.quit();
    return;
  }

  // Load the full DevPilot workspace into the native window
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.loadURL(DEVPILOT_URL);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  killBackendServer();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  killBackendServer();
});

app.on('will-quit', () => {
  killBackendServer();
});
