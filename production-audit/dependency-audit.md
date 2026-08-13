# Dependency Audit — DevPilot IDE Platform

This document audits Python requirements and Node package dependencies, highlighting risks, dependency sprawl, version conflicts, and opportunities to minimize production images.

---

## 1. Python Dependency Audits (`backend/requirements.txt`)

### Heavy Dependencies & Sprawl

1. **`chromadb>=0.4.0` (Vector Storage):**
   - **Risk:** ChromaDB includes native C++ dependencies (like `hnswlib` and `pysqlite3-binary`) that require compilation on installation. This adds ~300MB+ to the final Docker container image size and slows down build pipelines.
   - **Fix:** Move vector storage interfaces behind a generic `VectorStore` adapter. Isolate the actual database engine to a separate container (e.g. pgvector) so the control plane image stays thin.
2. **`pytesseract>=0.3.10` & `Pillow>=10.0.0` (Vision/OCR):**
   - **Risk:** Pytesseract is a wrapper around the Google Tesseract OCR binary. If the underlying OS packages (`tesseract-ocr`) are not installed on the system, the application will crash during runtime when analyzing images.
   - **Fix:** Isolate vision and OCR features into a dedicated worker service.
3. **`pywebview>=3.0` (Desktop GUI):**
   - **Risk:** Pywebview is used to render local native desktop panels on client machines. It is completely unused in the hosted FastAPI server control plane.
   - **Fix:** Separate pywebview into a dedicated `desktop` package group that is excluded from the server's production requirements.

### Version Constraints Analysis

- **Open Range Risk:** Many libraries in requirements.txt use open boundaries (e.g. `fastapi>=0.100.0`, `redis>=5.0.0`, `mcp>=1.0.0`). This introduces non-deterministic builds where minor dependency releases can break the production server.
- **Fix:** Pin dependencies to strict locked versions (e.g., `fastapi==0.110.0`) or migrate to `pyproject.toml` utilizing poetry/pip-compile lockfiles.

---

## 2. Frontend Dependency Audits (`frontend/package.json`)

- **Core Tech Stack:** React 18, Vite 5, TypeScript 5.
- **Key Modules:**
  - Monaco Editor (`@monaco-editor/react`) for full IDE editor panels.
  - Xterm.js (`xterm`, `xterm-addon-fit`) for terminal emulator shells.
- **Findings:**
  - Build scripts are configured correctly.
  - Dev dependencies are separated from runtime dependencies.
  - Oxlint (`.oxlintrc.json`) is integrated for fast code analysis, though it should be run in CI.
