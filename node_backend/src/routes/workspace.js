'use strict';

const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

let currentWorkspacePath = process.cwd();

// GET /api/workspace
router.get('/api/workspace', (req, res) => {
  res.json({ path: currentWorkspacePath });
});

// POST /api/workspace/change
router.post('/api/workspace/change', (req, res) => {
  const { path: newPath } = req.body;
  if (newPath && fs.existsSync(newPath)) {
    currentWorkspacePath = path.resolve(newPath);
    return res.json({ success: true, path: currentWorkspacePath });
  }
  res.status(400).json({ success: false, message: 'Invalid directory path' });
});

// GET /api/workspace/stats
router.get('/api/workspace/stats', (req, res) => {
  const extMap = {
    '.py': 'Python', '.ts': 'TypeScript', '.tsx': 'TypeScript',
    '.js': 'JavaScript', '.jsx': 'JavaScript', '.html': 'HTML',
    '.css': 'CSS', '.json': 'JSON', '.md': 'Markdown',
  };
  const skipDirs = new Set(['.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build']);
  
  let totalFiles = 0;
  let totalLines = 0;
  const langCounts = {};

  function scan(dir) {
    let files;
    try { files = fs.readdirSync(dir); } catch { return; }
    for (const f of files) {
      if (skipDirs.has(f) || f.startsWith('.')) continue;
      const full = path.join(dir, f);
      try {
        const stat = fs.statSync(full);
        if (stat.isDirectory()) {
          scan(full);
        } else if (stat.isFile()) {
          const ext = path.extname(f).toLowerCase();
          const lang = extMap[ext];
          if (lang) {
            totalFiles++;
            langCounts[lang] = (langCounts[lang] || 0) + 1;
            try {
              const content = fs.readFileSync(full, 'utf8');
              totalLines += content.split('\n').length;
            } catch {}
          }
        }
      } catch {}
    }
  }

  scan(currentWorkspacePath);

  const grandTotal = Object.values(langCounts).reduce((a, b) => a + b, 0);
  const languages = {};
  if (grandTotal > 0) {
    for (const [lang, cnt] of Object.entries(langCounts)) {
      languages[lang] = Number(((cnt / grandTotal) * 100).toFixed(1));
    }
  }

  exec('git rev-list --count HEAD', { cwd: currentWorkspacePath }, (err, stdout) => {
    const gitCommits = err ? 0 : parseInt(stdout.trim() || '0', 10);
    res.json({
      total_files: totalFiles,
      total_lines: totalLines,
      languages,
      git_commits: gitCommits,
    });
  });
});

// GET /api/health
router.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    db_connected: true,
    uptime_seconds: process.uptime(),
  });
});

// GET /api/files
router.get('/api/files', (req, res) => {
  function getTree(dir) {
    const skipDirs = new Set(['.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build']);
    const items = [];
    try {
      const files = fs.readdirSync(dir);
      for (const f of files) {
        if (skipDirs.has(f) || f.startsWith('.')) continue;
        const full = path.join(dir, f);
        const stat = fs.statSync(full);
        const rel = path.relative(currentWorkspacePath, full).replace(/\\/g, '/');
        if (stat.isDirectory()) {
          items.push({ name: f, path: rel, type: 'directory', children: getTree(full) });
        } else {
          items.push({ name: f, path: rel, type: 'file' });
        }
      }
    } catch {}
    return items;
  }
  res.json({ files: getTree(currentWorkspacePath) });
});

// GET /api/files/content
router.get('/api/files/content', (req, res) => {
  const relPath = req.query.path;
  if (!relPath) return res.status(400).json({ message: 'Path required' });
  const full = path.resolve(currentWorkspacePath, relPath);
  try {
    const content = fs.readFileSync(full, 'utf8');
    res.json({ content });
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

// POST /api/files/create
router.post('/api/files/create', (req, res) => {
  const { path: relPath, type = 'file' } = req.body;
  if (!relPath) return res.status(400).json({ message: 'Path required' });
  const full = path.resolve(currentWorkspacePath, relPath);
  try {
    if (type === 'directory') {
      fs.mkdirSync(full, { recursive: true });
    } else {
      fs.mkdirSync(path.dirname(full), { recursive: true });
      fs.writeFileSync(full, '', 'utf8');
    }
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

// POST /api/files/delete
router.post('/api/files/delete', (req, res) => {
  const { path: relPath } = req.body;
  if (!relPath) return res.status(400).json({ message: 'Path required' });
  const full = path.resolve(currentWorkspacePath, relPath);
  try {
    fs.rmSync(full, { recursive: true, force: true });
    res.json({ success: true });
  } catch (e) {
    res.status(500).json({ message: e.message });
  }
});

// GET /api/files/search
router.get('/api/files/search', (req, res) => {
  const query = (req.query.query || '').trim().toLowerCase();
  if (!query) return res.json([]);
  const results = [];
  const skipDirs = new Set(['.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build']);

  function search(dir) {
    try {
      const files = fs.readdirSync(dir);
      for (const f of files) {
        if (skipDirs.has(f) || f.startsWith('.')) continue;
        const full = path.join(dir, f);
        const stat = fs.statSync(full);
        if (stat.isDirectory()) {
          search(full);
        } else if (stat.isFile()) {
          const rel = path.relative(currentWorkspacePath, full).replace(/\\/g, '/');
          try {
            const content = fs.readFileSync(full, 'utf8');
            const lines = content.split('\n');
            lines.forEach((line, idx) => {
              if (line.toLowerCase().includes(query)) {
                results.push({ path: rel, line: idx + 1, content: line.trim() });
              }
            });
          } catch {}
        }
      }
    } catch {}
  }

  search(currentWorkspacePath);
  res.json(results.slice(0, 100));
});

module.exports = router;
