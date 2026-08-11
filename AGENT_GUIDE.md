# AI Coding Agent - Complete Guide

## 🎯 What This Agent Does

This is a **practical coding assistant** that:
- ✅ **Creates actual files** when you ask for them
- ✅ **Writes complete working code** (not placeholders)
- ✅ **Shows you what it's doing** in real-time
- ✅ **Doesn't create unwanted files** like research.md
- ✅ **Remembers conversation context** for follow-up requests

## 🚀 Quick Start (3 Steps)

### Step 1: Set API Key (One Time)
```powershell
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

Get your API key from: https://console.anthropic.com/

### Step 2: Install Dependencies (One Time)
```powershell
pip install -r requirements_agent.txt
```

### Step 3: Run the Agent
```powershell
# Option A: Use the startup script (recommended)
.\start_agent.ps1

# Option B: Run directly
python coding_agent.py
```

## 💡 How to Use It

### Interactive Mode (Best for Projects)

```powershell
python coding_agent.py
```

Then have a conversation:

```
👤 You: create a Flask REST API for a todo app

🤖 Agent: [Creates app.py, models.py, requirements.txt]

👤 You: add user authentication

🤖 Agent: [Updates app.py, creates auth.py]

👤 You: add database migrations

🤖 Agent: [Creates migrations folder, alembic config]
```

### Single Command Mode (Quick Tasks)

```powershell
python coding_agent.py "create a Python script to rename files in bulk"
```

## 📋 Example Requests

### Web Development
```
"create a Flask app with user registration and login"
"create a React component for a todo list"
"add a REST API endpoint for creating blog posts"
```

### Scripts & Tools
```
"create a Python script to batch rename image files"
"create a CLI tool for file encryption"
"make a script to backup database daily"
```

### Project Scaffolding
```
"create a Django project with authentication"
"set up a FastAPI app with SQLAlchemy"
"create a Node.js Express server with MongoDB"
```

### Code Addition
```
"add error handling to the login function"
"add unit tests for the user model"
"add logging to all API endpoints"
```

## ✅ What It Does Right

### 1. Creates Actual Files
❌ **Broken Agent**: Just describes what to do  
✅ **This Agent**: Actually creates the files

### 2. Complete Code
❌ **Broken Agent**: `# TODO: Add implementation here`  
✅ **This Agent**: Full working code

### 3. No Unwanted Files
❌ **Broken Agent**: Creates research.md, planning.md, notes.md  
✅ **This Agent**: Only creates what you ask for

### 4. Clear Progress
❌ **Broken Agent**: Silent, no feedback  
✅ **This Agent**: Shows each file being created

### 5. Follow-up Requests
❌ **Broken Agent**: Forgets context  
✅ **This Agent**: Remembers previous files and conversations

## 🔧 Advanced Usage

### Custom Workspace Directory
```powershell
$env:AGENT_WORKSPACE = "C:\projects\my-new-app"
python coding_agent.py
```

### Test Before Using on Real Projects
```powershell
# Run the test suite
python test_agent.py

# This creates test_agent_output/ directory
# Review the files to see what the agent creates
```

### Iterative Development
```
👤 You: create a simple calculator app

[Review the files]

👤 You: add a GUI with tkinter

[Review the updates]

👤 You: add unit tests

[Done!]
```

## 🛡️ Safety & Best Practices

### Always Review Generated Code
```powershell
# Before running generated code, review it
# The agent writes to disk immediately
```

### Use Version Control
```powershell
# Commit your work before using the agent
git commit -am "Before agent changes"

# Use the agent
python coding_agent.py

# Review changes
git diff

# Keep or revert
git checkout .  # Revert if needed
```

### Start in a Test Directory
```powershell
# Create a test directory first
mkdir test-agent-work
cd test-agent-work

# Run agent
python ..\coding_agent.py
```

### Break Large Projects into Steps
```
❌ Bad: "create a complete e-commerce platform"

✅ Good:
  Step 1: "create a Flask app with product listing"
  Step 2: "add shopping cart functionality"
  Step 3: "add user authentication"
  Step 4: "add checkout and payments"
```

## 🐛 Troubleshooting

### "ANTHROPIC_API_KEY environment variable not set"
```powershell
# Set the key
$env:ANTHROPIC_API_KEY = "your-key-here"

# Verify it's set
$env:ANTHROPIC_API_KEY
```

### "File already exists" Error
The agent won't overwrite with `create_file`. Instead, say:
```
👤 You: update app.py to add error handling
# Or
👤 You: replace app.py with a version that has logging
```

### Agent Not Creating Files
1. Check write permissions in the directory
2. Check API key is valid
3. Try running in a fresh directory
4. Run test: `python test_agent.py`

### Agent Creates Unwanted Files
If it creates research.md or planning files, explicitly tell it:
```
👤 You: create a Flask app
      Do NOT create any research or planning files
      Only create actual code files
```

### Code Has Bugs
```
👤 You: the login function has a bug with password validation
      Fix it to check for minimum length
```

## 📊 Features Comparison

| Feature | Old/Broken Agent | This Agent |
|---------|------------------|------------|
| Creates files | ❌ No | ✅ Yes |
| Complete code | ❌ Placeholders | ✅ Working code |
| Unwanted files | ❌ research.md | ✅ Only requested |
| Progress visible | ❌ Silent | ✅ Clear output |
| Context memory | ❌ Forgets | ✅ Remembers |
| Error handling | ❌ Crashes | ✅ Shows errors |
| Interactive mode | ❌ No | ✅ Yes |

## 🎓 Tips for Best Results

### 1. Be Specific
❌ "create a web app"  
✅ "create a Flask REST API with user authentication and SQLite database"

### 2. Mention Technology Stack
❌ "create a blog"  
✅ "create a Django blog with PostgreSQL and Bootstrap"

### 3. Specify What NOT to Create
✅ "create a React app - only code files, no documentation"

### 4. Use Follow-up Requests
```
👤 You: create a calculator app
👤 You: now add scientific functions
👤 You: add a GUI
👤 You: add keyboard shortcuts
```

### 5. Ask for Specific Patterns
✅ "use the factory pattern for database connections"  
✅ "follow REST API best practices"  
✅ "use async/await for all database calls"

## 📚 Example Session

```
PS E:\projects> python coding_agent.py

🤖 AI CODING AGENT - Interactive Mode

👤 You: create a Python CLI tool for converting images to different formats

🤖 Agent received: create a Python CLI tool for converting images to different formats

🔧 Executing operations...

   Creating image converter CLI tool
   ✓ Created file: image_converter.py
   Creating requirements file with Pillow dependency
   ✓ Created file: requirements.txt
   Creating usage documentation
   ✓ Created file: README.md

💬 I've created a Python CLI tool for image format conversion:

- image_converter.py: Main CLI application using click and Pillow
  Supports: JPG, PNG, GIF, BMP, WebP
  Usage: python image_converter.py input.jpg output.png

- requirements.txt: Pillow and click dependencies

- README.md: Installation and usage instructions

You can install dependencies with: pip install -r requirements.txt

👤 You: add batch conversion for entire directories

🤖 Agent received: add batch conversion for entire directories

🔧 Executing operations...

   Updating image_converter.py with batch processing
   ✓ Wrote file: image_converter.py

💬 I've updated the tool to support batch conversion:

New features:
- Process entire directories with --batch flag
- Preserve directory structure
- Progress bar for multiple files
- Error handling for invalid images

Usage: python image_converter.py --batch input_dir/ output_dir/ --format png

👤 You: quit

👋 Goodbye!
```

## 🎯 Project Examples

### Simple Script (2 minutes)
```
👤 You: create a Python script that watches a folder and
       automatically organizes files by extension
```
**Creates**: file_organizer.py, requirements.txt

### Medium Project (10 minutes)
```
👤 You: create a Flask REST API for a task manager with
       SQLite database, CRUD operations, and simple auth
```
**Creates**: app.py, models.py, auth.py, database.py, requirements.txt

### Complex Project (Iterative, 30+ minutes)
```
Step 1: create a FastAPI app with user management
Step 2: add JWT authentication  
Step 3: add PostgreSQL database with SQLAlchemy
Step 4: add API endpoints for blog posts
Step 5: add unit tests with pytest
Step 6: add Docker configuration
```

## 🚦 Status Indicators

When the agent runs, you'll see:
- 🤖 = Agent received your request
- 🔧 = Executing file operations  
- ✓ = Operation succeeded
- ✗ = Operation failed
- 💬 = Agent response message

## 🆘 Getting Help

If something doesn't work:

1. **Check the test**: `python test_agent.py`
2. **Check API key**: `$env:ANTHROPIC_API_KEY`
3. **Check permissions**: Can you create files in the directory?
4. **Try a simple request**: "create a hello.py file that prints hello world"

## 📝 Summary

This agent is designed to be **practical and reliable**:
- ✅ It creates files when you ask
- ✅ It writes real, working code
- ✅ It doesn't create junk files
- ✅ It shows what it's doing
- ✅ It works interactively or with single commands

**Just tell it what you want to build, and it will create it.**

---

Need help? Check README_AGENT.md for quick reference.
