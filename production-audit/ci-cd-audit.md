# CI/CD Audit — DevPilot IDE Platform

This document audits the CI/CD pipeline configuration, detailing execution path errors, coverage scope issues, and missing verification gates.

---

## 1. Audited Workflow Path Failures

The current [ci.yml](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/.github/workflows/ci.yml) workflow was verified to contain path errors:

- **The Problem:** The pytest execution script originally contained:
  `python -m pytest --cov=agent_os --cov-report=xml --cov-report=term-missing --cov-fail-under=70 agent_os/tests/ backend/tests/`
- **Path Issues:**
  1. **Non-Existent Target Directories:** Neither `agent_os/tests/` nor `backend/tests/` exists in the repository. The actual test files reside in `tests/` at the repository root. This caused pytest to fail immediately.
  2. **Incorrect Coverage Focus:** `--cov=agent_os` measures test coverage of the `agent_os` directory. `agent_os` contains no source files (it is an empty scratch space directory), causing Python coverage to report 0% and fail the `cov-fail-under=70` quality gate.
- **Fixed Path Configuration:** We updated [ci.yml](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/.github/workflows/ci.yml) during the stabilization phase of Phase 1 to execute:
  `python -m pytest --cov=backend/app --cov-report=xml --cov-report=term-missing --cov-fail-under=70 tests/`

---

## 2. Missing Quality Gates and Scanners

For a production-grade release process, the CI pipeline lacks:

1. **Security Vulnerability Auditing:**
   - No Python static AST analyzer (e.g. `bandit`) is run to catch vulnerabilities like unsafe subprocess flags.
   - No secret scanning tools (e.g. `gitleaks` or `trufflehog`) are configured to scan commits for exposed API keys or certificates.
2. **Frontend Type Checking:**
   - The `frontend-build` job executes `npm ci` and `npm run build` but does not explicitly run a type checking gate (`tsc --noEmit`) or linting rules (`oxlint` or `eslint`) to prevent compiler errors from reaching staging.
3. **Container Security Scanning:**
   - No vulnerability scanner (e.g., `trivy` or `anchore`) is run against the generated Docker images to scan for vulnerable OS packages or base library issues.
4. **CI/CD Service Dependencies:**
   - Tests that check Redis connectivity (e.g., in `db.py` fallback routes) mock connection state because no active Redis service container is started as a companion service in the GitHub Actions runner.
