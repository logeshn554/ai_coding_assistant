'use strict';

const os = require('os');
const path = require('path');
const url = require('url');
const pty = require('node-pty');

const SESSION_TOKEN = process.env.SESSION_TOKEN || 'devpilot-session-token-change-me';

function getShellCommand(requestedShell) {
  if (os.platform() === 'win32') {
    if (requestedShell === 'powershell') {
      const systemRoot = process.env.SystemRoot || 'C:\\Windows';
      return path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
    } else if (requestedShell === 'cmd') {
      return 'cmd.exe';
    } else if (requestedShell === 'bash') {
      return 'bash.exe';
    } else if (requestedShell === 'wsl') {
      return 'wsl.exe';
    }
    // Default on Windows
    const systemRoot = process.env.SystemRoot || 'C:\\Windows';
    return path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
  } else {
    if (requestedShell === 'bash') {
      return '/bin/bash';
    } else if (requestedShell === 'sh') {
      return '/bin/sh';
    }
    return process.env.SHELL || '/bin/bash';
  }
}

function handleTerminalSocket(ws, req) {
  const parsedUrl = url.parse(req.url, true);
  const token = parsedUrl.query.token;
  const requestedShell = parsedUrl.query.shell;

  if (process.env.NODE_ENV === 'production' && (!token || token !== SESSION_TOKEN)) {
    try {
      ws.send(JSON.stringify({ type: 'error', message: 'Unauthorized: invalid or missing token.' }));
      ws.close(4401);
    } catch (e) {}
    return;
  }

  const shellCmd = getShellCommand(requestedShell);
  const cwd = process.cwd() || os.homedir();

  let ptyProcess;
  try {
    ptyProcess = pty.spawn(shellCmd, [], {
      name: 'xterm-256color',
      cols: 120,
      rows: 30,
      cwd: cwd,
      env: process.env,
    });
  } catch (err) {
    console.error('Failed to spawn terminal process:', err);
    try {
      ws.send(`\r\nFailed to start terminal shell: ${err.message}\r\n`);
      ws.close();
    } catch (e) {}
    return;
  }

  ptyProcess.onData((data) => {
    try {
      ws.send(data);
    } catch (err) {
      // WebSocket may be closed
    }
  });

  ptyProcess.onExit(({ exitCode, signal }) => {
    try {
      ws.send(`\r\nTerminal process exited with code ${exitCode}.\r\n`);
      ws.close();
    } catch (err) {
      // Ignored
    }
  });

  ws.on('message', (message) => {
    try {
      const dataStr = message.toString();
      if (dataStr.startsWith('{')) {
        try {
          const parsed = JSON.parse(dataStr);
          if (parsed && parsed.type === 'resize') {
            const cols = parsed.cols || 120;
            const rows = parsed.rows || 30;
            ptyProcess.resize(cols, rows);
            return;
          }
        } catch (e) {
          // Fail-safe: treat as raw input if JSON parsing fails
        }
      }
      ptyProcess.write(dataStr);
    } catch (err) {
      console.error('Failed to write to terminal process:', err);
    }
  });

  ws.on('close', () => {
    try {
      ptyProcess.kill();
    } catch (err) {
      // Ignored
    }
  });

  ws.on('error', (err) => {
    console.error('WebSocket error in terminal socket:', err);
    try {
      ptyProcess.kill();
    } catch (e) {}
  });
}

module.exports = { handleTerminalSocket };
