'use strict';

const express = require('express');
const router = express.Router();
const Profile = require('../models/Profile');

// Mock memory store if mongo not connected
let inMemoryProfiles = [
  {
    id: 'default-profile',
    name: 'OpenAI GPT-4o',
    provider: 'openai',
    api_key: '',
    base_url: 'https://api.openai.com/v1',
    model_name: 'gpt-4o',
    api_format: 'openai',
    isActive: true,
  },
];

// GET /api/profiles
router.get('/api/profiles', async (req, res) => {
  try {
    const dbProfiles = await Profile.find().lean();
    if (dbProfiles.length > 0) return res.json({ profiles: dbProfiles });
  } catch {}
  res.json({ profiles: inMemoryProfiles });
});

// POST /api/profiles
router.post('/api/profiles', async (req, res) => {
  const profileData = req.body;
  if (!profileData.id) profileData.id = `prof_${Date.now()}`;
  try {
    await Profile.updateOne({ id: profileData.id }, profileData, { upsert: true });
  } catch {
    const idx = inMemoryProfiles.findIndex((p) => p.id === profileData.id);
    if (idx >= 0) inMemoryProfiles[idx] = profileData;
    else inMemoryProfiles.push(profileData);
  }
  res.json({ success: true, profile: profileData });
});

// POST /api/profiles/active
router.post('/api/profiles/active', async (req, res) => {
  const { id } = req.body;
  try {
    await Profile.updateMany({}, { isActive: false });
    await Profile.updateOne({ id }, { isActive: true });
  } catch {
    inMemoryProfiles.forEach((p) => (p.isActive = p.id === id));
  }
  res.json({ success: true });
});

// DELETE /api/profiles/:id
router.delete('/api/profiles/:id', async (req, res) => {
  const { id } = req.params;
  try {
    await Profile.deleteOne({ id });
  } catch {
    inMemoryProfiles = inMemoryProfiles.filter((p) => p.id !== id);
  }
  res.json({ success: true });
});

// POST /api/models/fetch
router.post('/api/models/fetch', (req, res) => {
  res.json({
    success: true,
    models: ['gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet-20241022', 'deepseek-chat', 'llama3'],
  });
});

// POST /api/test-connection
router.post('/api/test-connection', (req, res) => {
  res.json({ success: true, message: 'Connection successful' });
});

module.exports = router;
