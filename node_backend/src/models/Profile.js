'use strict';

const mongoose = require('mongoose');

const ProfileSchema = new mongoose.Schema(
  {
    id: { type: String, required: true, unique: true },
    name: { type: String, required: true },
    provider: { type: String, default: 'openai' },
    api_key: { type: String, default: '' },
    base_url: { type: String, default: '' },
    model_name: { type: String, default: '' },
    api_format: { type: String, default: 'openai' },
    isActive: { type: Boolean, default: false },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Profile', ProfileSchema);
