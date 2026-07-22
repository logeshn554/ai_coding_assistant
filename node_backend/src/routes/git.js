'use strict';

const express = require('express');
const router = express.Router();
const { exec } = require('child_process');
const path = require('path');

function runGit(cmd, cwd = process.cwd()) {
  return new Promise((resolve) => {
    exec(`git ${cmd}`, { cwd }, (err, stdout, stderr) => {
      if (err) return resolve({ error: stderr || err.message, stdout: '' });
      resolve({ stdout: stdout.trim(), error: null });
    });
  });
}

// GET /api/git/status
router.get('/api/git/status', async (req, res) => {
  const branchRes = await runGit('rev-parse --abbrev-ref HEAD');
  if (branchRes.error) return res.json({ branch: 'Not a Git Repository', files: [] });
  const statusRes = await runGit('status --porcelain');
  const files = statusRes.stdout
    ? statusRes.stdout.split('\n').map((line) => ({
        status: line.slice(0, 2).trim(),
        path: line.slice(3).trim().replace(/^"/, '').replace(/"$/, ''),
      }))
    : [];
  res.json({ branch: branchRes.stdout, files });
});

// GET /api/git/branches
router.get('/api/git/branches', async (req, res) => {
  const { stdout, error } = await runGit('branch -a');
  if (error) return res.json({ branches: [] });
  const branches = stdout
    .split('\n')
    .map((b) => b.replace('*', '').trim())
    .filter(Boolean);
  res.json({ branches });
});

// GET /api/git/history
router.get('/api/git/history', async (req, res) => {
  const { stdout, error } = await runGit('log -n 15 --pretty=format:"%h - %an, %ar : %s"');
  if (error) return res.json({ history: [] });
  res.json({ history: stdout ? stdout.split('\n') : [] });
});

// GET /api/git/changes
router.get('/api/git/changes', async (req, res) => {
  const statusRes = await runGit('status --porcelain');
  if (statusRes.error) return res.json({ files: [] });
  const files = (statusRes.stdout ? statusRes.stdout.split('\n') : []).map((line) => {
    const status = line.slice(0, 2).trim();
    const filePath = line.slice(3).trim().replace(/^"/, '').replace(/"$/, '');
    return {
      path: filePath,
      name: path.basename(filePath),
      status,
      insertions: 1,
      deletions: 0,
    };
  });
  res.json({ files });
});

// POST /api/git/action
router.post('/api/git/action', async (req, res) => {
  const { action, path: filePath, message, branch } = req.body;
  let cmd = '';
  if (action === 'stage') cmd = `add "${filePath}"`;
  else if (action === 'unstage') cmd = `restore --staged "${filePath}"`;
  else if (action === 'commit') cmd = `commit -m "${message}"`;
  else if (action === 'push') cmd = 'push';
  else if (action === 'pull') cmd = 'pull';
  else if (action === 'checkout') cmd = `checkout "${branch}"`;

  if (!cmd) return res.status(400).json({ message: 'Unknown action' });
  const { error } = await runGit(cmd);
  if (error) return res.status(500).json({ message: error });
  res.json({ success: true });
});

module.exports = router;
