# Loopix — AI-Native Developer IDE & Agentic Operating System

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![React + TypeScript](https://img.shields.io/badge/frontend-React%20%2B%20TypeScript-61dafb.svg)](frontend/)

> **Loopix is an AI-native developer IDE and agentic operating system that understands your entire software codebase, plans complex tasks, edits files transactionally, runs terminal commands, executes tests, and manages VS Code extensions while keeping the developer in full control.**

---

## 🌟 Key Capabilities

- **Universal Multi-Agent Orchestrator**: Supports 8 specialized execution modes (`Ask`, `Plan`, `Assist`, `Code`, `Debug`, `Review`, `Architect`, `Autonomous`) with live visual execution timelines.
- **Dynamic VS Code Extension Engine**: Native support for VS Code extension packages (`.vsix`/`ZIP`), extracting manifest commands, snippets, and registering custom AI tools dynamically.
- **Centralized Security & Permission Engine**: Fine-grained capability security (`READ_FILES`, `WRITE_FILES`, `RUN_COMMAND`, `BROWSER`, etc.) with `Safe`, `Balanced`, `Autonomous`, and `Custom` permission policies.
- **Transactional File System**: Pre-edit atomic snapshotting, side-by-side diff previews, and instant one-click task rollbacks.
- **Prompt-Injection Defense**: Strict boundary tag isolation protecting system instructions against untrusted codebase inputs.
- **Incremental Codebase Indexing**: Symbol graph navigation, fast semantic code search, and ChromaDB vector retrieval.
- **Developer Platform Integration**: Built-in Command Palette (`Ctrl+Shift+P`), AI Git Assistant, SQLite Database IDE, and terminal integration.

---

## 🛠️ Quick Start

### 1. Prerequisites
- **Python**: 3.10 or higher
- **Node.js**: 18.0 or higher

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/logeshn554/ai_coding_assistant.git
cd ai_coding_assistant

# Setup Virtual Environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt

# Configure Environment
cp .env.example .env

# Run Backend Server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
```bash
# Open a new terminal
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` or [https://loopix-five.vercel.app/](https://loopix-five.vercel.app/) to launch the Loopix IDE.

---

## ⚡ Dynamic Extension System

Loopix features a VS Code-style extension host system:
1. Open the **Extensions Sidebar** in Loopix.
2. Search and install extensions from the Open VSX registry or upload a `.vsix` package.
3. Installed extensions automatically register their contributed commands in the **Command Palette (`Ctrl+Shift+P`)** and expose AI tools directly to the assistant.

---

## 🔒 Security Architecture

Loopix operates under the core principle: **The LLM model is never trusted to make security decisions. The runtime engine enforces all security boundaries.**

- **Path Traversal Protection**: Canonical realpath verification prevents escaping workspace bounds.
- **Secret Redaction**: Automatic scrubbing of API keys, JWTs, and tokens in output logs.
- **Terminal Execution Limits**: Subprocess execution isolation with optional interactive prompt confirmation for high-risk commands.

For more details, see [SECURITY.md](SECURITY.md).

---

## 🧪 Testing & Quality Assurance

Run the comprehensive Python test suite:
```bash
pytest tests/
```

Run frontend build and type checks:
```bash
cd frontend
npm run build
```

---

## 📖 Documentation

Additional technical documentation is available in the [`docs/`](docs/) directory:
- [System Architecture](docs/ARCHITECTURE.md)
- [Agent Engine Specifications](docs/agent-system.md)
- [Coding Standards](docs/CODING_STANDARDS.md)
- [Event System Protocol](docs/EVENTS.md)

---

## 🤝 Contributing

Contributions are welcome! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) guide before submitting a Pull Request.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).