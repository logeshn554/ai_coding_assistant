# DevPilot Node.js Backend

Production-ready Node.js / Express backend for DevPilot IDE, mirroring all 50+ REST endpoints and WebSocket channels.

## Quick Start

```bash
# 1. Install dependencies
npm install

# 2. Start development server
npm run dev
```

The server listens on `http://localhost:8001` with WebSocket support at `ws://localhost:8001/ws/chat`.

## Environment Variables

Copy `.env.example` to `.env`:

```env
PORT=8001
MONGO_URI=mongodb://localhost:27017/devpilot
SESSION_TOKEN=devpilot-session-token-change-me
```

## API Endpoints Summary

- **Workspace**: `/api/workspace`, `/api/workspace/stats`, `/api/health`, `/api/files`
- **Git**: `/api/git/status`, `/api/git/branches`, `/api/git/history`, `/api/git/changes`, `/api/git/action`
- **Profiles**: `/api/profiles`, `/api/profiles/active`, `/api/models/fetch`, `/api/test-connection`
- **Chat**: `/api/chat/sessions`, `/api/chat/history`, `/api/chat/tokenize`
- **Extensions**: `/api/extensions/installed`, `/api/extensions/install`, `/api/extensions/uninstall`
- **Packages**: `/api/packages/list`, `/api/packages/install`, `/api/packages/uninstall`
- **Debug & Tests**: `/api/debug/status`, `/api/scan-bugs`, `/api/testing/discover`
- **Config & Permissions**: `/api/config/settings`, `/api/permissions`
