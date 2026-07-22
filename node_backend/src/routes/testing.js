'use strict';

const express = require('express');
const router = express.Router();

// GET /api/testing/discover
router.get('/api/testing/discover', (req, res) => {
  res.json({
    tests: [
      { id: 't1', name: 'app.test.js - GET /api/health', status: 'passed' },
      { id: 't2', name: 'auth.test.js - Bearer authentication', status: 'passed' },
    ],
  });
});

// POST /api/testing/run
router.post('/api/testing/run', (req, res) => {
  res.json({
    success: true,
    results: [
      { id: 't1', status: 'passed', durationMs: 45 },
      { id: 't2', status: 'passed', durationMs: 32 },
    ],
  });
});

module.exports = router;
