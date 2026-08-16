# Contributing to DevPilot AI Editor

Thank you for your interest in contributing to DevPilot! We welcome contributions from the community.

## Development Setup

### Prerequisites
- **Python**: 3.10+
- **Node.js**: 18+
- **npm** or **yarn**

### Quick Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/logeshn554/ai_coding_assistant.git
   cd ai_coding_assistant
   ```

2. **Backend Setup**:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   cd ..
   ```

4. **Environment Setup**:
   ```bash
   cp .env.example .env
   ```

---

## Running the Application

### Development Mode

- **Start Backend**:
  ```bash
  python -m uvicorn backend.app.main:app --reload
  ```

- **Start Frontend**:
  ```bash
  cd frontend
  npm run dev
  ```

---

## Testing & Verification

Before submitting a pull request, please ensure all backend and frontend tests pass:

- **Backend Tests**:
  ```bash
  pytest
  ```

- **Frontend Build & Lint**:
  ```bash
  cd frontend
  npm run build
  ```

---

## Code Style & Conventions

- **Python**: Follow PEP 8 guidelines. Use type annotations where appropriate.
- **TypeScript / React**: Use functional components, strict TypeScript typing, and Tailwind / CSS classes consistent with DevPilot design tokens.

---

## License

By contributing to DevPilot, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
