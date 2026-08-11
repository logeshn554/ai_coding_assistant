# ⚠️ IMPORTANT: How to Use the Coding Agent

## The Issue You're Seeing

The screenshot shows **DevPilot IDE's built-in AI assistant** (top-right panel).
That's NOT the coding agent I built for you.

The DevPilot assistant only gives advice - it doesn't create files.

## The Solution: Use the Real Coding Agent

I built a **separate, working coding agent** called `coding_agent.py` that actually creates files.

### Step 1: Open PowerShell Terminal

In DevPilot IDE:
1. Click "Terminal" menu → "New Terminal"
2. Or press `` Ctrl+` ``

You should see a PowerShell terminal at the bottom of the screen.

### Step 2: Set Your API Key

In the terminal, run:
```powershell
$env:ANTHROPIC_API_KEY = "your-anthropic-api-key-here"
```

Get your key from: https://console.anthropic.com/

### Step 3: Install Dependency

```powershell
pip install anthropic
```

### Step 4: Run the Coding Agent

```powershell
python coding_agent.py
```

### Step 5: Give Your Request

When you see the prompt, type:
```
👤 You: create a Flask REST API for blog posts
```

### What Will Happen

```
🤖 Agent received: create a Flask REST API for blog posts

🔧 Executing operations...
   Creating main Flask application
   ✓ Created file: app.py
   Creating database models
   ✓ Created file: models.py
   Creating requirements file
   ✓ Created file: requirements.txt

💬 Created Flask REST API with:
- app.py: Main application with CRUD endpoints
- models.py: BlogPost model with SQLAlchemy
- requirements.txt: Flask, SQLAlchemy, flask-cors

The files are now in your workspace!
```

## Quick Visual Guide

```
┌────────────────────────────────────────────────────┐
│  DevPilot IDE Window                               │
│                                                     │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ Files Explorer   │  │ Editor Area          │  │
│  │                  │  │                      │  │
│  │                  │  │                      │  │
│  └──────────────────┘  └──────────────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │ > TERMINAL (Use this!)                       │ │
│  │                                              │ │
│  │ PS E:\...\ai_coding_assistant>               │ │
│  │ PS E:\...\ai_coding_assistant> python coding_agent.py
│  │                                              │ │
│  │ 👤 You: create a Flask REST API             │ │
│  │                                              │ │
│  └──────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘

❌ DON'T use the DevPilot AI Assistant panel (top-right)
✅ DO use the Terminal to run coding_agent.py
```

## Why This Is Better

| DevPilot Assistant | coding_agent.py |
|-------------------|-----------------|
| ❌ Just gives advice | ✅ Creates actual files |
| ❌ Summaries only | ✅ Complete working code |
| ❌ No file creation | ✅ Shows each file created |
| ❌ Vague next steps | ✅ Does it for you |

## Complete Example

```powershell
# 1. Open terminal in DevPilot IDE
# 2. Set API key
PS> $env:ANTHROPIC_API_KEY = "sk-ant-..."

# 3. Install
PS> pip install anthropic

# 4. Run agent
PS> python coding_agent.py

🤖 AI CODING AGENT - Interactive Mode
============================================================

👤 You: create a Flask REST API for blog posts

🤖 Agent received: create a Flask REST API for blog posts

🔧 Executing operations...

   Creating Flask application with blog post routes
   ✓ Created file: app.py
   Creating BlogPost database model
   ✓ Created file: models.py
   Creating database initialization
   ✓ Created file: database.py
   Creating requirements file
   ✓ Created file: requirements.txt
   Creating README with usage instructions
   ✓ Created file: README.md

💬 I've created a Flask REST API for blog posts with:

Files created:
- app.py: Main application with 5 endpoints
  * GET /api/posts - List all posts
  * GET /api/posts/<id> - Get single post
  * POST /api/posts - Create post
  * PUT /api/posts/<id> - Update post
  * DELETE /api/posts/<id> - Delete post

- models.py: BlogPost model (id, title, content, author, created_at)
- database.py: SQLAlchemy database setup
- requirements.txt: Flask, Flask-CORS, SQLAlchemy

To run:
1. pip install -r requirements.txt
2. python app.py

API will be available at http://localhost:5000

👤 You: add user authentication

[Agent will update the files with auth...]

👤 You: quit

👋 Goodbye!
```

## Still Not Working?

Run the test to see it in action:
```powershell
python test_agent.py
```

This creates a test_agent_output/ folder with sample files so you can see what the agent creates.

---

**Remember**: 
- ❌ Don't use the DevPilot AI Assistant panel
- ✅ Use the Terminal to run `python coding_agent.py`
