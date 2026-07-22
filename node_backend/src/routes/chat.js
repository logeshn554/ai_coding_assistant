'use strict';

const express = require('express');
const router = express.Router();
const ChatSession = require('../models/ChatSession');

let inMemorySessions = [
  {
    id: 'default-session',
    title: 'Default Conversation',
    messages: [],
    updated_at: new Date().toISOString(),
  },
];
let activeSessionId = 'default-session';

// GET /api/chat/sessions
router.get('/api/chat/sessions', async (req, res) => {
  try {
    const dbSessions = await ChatSession.find().lean();
    if (dbSessions.length > 0) {
      return res.json({ sessions: dbSessions, active_session_id: activeSessionId });
    }
  } catch {}
  res.json({ sessions: inMemorySessions, active_session_id: activeSessionId });
});

// POST /api/chat/sessions
router.post('/api/chat/sessions', async (req, res) => {
  const { title = 'New Chat' } = req.body;
  const newSession = {
    id: `sess_${Date.now()}`,
    title,
    messages: [],
    updated_at: new Date().toISOString(),
  };
  try {
    await ChatSession.create(newSession);
  } catch {
    inMemorySessions.push(newSession);
  }
  activeSessionId = newSession.id;
  res.json({ success: true, session: newSession });
});

// GET /api/chat/sessions/:id
router.get('/api/chat/sessions/:id', async (req, res) => {
  const { id } = req.params;
  try {
    const session = await ChatSession.findOne({ id }).lean();
    if (session) return res.json({ session });
  } catch {}
  const session = inMemorySessions.find((s) => s.id === id) || inMemorySessions[0];
  res.json({ session });
});

// PUT /api/chat/sessions/:id
router.put('/api/chat/sessions/:id', async (req, res) => {
  const { id } = req.params;
  const { title } = req.body;
  try {
    await ChatSession.updateOne({ id }, { title });
  } catch {
    const sess = inMemorySessions.find((s) => s.id === id);
    if (sess) sess.title = title;
  }
  res.json({ success: true });
});

// DELETE /api/chat/sessions/:id
router.delete('/api/chat/sessions/:id', async (req, res) => {
  const { id } = req.params;
  try {
    await ChatSession.deleteOne({ id });
  } catch {
    inMemorySessions = inMemorySessions.filter((s) => s.id !== id);
  }
  if (activeSessionId === id) {
    activeSessionId = inMemorySessions[0]?.id || 'default-session';
  }
  res.json({ success: true });
});

// GET /api/chat/history
router.get('/api/chat/history', async (req, res) => {
  let messages = [];
  try {
    const sess = await ChatSession.findOne({ id: activeSessionId }).lean();
    if (sess) messages = sess.messages || [];
  } catch {
    const sess = inMemorySessions.find((s) => s.id === activeSessionId);
    if (sess) messages = sess.messages || [];
  }
  res.json({ messages });
});

// POST /api/chat/tokenize
router.post('/api/chat/tokenize', (req, res) => {
  const { messages = [] } = req.body;
  const totalChars = messages.reduce((acc, m) => acc + (m.content ? String(m.content).length : 0), 0);
  const approxTokens = Math.ceil(totalChars / 4);
  res.json({ tokens: approxTokens });
});

module.exports = router;
