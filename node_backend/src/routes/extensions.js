'use strict';

const express = require('express');
const router = express.Router();

let extensions = [
  { id: 'python', name: 'Python Rich Language', description: 'Syntax highlighting, auto-completions', version: 'v2.1.0', installed: true },
  { id: 'prettier', name: 'Prettier Code Formatter', description: 'Opinionated code formatter', version: 'v3.0.1', installed: true },
  { id: 'gitlens', name: 'GitLens Sidebar tool', description: 'Visualize git commit history', version: 'v11.4.0', installed: false },
  { id: 'copilot', name: 'DevPilot Autocomplete', description: 'Real-time AI completions', version: 'v1.0.0', installed: true },
  { id: 'docker', name: 'Docker integration', description: 'Manage Docker containers', version: 'v1.22.0', installed: false },
];

// GET /api/extensions/installed
router.get('/api/extensions/installed', (req, res) => {
  res.json({ extensions });
});

// POST /api/extensions/install
router.post('/api/extensions/install', (req, res) => {
  const { id } = req.body;
  const ext = extensions.find((e) => e.id === id);
  if (ext) ext.installed = true;
  res.json({ success: true });
});

// POST /api/extensions/uninstall
router.post('/api/extensions/uninstall', (req, res) => {
  const { id } = req.body;
  const ext = extensions.find((e) => e.id === id);
  if (ext) ext.installed = false;
  res.json({ success: true });
});

module.exports = router;
