const express = require('express');
const cors = require('cors');
const http = require('http');
const { WebSocketServer } = require('ws');

const app = express();
const port = process.env.PORT || 8001;

app.use(cors());
app.use(express.json());

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'node_backend', version: '1.0.0' });
});

// Workspace routes
app.get('/api/workspace', (req, res) => {
  res.json({ root: process.cwd(), files: [] });
});

app.get('/api/workspace/stats', (req, res) => {
  res.json({ totalFiles: 0, totalLines: 0 });
});

app.get('/api/files', (req, res) => {
  res.json({ files: [] });
});

// Git routes
app.get('/api/git/status', (req, res) => {
  res.json({ branch: 'main', clean: true, changes: [] });
});

app.get('/api/git/branches', (req, res) => {
  res.json({ current: 'main', branches: ['main'] });
});

app.get('/api/git/history', (req, res) => {
  res.json({ commits: [] });
});

app.get('/api/git/changes', (req, res) => {
  res.json({ changes: [] });
});

app.post('/api/git/action', (req, res) => {
  res.json({ success: true, action: req.body?.action || 'none' });
});

// Profiles & Models
app.get('/api/profiles', (req, res) => {
  res.json({ profiles: [] });
});

app.get('/api/profiles/active', (req, res) => {
  res.json({ active: 'default' });
});

app.get('/api/models/fetch', (req, res) => {
  res.json({ models: ['gpt-4o', 'claude-3-5-sonnet', 'gemini-1.5-pro'] });
});

app.post('/api/test-connection', (req, res) => {
  res.json({ success: true, message: 'Connection successful' });
});

// Chat routes
app.get('/api/chat/sessions', (req, res) => {
  res.json({ sessions: [] });
});

app.get('/api/chat/history', (req, res) => {
  res.json({ history: [] });
});

app.post('/api/chat/tokenize', (req, res) => {
  const text = req.body?.text || '';
  res.json({ tokens: Math.ceil(text.length / 4) });
});

// Extensions
app.get('/api/extensions/installed', (req, res) => {
  res.json({ extensions: [] });
});

app.post('/api/extensions/install', (req, res) => {
  res.json({ success: true, extension: req.body?.name });
});

app.post('/api/extensions/uninstall', (req, res) => {
  res.json({ success: true, extension: req.body?.name });
});

// Packages
app.get('/api/packages/list', (req, res) => {
  res.json({ packages: [] });
});

app.post('/api/packages/install', (req, res) => {
  res.json({ success: true, package: req.body?.name });
});

app.post('/api/packages/uninstall', (req, res) => {
  res.json({ success: true, package: req.body?.name });
});

// Debug & Tests
app.get('/api/debug/status', (req, res) => {
  res.json({ running: false, session: null });
});

app.post('/api/scan-bugs', (req, res) => {
  res.json({ bugs: [] });
});

app.get('/api/testing/discover', (req, res) => {
  res.json({ tests: [] });
});

// Config & Permissions
app.get('/api/config/settings', (req, res) => {
  res.json({ settings: {} });
});

app.get('/api/permissions', (req, res) => {
  res.json({ permissions: [] });
});

const server = http.createServer(app);

// WebSocket support
const wss = new WebSocketServer({ server, path: '/ws/chat' });
wss.on('connection', (ws) => {
  ws.send(JSON.stringify({ type: 'connected', message: 'Connected to DevPilot Node Backend WebSocket' }));
  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message.toString());
      ws.send(JSON.stringify({ type: 'response', echo: data }));
    } catch {
      ws.send(JSON.stringify({ type: 'error', message: 'Invalid JSON payload' }));
    }
  });
});

server.listen(port, () => {
  console.log(`DevPilot Node Backend listening at http://localhost:${port}`);
});
