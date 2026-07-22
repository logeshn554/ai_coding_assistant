'use strict';

const mongoose = require('mongoose');

const SettingsSchema = new mongoose.Schema(
  {
    exclude_list: { type: [String], default: ['.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build'] },
    auto_backup_enabled: { type: Boolean, default: true },
    agent_model_name: { type: String, default: '' },
    agent_models: { type: Map, of: String, default: {} },
    default_shell: { type: String, default: '' },
    terminal_font_size: { type: Number, default: 13 },
    terminal_scrollback: { type: Number, default: 5000 },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Settings', SettingsSchema);
