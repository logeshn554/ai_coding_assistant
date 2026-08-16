import sys
import os
import asyncio
import traceback
import json

# Setup import paths
workspace_root = r"e:\os kernel with ani\ai_coding_assistant"
sys.path.insert(0, workspace_root)
sys.path.insert(0, os.path.join(workspace_root, "backend"))
sys.path.insert(0, os.path.join(workspace_root, "backend", "app"))
sys.path.insert(0, os.path.join(workspace_root, "backend", "app", "agent"))

from backend.app.config import settings

# Force local development settings
settings.ENVIRONMENT = "development"
settings.MODE = "local"
settings.DATABASE_URL = "sqlite+aiosqlite:///devpilot.db"

# Mock Session class
class MockSession:
    def __init__(self, workspace_root):
        self.workspace_root = workspace_root
        self.pending_confirmations = {}
        self.audit = []
        self._knowledge_store = None
        self.last_mode = "Ask"
        self.permission_manager = None
        self.run_id = "test_run"
        self.workspace_id = "test_ws"
        self.network_mode = "NO_NETWORK"

    async def send_ws_message(self, msg):
        pass

    def log_audit(self, name, args, status, message):
        self.audit.append((name, args, status, message))

    async def _run_llm_query(self, system_prompt, prompt, agent_name="Router"):
        return '{"target": "dummy_content"}'

async def run_db_init():
    from backend.app.infrastructure.database.models import Base
    from backend.app.infrastructure.database.connection import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def test_tools():
    results = {}
    session = MockSession(workspace_root)
    from backend.app.tools.dispatcher import dispatch_tool

    # 1. list_directory
    try:
        print("  - Running list_directory...")
        res = await dispatch_tool(session, "tc_1", "list_directory", {"path": ""}, False)
        data = json.loads(res)
        if isinstance(data, list) and len(data) > 0:
            results["list_directory"] = ("PASS", f"Returned {len(data)} items.")
        else:
            results["list_directory"] = ("FAIL", f"Returned unexpected format: {res[:100]}")
    except Exception as e:
        results["list_directory"] = ("FAIL", str(e))

    # 2. read_file
    try:
        print("  - Running read_file...")
        res = await dispatch_tool(session, "tc_2", "read_file", {"path": "ARCHITECTURE.md"}, False)
        if "DevPilot" in res or len(res) > 50:
            results["read_file"] = ("PASS", f"Read ARCHITECTURE.md successfully ({len(res)} chars).")
        else:
            results["read_file"] = ("FAIL", f"Returned unexpected content: {res[:100]}")
    except Exception as e:
        results["read_file"] = ("FAIL", str(e))

    # 3. write_file
    try:
        print("  - Running write_file...")
        res = await dispatch_tool(session, "tc_3", "write_file", {"path": "_healthcheck/test.txt", "content": "healthcheck"}, True)
        if "Success" in res:
            results["write_file"] = ("PASS", "Successfully wrote temp file.")
        else:
            results["write_file"] = ("FAIL", res)
    except Exception as e:
        results["write_file"] = ("FAIL", str(e))

    # 4. edit_file
    try:
        print("  - Running edit_file...")
        res = await dispatch_tool(session, "tc_4", "edit_file", {
            "path": "_healthcheck/test.txt",
            "target": "healthcheck",
            "replacement": "healthcheck-edited"
        }, True)
        if "Success" in res:
            # Check content
            check = await dispatch_tool(session, "tc_4_check", "read_file", {"path": "_healthcheck/test.txt"}, False)
            if check.strip() == "healthcheck-edited":
                results["edit_file"] = ("PASS", "Successfully edited temp file and verified content.")
            else:
                results["edit_file"] = ("FAIL", f"Edited content did not match: '{check}'")
        else:
            results["edit_file"] = ("FAIL", res)
    except Exception as e:
        results["edit_file"] = ("FAIL", str(e))

    # 5. delete_file
    try:
        print("  - Running delete_file...")
        res = await dispatch_tool(session, "tc_5", "delete_file", {"path": "_healthcheck/test.txt"}, True)
        if "Success" in res:
            # Verify deletion
            if not os.path.exists(os.path.join(workspace_root, "_healthcheck", "test.txt")):
                results["delete_file"] = ("PASS", "Successfully deleted temp file.")
            else:
                results["delete_file"] = ("FAIL", "File still exists after deletion.")
        else:
            results["delete_file"] = ("FAIL", res)
    except Exception as e:
        results["delete_file"] = ("FAIL", str(e))

    # Cleanup directory
    try:
        os.rmdir(os.path.join(workspace_root, "_healthcheck"))
    except Exception:
        pass

    # 6. glob
    try:
        print("  - Running glob...")
        res = await dispatch_tool(session, "tc_6", "glob", {"pattern": "**/*.py"}, False)
        if "Found" in res:
            results["glob"] = ("PASS", f"Found matching files.")
        else:
            results["glob"] = ("FAIL", res)
    except Exception as e:
        results["glob"] = ("FAIL", str(e))

    # 7. search_codebase (grep)
    try:
        print("  - Running search_codebase...")
        res = await dispatch_tool(session, "tc_7", "search_codebase", {"query": "AgentSession"}, False)
        data = json.loads(res)
        if isinstance(data, list) and len(data) > 0:
            results["search_codebase"] = ("PASS", f"Found {len(data)} codebase references.")
        else:
            results["search_codebase"] = ("FAIL", f"Search returned: {res[:100]}")
    except Exception as e:
        results["search_codebase"] = ("FAIL", str(e))

    # 8. run_terminal_command
    try:
        print("  - Running run_terminal_command...")
        res = await dispatch_tool(session, "tc_8", "run_terminal_command", {"command": "echo healthcheck"}, True)
        if "healthcheck" in res.lower():
            results["run_terminal_command"] = ("PASS", "Successfully ran shell command and got output.")
        else:
            results["run_terminal_command"] = ("FAIL", f"Unexpected output: {res[:100]}")
    except Exception as e:
        results["run_terminal_command"] = ("FAIL", str(e))

    # 9. tool_normalization
    try:
        print("  - Running tool name normalization tests (control channel stripping)...")
        from backend.app.infrastructure.tool_registry import ToolRegistry
        tool_def = ToolRegistry.get_tool("read_file<|channel|>commentary")
        if not tool_def or tool_def.name != "read_file":
            raise ValueError(f"ToolRegistry.get_tool failed to normalize name, got {tool_def}")

        res = await dispatch_tool(session, "tc_norm_1", "read_file<|channel|>commentary", {"path": "ARCHITECTURE.md"}, False)
        if "DevPilot" in res or len(res) > 50:
            results["tool_normalization"] = ("PASS", "Successfully normalized dirty tool name and executed canonical read_file.")
        else:
            results["tool_normalization"] = ("FAIL", f"Expected read_file output, got: {res[:100]}")
    except Exception as e:
        results["tool_normalization"] = ("FAIL", str(e))

    return results

def test_intent_router():
    from backend.app.agent.intent_router import IntentRouter, IntentType
    router = IntentRouter()
    
    test_cases = [
        ("scaffold a fresh backend in django", IntentType.NEW_PROJECT),
        ("create a new react application from scratch", IntentType.NEW_PROJECT),
        ("implement spec in spec.md", IntentType.IMPLEMENT_SPEC),
        ("write code according to features.txt", IntentType.IMPLEMENT_SPEC),
        ("fix Typeerror in auth.py", IntentType.BUG_FIX),
        ("resolve traceback in routes.py", IntentType.BUG_FIX),
        ("refactor AuthService to simplify code", IntentType.REFACTOR),
        ("restructure app to decouple routes", IntentType.REFACTOR),
        ("explain how validate_token works", IntentType.EXPLAIN),
        ("resume last task", IntentType.CONTINUE),
        ("grep for authenticate in codebase", IntentType.SEARCH),
        ("security audit of secure_fs.py", IntentType.REVIEW),
    ]
    
    results = {}
    for idx, (query, expected) in enumerate(test_cases, 1):
        try:
            res = router.classify(query)
            if res.intent == expected:
                results[f"case_{idx}"] = ("PASS", f"Query '{query}' classified correctly as {expected.value}.")
            else:
                results[f"case_{idx}"] = ("FAIL", f"Query '{query}' classified as {res.intent.value} instead of {expected.value}.")
        except Exception as e:
            results[f"case_{idx}"] = ("FAIL", str(e))
            
    return results

def test_slash_commands():
    from backend.app.agent.intent_router import IntentRouter, IntentType
    router = IntentRouter()
    results = {}
    
    # /goal
    try:
        res = router.classify("/goal implement tests")
        # routes to GENERAL as fallback since there is no special regex for /goal
        if res.intent == IntentType.GENERAL:
            results["/goal"] = ("PASS", f"Parsed /goal correctly as GENERAL fallback.")
        else:
            results["/goal"] = ("FAIL", f"Expected GENERAL for /goal, got {res.intent.value}")
    except Exception as e:
        results["/goal"] = ("FAIL", str(e))

    # /grill-me
    try:
        res = router.classify("/grill-me auth flow")
        # routes to GENERAL as fallback
        if res.intent == IntentType.GENERAL:
            results["/grill-me"] = ("PASS", f"Parsed /grill-me correctly as GENERAL fallback.")
        else:
            results["/grill-me"] = ("FAIL", f"Expected GENERAL for /grill-me, got {res.intent.value}")
    except Exception as e:
        results["/grill-me"] = ("FAIL", str(e))

    # /learn
    try:
        res = router.classify("/learn coding styles")
        # routes to REVIEW
        if res.intent == IntentType.REVIEW:
            results["/learn"] = ("PASS", f"Parsed /learn correctly as REVIEW.")
        else:
            results["/learn"] = ("FAIL", f"Expected REVIEW for /learn, got {res.intent.value}")
    except Exception as e:
        results["/learn"] = ("FAIL", str(e))
        
    return results

def test_agent_registry():
    from parallel_agent_system.agents import AGENT_REGISTRY
    results = {}
    for name, agent_cls in AGENT_REGISTRY.items():
        try:
            # Check class name and type
            if agent_cls and hasattr(agent_cls, "__name__"):
                results[name] = ("PASS", f"Loaded agent class {agent_cls.__name__} successfully.")
            else:
                results[name] = ("FAIL", "Invalid class type in registry.")
        except Exception as e:
            results[name] = ("FAIL", str(e))
    return results

async def test_context_engine():
    from backend.app.agent.context_engine import ContextEngine, WorkspaceContext, EditorContext, Position, GitContext
    results = {}
    try:
        engine = ContextEngine.get_instance(workspace_root)
        engine._index_sync()
        
        editor = EditorContext(
            active_file="backend/app/session/agent_session.py",
            cursor=Position(line=10, column=5),
            selected_text="class AgentSession",
            diagnostics=[]
        )
        git = GitContext(branch="main", modified_files=[])
        
        ctx = await engine.build_context(
            task_description="Explain AgentSession class structure",
            workspace=WorkspaceContext(workspace_root=workspace_root),
            editor=editor,
            git=git
        )
        if ctx and len(ctx.items) > 0:
            results["build_context"] = ("PASS", f"Successfully assembled context package. Total items: {len(ctx.items)}. Estimated tokens: {ctx.total_tokens_estimate}")
        else:
            results["build_context"] = ("FAIL", "Context assembly returned empty context.")
    except Exception as e:
        results["build_context"] = ("FAIL", str(traceback.format_exc()))
    return results

async def test_mode_routing():
    from backend.app.session.agent_session import AgentSession
    results = {}
    try:
        session = AgentSession(
            workspace_root=workspace_root,
            active_profile={},
            send_to_client=lambda msg: None,
            permission_manager=None,
            session_id="test_mode_session"
        )
        
        # Check tools for Ask mode
        ask_tools = session._get_tools_for_mode("Ask")
        # Check tools for Plan mode
        plan_tools = session._get_tools_for_mode("Plan")
        # Check tools for Agent mode
        agent_tools = session._get_tools_for_mode("Agent")
        # Check tools for Goal mode
        goal_tools = session._get_tools_for_mode("Goal")
        
        results["mode_tools"] = ("PASS", f"Ask: {len(ask_tools)} tools, Plan: {len(plan_tools)} tools, Agent: {len(agent_tools)} tools, Goal: {len(goal_tools)} tools.")
        
        # Check system prompt rendering for each mode
        ask_prompt = session._get_system_prompt("Ask")
        plan_prompt = session._get_system_prompt("Plan")
        agent_prompt = session._get_system_prompt("Agent")
        
        if "OPERATING MODE: Ask" in ask_prompt and "OPERATING MODE: Plan" in plan_prompt and "OPERATING MODE: Agent" in agent_prompt:
            results["mode_prompts"] = ("PASS", "System prompts rendered correctly with appropriate operating mode labels.")
        else:
            results["mode_prompts"] = ("FAIL", "System prompt operating mode label rendering was incorrect.")
            
    except Exception as e:
        results["mode_routing"] = ("FAIL", str(traceback.format_exc()))
    return results

async def main():
    print("="*60)
    print("      DEVPILOT SYSTEM HEALTH DIAGNOSTIC AUDIT RUNNER")
    print("="*60)
    
    print("\n[DB] Initializing database tables...")
    await run_db_init()
    print("[DB] Initialized successfully.")
    
    print("\n[Phase 1] Executing Tool Health Check...")
    tool_results = await test_tools()
    
    print("\n[Phase 2] Executing Intent Router Check...")
    intent_results = test_intent_router()
    
    print("\n[Phase 3] Executing Slash Command Routing Check...")
    slash_results = test_slash_commands()
    
    print("\n[Phase 4] Executing Agent Registry Integration Check...")
    agent_results = test_agent_registry()
    
    print("\n[Phase 5] Executing Context Engine Signal Strength Check...")
    ctx_results = await test_context_engine()
    
    print("\n[Phase 6] Executing Mode Routing Check...")
    mode_results = await test_mode_routing()
    
    # Save a JSON file with full results
    full_report = {
        "tools": tool_results,
        "intent_router": intent_results,
        "slash_commands": slash_results,
        "agents": agent_results,
        "context_engine": ctx_results,
        "mode_routing": mode_results
    }
    
    with open("healthcheck_results.json", "w") as f:
        json.dump(full_report, f, indent=2)
        
    print("\n" + "="*60)
    print("                      SUMMARY REPORT")
    print("="*60)
    
    all_categories = [
        ("File & Terminal Tools", tool_results),
        ("Intent Router Classification", intent_results),
        ("Slash Command Routing", slash_results),
        ("Agent Registry Integration", agent_results),
        ("Context Engine Signal Strength", ctx_results),
        ("Mode Routing", mode_results)
    ]
    
    grand_passed = 0
    grand_failed = 0
    
    for category_name, cat_results in all_categories:
        print(f"\n--- {category_name} ---")
        passed = sum(1 for status, _ in cat_results.values() if status == "PASS")
        failed = sum(1 for status, _ in cat_results.values() if status == "FAIL")
        grand_passed += passed
        grand_failed += failed
        
        for name, (status, desc) in cat_results.items():
            icon = "✅ PASS" if status == "PASS" else "❌ FAIL"
            print(f"  {icon} | {name}: {desc}")
            
    print("\n" + "="*60)
    print(f"OVERALL SUMMARY: {grand_passed} passed, {grand_failed} failed.")
    print("="*60)
    
    if grand_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
