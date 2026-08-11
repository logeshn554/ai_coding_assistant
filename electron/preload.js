/**
 * preload.js — runs in the renderer's context with Node.js access disabled.
 * Exposes a secure electronAPI surface to the renderer via contextBridge.
 *
 * Available APIs:
 *   - openFolder()           — Opens the native OS folder picker dialog.
 *   - getSystemStatus()      — Returns the AgentOS boot/health status.
 *   - onParallelProgress(cb) — Subscribes to real-time parallel task progress events.
 *   - cancelTask(taskId)     — Cancels a running parallel subtask by ID.
 *   - onAgentState(cb)       — Subscribes to agent state change events.
 *   - removeAllListeners(ch) — Cleans up IPC listeners for a given channel.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Opens the native OS folder picker dialog.
   * @returns {Promise<{path: string} | {cancelled: true}>}
   */
  openFolder: () => ipcRenderer.invoke('dialog:openFolder'),

  /**
   * Queries the current AgentOS system status (boot state, token budget, running tasks).
   * @returns {Promise<{status: string, workspace_root: string, token_budget: number, current_tokens: number, concurrency_limit: number, total_files_indexed: number, running_tasks: number}>}
   */
  getSystemStatus: () => ipcRenderer.invoke('agentos:status'),

  /**
   * Subscribes to real-time parallel task progress updates.
   * Each event payload: { subtasks: Array, collaboration_log: Array, active_agent: string }
   * @param {(event: Electron.IpcRendererEvent, data: object) => void} callback
   * @returns {() => void} Unsubscribe function
   */
  onParallelProgress: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('parallel:progress', handler);
    return () => ipcRenderer.removeListener('parallel:progress', handler);
  },

  /**
   * Cancels a running parallel subtask by its ID.
   * @param {string} taskId — The subtask UUID to cancel.
   * @returns {Promise<{success: boolean, message: string}>}
   */
  cancelTask: (taskId) => ipcRenderer.invoke('agentos:cancelTask', taskId),

  /**
   * Subscribes to agent state change events (agent switching, task completion).
   * @param {(event: Electron.IpcRendererEvent, data: object) => void} callback
   * @returns {() => void} Unsubscribe function
   */
  onAgentState: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('agent:state', handler);
    return () => ipcRenderer.removeListener('agent:state', handler);
  },

  /**
   * Removes all listeners for a given IPC channel (cleanup on unmount).
   * @param {string} channel
   */
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  },
});

