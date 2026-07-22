/**
 * preload.js — runs in the renderer's context with Node.js access disabled.
 * Exposes ONLY window.electronAPI.openFolder() to the renderer via contextBridge.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Opens the native OS folder picker dialog.
   * @returns {Promise<{path: string} | {cancelled: true}>}
   */
  openFolder: () => ipcRenderer.invoke('dialog:openFolder'),
});
