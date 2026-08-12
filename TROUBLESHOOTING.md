# Troubleshooting & Recovery Guide — DevPilot IDE

## Common Issues & Recovery

1. **Permission Approval Blocked**: Verify session state mode (`Strict`, `Assisted`, `Autonomous`). Respond via `ApprovalCard` UI.
2. **Session Interrupted / Crashed**: DevPilot automatically recovers session state from persistent snapshots via `SessionRecoveryManager`.
3. **Port Conflicts**: Backend defaults to port 8000. Configure via environment `PORT`.
