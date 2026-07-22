'use strict';

const mongoose = require('mongoose');

const PermissionSchema = new mongoose.Schema(
  {
    command: { type: String, required: true },
    scope: { type: String, enum: ['project', 'session'], required: true },
    grantedAt: { type: Date, default: Date.now },
  },
  { timestamps: true }
);

module.exports = mongoose.model('Permission', PermissionSchema);
