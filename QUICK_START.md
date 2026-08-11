# 🚀 AI Coding Agent - 60 Second Quick Start

## Setup (First Time Only)

```powershell
# 1. Set your Anthropic API key
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"

# 2. Install dependency
pip install anthropic

# 3. Run the agent
python coding_agent.py
```

## Usage

Just tell it what you want:

```
👤 You: create a Flask REST API for a todo app
👤 You: add user authentication
👤 You: add database migrations
```

## What It Does

✅ **Creates actual files** - not descriptions  
✅ **Complete working code** - no placeholders  
✅ **Only what you ask for** - no unwanted files  

## Example

```
👤 You: create a Python script to rename files in bulk

🔧 Executing operations...
   ✓ Created file: file_renamer.py
   ✓ Created file: requirements.txt

💬 Created a CLI tool for bulk file renaming with pattern matching
```

## Need Help?

- **Full Guide**: See `AGENT_GUIDE.md`
- **Startup Script**: Run `.\start_agent.ps1`
- **Test It**: Run `python test_agent.py`

## Common Issues

**"API key not set"** → `$env:ANTHROPIC_API_KEY = "your-key"`  
**"File exists"** → Ask agent to "update" instead of "create"  
**Unwanted files** → Tell it "no research or planning files"

---

That's it! Just run `python coding_agent.py` and start building.
