'use strict';

const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');

// GET /api/packages/list
router.get('/api/packages/list', (req, res) => {
  const pkgPath = path.join(process.cwd(), 'package.json');
  if (!fs.existsSync(pkgPath)) return res.json({ packages: [] });
  try {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
    const deps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };
    const packages = Object.entries(deps).map(([name, version]) => ({
      name,
      version: String(version),
      type: pkg.dependencies && pkg.dependencies[name] ? 'dependency' : 'devDependency',
    }));
    res.json({ packages });
  } catch (e) {
    res.json({ packages: [] });
  }
});

// POST /api/packages/install
router.post('/api/packages/install', (req, res) => {
  res.json({ success: true, message: 'Package installation triggered' });
});

// POST /api/packages/uninstall
router.post('/api/packages/uninstall', (req, res) => {
  res.json({ success: true, message: 'Package uninstallation triggered' });
});

module.exports = router;
