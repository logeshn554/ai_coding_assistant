from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from pathlib import Path
import json

router = APIRouter()

class UpdatePromptRequest(BaseModel):
    agent_name: str
    prompt: str

class CreateAgentRequest(BaseModel):
    name: str
    role: str
    tier: str
    icon: str = "Bot"
    color: str = "cyan"
    system_prompt: str = "You are a specialized custom agent."
    prompt_template: str = "Process task: {task_description}"

DEFAULT_AGENTS_METADATA = [
    { "name": "Planner Agent", "role": "Master task planner & dependency graph", "tier": "Planning", "icon": "Sparkles", "color": "violet" },
    { "name": "Frontend Planner Agent", "role": "UI architecture, components, design system", "tier": "Planning", "icon": "Layers", "color": "violet" },
    { "name": "Backend Planner Agent", "role": "API structure, DB schema, auth strategy", "tier": "Planning", "icon": "Package", "color": "violet" },
    { "name": "Requirement Analysis Agent", "role": "Identifies target files & requirements", "tier": "Planning", "icon": "Search", "color": "violet" },
    { "name": "Software Architect Agent", "role": "Folder structure, patterns, event flows", "tier": "Architecture", "icon": "Cpu", "color": "blue" },
    { "name": "File System Agent", "role": "Reads workspace files for other agents", "tier": "Development", "icon": "FileText", "color": "cyan" },
    { "name": "Coding Agent", "role": "General-purpose file modifications", "tier": "Development", "icon": "Code2", "color": "cyan" },
    { "name": "Frontend Developer Agent", "role": "React/TS UI, components, hooks, SEO", "tier": "Development", "icon": "Globe", "color": "cyan" },
    { "name": "Backend Developer Agent", "role": "REST APIs, auth, services, middleware", "tier": "Development", "icon": "Bot", "color": "cyan" },
    { "name": "Database Agent", "role": "Schema, migrations, indexes, seed data", "tier": "Development", "icon": "Database", "color": "cyan" },
    { "name": "API Agent", "role": "OpenAPI 3.0, validation, rate limiting", "tier": "Development", "icon": "Network", "color": "cyan" },
    { "name": "Integration Agent", "role": "Frontend↔Backend↔DB integration checks", "tier": "QA", "icon": "Layers", "color": "amber" },
    { "name": "Testing Agent", "role": "Unit, integration & E2E test suites", "tier": "QA", "icon": "TestTube", "color": "amber" },
    { "name": "Debugging Agent", "role": "Log analysis, bug detection & fixes", "tier": "QA", "icon": "Bug", "color": "amber" },
    { "name": "Security Agent", "role": "OWASP Top 10, XSS, CSRF, JWT, RBAC", "tier": "QA", "icon": "Shield", "color": "amber" },
    { "name": "Performance Agent", "role": "Bundles, N+1 queries, caching, memory", "tier": "QA", "icon": "Zap", "color": "amber" },
    { "name": "Code Review Agent", "role": "Code quality, naming, architecture", "tier": "QA", "icon": "Beaker", "color": "amber" },
    { "name": "AI Reviewer Agent", "role": "Staff Engineer: algorithms, tech debt", "tier": "QA", "icon": "Sparkles", "color": "amber" },
    { "name": "Documentation Agent", "role": "README, API docs, developer guide", "tier": "Operations", "icon": "FileText", "color": "emerald" },
    { "name": "Git Agent", "role": "Git status, diff summaries, changelogs", "tier": "Operations", "icon": "GitBranch", "color": "emerald" },
    { "name": "Terminal Agent", "role": "Runs builds, tests, migrations, Docker", "tier": "Operations", "icon": "Terminal", "color": "emerald" },
    { "name": "DevOps Agent", "role": "Dockerfile, CI/CD, NGINX, monitoring", "tier": "Operations", "icon": "Rocket", "color": "emerald" },
    { "name": "Release Agent", "role": "Semver, release notes, rollback plan", "tier": "Operations", "icon": "Package", "color": "emerald" },
]

def get_custom_agents_file_path() -> Path:
    return Path.home() / ".devpilot" / "custom_agents.json"

@router.get("/api/agents/modes")
async def get_agent_modes():
    """Returns definitions and capabilities for all 8 universal DevPilot agent modes."""
    return {
        "modes": [
            { "mode": "Ask", "description": "Read-only project context and technical Q&A", "read_only": True },
            { "mode": "Plan", "description": "Structured implementation planning without modifying files", "read_only": True },
            { "mode": "Assist", "description": "Interactive coding assistance and targeted edit suggestions", "read_only": False },
            { "mode": "Code", "description": "Full feature implementation and code generation", "read_only": False },
            { "mode": "Debug", "description": "Runtime log analysis, stack trace inspection, and root-cause repair", "read_only": False },
            { "mode": "Review", "description": "Independent security, correctness, and architecture code review", "read_only": True },
            { "mode": "Architect", "description": "System design, API boundaries, and migration planning", "read_only": True },
            { "mode": "Autonomous", "description": "End-to-end multi-step autonomous execution with verification & self-repair", "read_only": False },
        ]
    }

@router.get("/api/agents")
async def get_agents():
    custom_agents_path = get_custom_agents_file_path()
    agents = list(DEFAULT_AGENTS_METADATA)
    
    if custom_agents_path.exists():
        try:
            with open(custom_agents_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_agents = data.get("custom_agents", [])
                for a in custom_agents:
                    agents.append({
                        "name": a["name"],
                        "role": a["role"],
                        "tier": a["tier"],
                        "icon": a.get("icon", "Bot"),
                        "color": a.get("color", "cyan"),
                        "is_custom": True
                    })
        except Exception:
            pass
            
    return agents

@router.post("/api/agents")
async def create_agent(req: CreateAgentRequest):
    custom_agents_path = get_custom_agents_file_path()
    
    data = {}
    if custom_agents_path.exists():
        try:
            with open(custom_agents_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
            
    if "custom_agents" not in data:
        data["custom_agents"] = []
        
    # Check if agent already exists
    all_names = {a["name"] for a in DEFAULT_AGENTS_METADATA} | {a["name"] for a in data["custom_agents"]}
    if req.name in all_names:
        raise HTTPException(status_code=400, detail=f"Agent with name '{req.name}' already exists.")
        
    new_agent = {
        "name": req.name,
        "role": req.role,
        "tier": req.tier,
        "icon": req.icon,
        "color": req.color,
        "system_prompt": req.system_prompt,
        "prompt_template": req.prompt_template
    }
    
    data["custom_agents"].append(new_agent)
    
    try:
        custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
        with open(custom_agents_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save new agent: {e}")
        
    return {"status": "ok", "message": f"Agent '{req.name}' created successfully.", "agent": new_agent}

@router.get("/api/agents/prompts")
async def get_agent_prompts():
    from ..orchestrator import (
        planner_prompt_template,
        frontend_planner_prompt_template,
        backend_planner_prompt_template,
        requirement_prompt_template,
        architect_prompt_template,
        coding_prompt_template,
        frontend_dev_prompt_template,
        backend_dev_prompt_template,
        database_prompt_template,
        api_agent_prompt_template,
        integration_prompt_template,
        security_prompt_template,
        performance_prompt_template,
        review_prompt_template,
        ai_reviewer_prompt_template,
        documentation_prompt_template,
        terminal_prompt_template,
        devops_prompt_template,
        release_prompt_template,
        orchestrator_prompt_template,
    )
    
    templates = {
        "Planner Agent": planner_prompt_template,
        "Frontend Planner Agent": frontend_planner_prompt_template,
        "Backend Planner Agent": backend_planner_prompt_template,
        "Requirement Analysis Agent": requirement_prompt_template,
        "Software Architect Agent": architect_prompt_template,
        "Coding Agent": coding_prompt_template,
        "Frontend Developer Agent": frontend_dev_prompt_template,
        "Backend Developer Agent": backend_dev_prompt_template,
        "Database Agent": database_prompt_template,
        "API Agent": api_agent_prompt_template,
        "Integration Agent": integration_prompt_template,
        "Security Agent": security_prompt_template,
        "Performance Agent": performance_prompt_template,
        "Code Review Agent": review_prompt_template,
        "AI Reviewer Agent": ai_reviewer_prompt_template,
        "Documentation Agent": documentation_prompt_template,
        "Terminal Agent": terminal_prompt_template,
        "DevOps Agent": devops_prompt_template,
        "Release Agent": release_prompt_template,
        "Orchestrator Agent": orchestrator_prompt_template,
    }
    
    prompts = {}
    for name, tmpl in templates.items():
        prompts[name] = getattr(tmpl, "template", "")
        
    prompts["File System Agent"] = "deterministic_worker"
    prompts["Testing Agent"] = "deterministic_worker"
    prompts["Git Agent"] = "deterministic_worker"
    
    # Merge custom agents and prompt overrides
    custom_agents_path = get_custom_agents_file_path()
    if custom_agents_path.exists():
        try:
            with open(custom_agents_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                prompt_overrides = data.get("prompt_overrides", {})
                for name, prompt_str in prompt_overrides.items():
                    if name in prompts:
                        prompts[name] = prompt_str
                custom_agents = data.get("custom_agents", [])
                for agent_info in custom_agents:
                    prompts[agent_info["name"]] = agent_info.get("prompt_template", "")
        except Exception:
            pass
            
    return prompts

@router.post("/api/agents/prompts")
async def update_agent_prompt(req: UpdatePromptRequest):
    from ..orchestrator import (
        planner_prompt_template,
        frontend_planner_prompt_template,
        backend_planner_prompt_template,
        requirement_prompt_template,
        architect_prompt_template,
        coding_prompt_template,
        frontend_dev_prompt_template,
        backend_dev_prompt_template,
        database_prompt_template,
        api_agent_prompt_template,
        integration_prompt_template,
        security_prompt_template,
        performance_prompt_template,
        review_prompt_template,
        ai_reviewer_prompt_template,
        documentation_prompt_template,
        terminal_prompt_template,
        devops_prompt_template,
        release_prompt_template,
        orchestrator_prompt_template,
    )
    
    templates = {
        "Planner Agent": planner_prompt_template,
        "Frontend Planner Agent": frontend_planner_prompt_template,
        "Backend Planner Agent": backend_planner_prompt_template,
        "Requirement Analysis Agent": requirement_prompt_template,
        "Software Architect Agent": architect_prompt_template,
        "Coding Agent": coding_prompt_template,
        "Frontend Developer Agent": frontend_dev_prompt_template,
        "Backend Developer Agent": backend_dev_prompt_template,
        "Database Agent": database_prompt_template,
        "API Agent": api_agent_prompt_template,
        "Integration Agent": integration_prompt_template,
        "Security Agent": security_prompt_template,
        "Performance Agent": performance_prompt_template,
        "Code Review Agent": review_prompt_template,
        "AI Reviewer Agent": ai_reviewer_prompt_template,
        "Documentation Agent": documentation_prompt_template,
        "Terminal Agent": terminal_prompt_template,
        "DevOps Agent": devops_prompt_template,
        "Release Agent": release_prompt_template,
        "Orchestrator Agent": orchestrator_prompt_template,
    }
    
    custom_agents_path = get_custom_agents_file_path()
    
    data = {}
    if custom_agents_path.exists():
        try:
            with open(custom_agents_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
            
    if "prompt_overrides" not in data:
        data["prompt_overrides"] = {}
    if "custom_agents" not in data:
        data["custom_agents"] = []
        
    if req.agent_name in templates:
        templates[req.agent_name].template = req.prompt
        data["prompt_overrides"][req.agent_name] = req.prompt
    else:
        # Check if it is a custom agent
        custom_agent = next((a for a in data["custom_agents"] if a["name"] == req.agent_name), None)
        if not custom_agent:
            raise HTTPException(status_code=400, detail=f"Agent '{req.agent_name}' not found.")
        custom_agent["prompt_template"] = req.prompt
        
    try:
        custom_agents_path.parent.mkdir(parents=True, exist_ok=True)
        with open(custom_agents_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save updated prompt: {e}")
        
    return {"status": "ok", "message": f"Prompt for '{req.agent_name}' updated successfully."}
