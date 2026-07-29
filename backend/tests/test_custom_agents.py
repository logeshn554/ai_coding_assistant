import os
import sys
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app, SESSION_TOKEN
from app.routes.agents import get_custom_agents_file_path

@pytest.fixture
def auth_client():
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {SESSION_TOKEN}"})
    return client

@pytest.fixture(autouse=True)
def clean_custom_agents_file():
    """Fixture to ensure a clean custom_agents.json file before and after tests."""
    file_path = get_custom_agents_file_path()
    # Back up existing file if any
    backup_path = file_path.with_suffix(".json.testbak")
    has_backup = False
    if file_path.exists():
        file_path.rename(backup_path)
        has_backup = True
        
    yield
    
    # Clean up test output
    if file_path.exists():
        file_path.unlink()
        
    # Restore original file
    if has_backup:
        backup_path.rename(file_path)

def test_get_agents_initial(auth_client):
    res = auth_client.get("/api/agents")
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) > 0
    # Must contain default agents like Planner Agent
    planner = next((a for a in agents if a["name"] == "Planner Agent"), None)
    assert planner is not None
    assert planner["tier"] == "Planning"
    assert "is_custom" not in planner or not planner["is_custom"]

def test_create_and_get_custom_agent(auth_client):
    # Create new custom agent
    payload = {
        "name": "Security Expert Agent",
        "role": "Performs penetration testing and security reviews",
        "tier": "QA",
        "icon": "Shield",
        "color": "amber",
        "system_prompt": "You are a master security hacker.",
        "prompt_template": "Analyze: {task_description}"
    }
    res = auth_client.post("/api/agents", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["agent"]["name"] == "Security Expert Agent"
    
    # Get all agents, verify new one exists
    res = auth_client.get("/api/agents")
    assert res.status_code == 200
    agents = res.json()
    custom_agent = next((a for a in agents if a["name"] == "Security Expert Agent"), None)
    assert custom_agent is not None
    assert custom_agent["tier"] == "QA"
    assert custom_agent.get("is_custom") is True

def test_prompt_endpoints(auth_client):
    # Get all initial prompts
    res = auth_client.get("/api/agents/prompts")
    assert res.status_code == 200
    prompts = res.json()
    assert "Planner Agent" in prompts
    original_planner_prompt = prompts["Planner Agent"]
    
    # Update Planner Agent prompt (default agent override)
    new_prompt = "You are a new customized Planner."
    res = auth_client.post("/api/agents/prompts", json={"agent_name": "Planner Agent", "prompt": new_prompt})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    
    # Verify the update works and returns from GET
    res = auth_client.get("/api/agents/prompts")
    assert res.status_code == 200
    updated_prompts = res.json()
    assert updated_prompts["Planner Agent"] == new_prompt
    
    # Register a custom agent
    payload = {
        "name": "Audit Agent",
        "role": "Audits database performance",
        "tier": "QA",
        "prompt_template": "Audit database: {task_description}"
    }
    auth_client.post("/api/agents", json=payload)
    
    # Update custom agent prompt
    new_custom_prompt = "Optimized audit instructions: {task_description}"
    res = auth_client.post("/api/agents/prompts", json={"agent_name": "Audit Agent", "prompt": new_custom_prompt})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    
    # Verify GET returns custom agent prompt
    res = auth_client.get("/api/agents/prompts")
    assert res.status_code == 200
    assert res.json()["Audit Agent"] == new_custom_prompt


@pytest.mark.asyncio
async def test_rag_codebase_retrieval(tmp_path):
    from app.orchestrator import async_get_codebase_dict
    
    workspace = tmp_path
    src_dir = workspace / "src"
    src_dir.mkdir()
    (src_dir / "auth.py").write_text("def auth(): pass", encoding="utf-8")
    (src_dir / "database.py").write_text("def db(): pass", encoding="utf-8")
    (workspace / "requirements.txt").write_text("pytest\nfastapi", encoding="utf-8")
    
    # 1. Test when target_files is provided
    res = await async_get_codebase_dict(str(workspace), target_files=["src/auth.py"])
    assert "src/auth.py" in res
    assert "src/database.py" not in res
    assert res["src/auth.py"] == "def auth(): pass"
    
    # 2. Test when task_description matches keywords
    res2 = await async_get_codebase_dict(str(workspace), task_description="database connection logic")
    assert "src/database.py" in res2
