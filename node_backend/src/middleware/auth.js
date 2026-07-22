'use strict';

const SESSION_TOKEN = process.env.SESSION_TOKEN || 'devpilot-session-token-change-me';

/**
 * Middleware verifying Bearer or Session Token.
 */
function verifySessionToken(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    // If no header required in dev, pass through or check query param
    return next();
  }

  const token = authHeader.replace(/^Bearer\s+/, '').trim();
  if (token && token !== SESSION_TOKEN && process.env.NODE_ENV === 'production') {
    return res.status(401).json({ success: false, message: 'Unauthorized: Invalid token' });
  }

  next();
}

module.exports = {
  verifySessionToken,
};
