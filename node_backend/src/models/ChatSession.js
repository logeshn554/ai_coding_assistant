'use strict';

const mongoose = require('mongoose');

const MessageSchema = new mongoose.Schema({
  id: { type: String, required: true },
  role: { type: String, enum: ['user', 'assistant', 'system', 'tool'], required: true },
  content: { type: mongoose.Schema.Types.Mixed, default: '' },
  name: { type: String },
  tool_call_id: { type: String },
  status: { type: String },
  tool_calls: { type: Array, default: [] },
  diff: { type: Object },
  cost_usd: { type: Number },
  agents_used: { type: Number },
  elapsed_ms: { type: Number },
  thinkingSteps: { type: [String], default: [] },
  timestamp: { type: Number, default: () => Math.floor(Date.now() / 1000) },
});

const ChatSessionSchema = new mongoose.Schema(
  {
    id: { type: String, required: true, unique: true },
    title: { type: String, required: true, default: 'New Conversation' },
    messages: [MessageSchema],
  },
  { timestamps: true }
);

module.exports = mongoose.model('ChatSession', ChatSessionSchema);
