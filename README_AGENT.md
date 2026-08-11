# AI Coding Agent - Quick Start Guide

A practical AI coding assistant that creates files and projects based on your requests.

## Setup (2 minutes)

### 1. Install Dependencies
```bash
pip install -r requirements_agent.txt
```

### 2. Set Your API Key
Get your API key from: https://console.anthropic.com/

**Windows PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY = "your-api-key-here"
```

**Linux/Mac:**
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

### Interactive Mode (Recommended)
```bash
python coding_agent.py
```

Then just tell it what you want:
```
👤 You: create a simple Flask web app with a home page
👤 You: add a user authentication system
👤 You: create a REST API for blog posts
```

### Single Command Mode
```bash
python coding_agent.py "create a React app with routing"
```

### Custom Workspace
```bash
# Set workspace directory
$env:AGENT_WORKSPACE = "C:\projects\myapp"
python coding_agent.py
```

## Features

✅ **Creates actual files** - not just descriptions  
✅ **Complete working code** - not placeholder comments  
✅ **Shows progress** - see what's being created in real-time  
✅ **No unwanted files** - doesn't create research.md or planning files  
✅ **Conversation memory** - remembers context from previous messages  

## Example Session

```
🤖 AI CODING AGENT - Interactive Mode

👤 You: create a Python CLI tool for file encryption

🤖 Agent received: create a Python CLI tool for file encryption

🔧 Executing operations...

   Creating main CLI application
   ✓ Created file: encrypt_tool.py
   Creating requirements file
   ✓ Created file: requirements.txt
   Creating README
   ✓ Created file: README.md

💬 I've created a Python CLI tool for file encryption with:
- encrypt_tool.py: Main application with encrypt/decrypt commands
- requirements.txt: Required dependencies (cryptography)
- README.md: Usage instructions

You can run it with: python encrypt_tool.py --help
```

## What It Does Well

1. **Project Creation**: "create a Django blog app" → creates full project structure
2. **File Generation**: "add a database schema" → creates migration files
3. **Code Writing**: "create a user authentication module" → complete working code
4. **Updates**: "add error handling to the login function" → updates existing files

## What It Doesn't Do

❌ Create planning/research documents unless you ask  
❌ Just describe code without creating files  
❌ Create incomplete placeholder code  

## Troubleshooting

**"ANTHROPIC_API_KEY environment variable not set"**
- Set the environment variable as shown in Setup step 2

**"File already exists"**
- The agent won't overwrite existing files with create_file
- Ask it to "update" or "edit" instead

**Agent not creating files**
- Make sure you have write permissions in the workspace directory
- Check that the API key is valid

## Tips

💡 Be specific: "create a Flask REST API with SQLite database"  
💡 Break complex projects into steps: First ask for the structure, then add features  
💡 Review created files before running: Always check generated code  
💡 Use version control: Commit before using the agent so you can revert if needed  

## Safety

⚠️ **Always review generated code before running it**  
⚠️ **Use in a test directory first**  
⚠️ **Keep backups of important files**  

The agent creates real files with real code. Treat it like any code generation tool - review before executing.
