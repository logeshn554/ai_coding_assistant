'use strict';

const express = require('express');
const router = express.Router();

const workspaceRouter = require('./workspace');
const gitRouter = require('./git');
const profilesRouter = require('./profiles');
const chatRouter = require('./chat');
const extensionsRouter = require('./extensions');
const packagesRouter = require('./packages');
const debugRouter = require('./debug');
const testingRouter = require('./testing');
const configRouter = require('./config');

router.use(workspaceRouter);
router.use(gitRouter);
router.use(profilesRouter);
router.use(chatRouter);
router.use(extensionsRouter);
router.use(packagesRouter);
router.use(debugRouter);
router.use(testingRouter);
router.use(configRouter);

module.exports = router;
