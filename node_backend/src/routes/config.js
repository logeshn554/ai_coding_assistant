'use strict';

const express = require('express');
const router = express.Router();
const Settings = require('../models/Settings');
const Permission = require('../models/Permission');

let settingsMemory = {
  exclude_list: ['.git', 'node_modules', 'venv', '__pycache__'],
  auto_backup_enabled: true,
  agent_model_name: '',
  agent_models: {},
  default_shell: '',
  terminal_font_size: 13,
  terminal_scrollback: 5000,
};

let permissionsMemory = {
  project: [],
  session: [],
};

// GET /api/config/settings
router.get('/api/config/settings', async (req, res) => {
  try {
    const dbSettings = await Settings.findOne().lean();
    if (dbSettings) return res.json(dbSettings);
  } catch {}
  res.json(settingsMemory);
});

// POST /api/config/settings
router.post('/api/config/settings', async (req, res) => {
  const newSettings = req.body;
  try {
    await Settings.updateOne({}, newSettings, { upsert: true });
  } catch {}
  settingsMemory = { ...settingsMemory, ...newSettings };
  res.json({ success: true });
});

// GET /api/permissions
router.get('/api/permissions', async (req, res) => {
  try {
    const perms = await Permission.find().lean();
    const project = perms.filter((p) => p.scope === 'project').map((p) => p.command);
    const session = perms.filter((p) => p.scope === 'session').map((p) => p.command);
    return res.json({ project, session });
  } catch {}
  res.json(permissionsMemory);
});

// POST /api/permissions/revoke
router.post('/api/permissions/revoke', async (req, res) => {
  const { command, scope } = req.body;
  try {
    await Permission.deleteOne({ command, scope });
  } catch {
    if (permissionsMemory[scope]) {
      permissionsMemory[scope] = permissionsMemory[scope].filter((c) => c !== command);
    }
  }
  res.json({ success: true });
});

module.exports = router;
