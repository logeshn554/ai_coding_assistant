/**
 * main.js — Electron main process for DevPilot.
 *
 * Responsibilities:
 *  1. Open a BrowserWindow that loads the DevPilot web app (http://localhost:8000)
 *  2. Handle 'dialog:openFolder' IPC → show native OS folder picker
 *  3. Return the selected path (or cancelled flag) to the renderer
 */

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');

// The DevPilot backend URL (must be running before launching Electron)
const DEVPILOT_URL = 'http://localhost:8000';

// How long to wait for the backend to be ready before loading (ms)
const BACKEND_POLL_INTERVAL = 500;
const BACKEND_TIMEOUT = 30_000;

let mainWindow = null;

// ─── IPC Handler ────────────────────────────────────────────────────────────

/**
 * 'dialog:openFolder'
 * Opens the native OS folder selection dialog.
 * Returns { path: string } on success, { cancelled: true } if the user cancels.
 */
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

// ─── Window Creation ─────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    title: 'DevPilot',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,   // Required for contextBridge security
      nodeIntegration: false,   // Never expose Node in renderer
    },
  });

  // Load the running DevPilot web app
  mainWindow.loadURL(DEVPILOT_URL);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ─── Backend Ready Check ─────────────────────────────────────────────────────

/**
 * Polls localhost:8000 until the backend responds, then creates the window.
 * This prevents a blank screen if Electron starts before the server is up.
 */
async function waitForBackend(timeout = BACKEND_TIMEOUT) {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    try {
      // Node's built-in http — no need for node-fetch
      await new Promise((resolve, reject) => {
        const http = require('http');
        const req = http.get(DEVPILOT_URL, (res) => {
          res.destroy();
          resolve();
        });
        req.on('error', reject);
        req.setTimeout(1000, () => { req.destroy(); reject(new Error('timeout')); });
      });
      return true; // Backend is up
    } catch {
      await new Promise((r) => setTimeout(r, BACKEND_POLL_INTERVAL));
    }
  }

  return false; // Timed out
}

// ─── App Lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  const ready = await waitForBackend();

  if (!ready) {
    console.error(
      `[DevPilot Electron] Backend at ${DEVPILOT_URL} did not respond within ${BACKEND_TIMEOUT / 1000}s.\n` +
      'Make sure DevPilot is running (docker compose up or npm start) before launching Electron.'
    );
    app.quit();
    return;
  }

  createWindow();

  // macOS: re-create the window when clicking the dock icon with no windows open
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Quit when all windows are closed (except on macOS)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
