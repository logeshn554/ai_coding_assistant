"""Source-level verification tests for second-audit bug fixes."""
import sys, asyncio, tempfile, pathlib, importlib.util
BASE = pathlib.Path(__file__).resolve().parent.parent.parent
def read(p): return (BASE / p).read_text(encoding="utf-8")

def test_c1_terminal_tool():
    src = read("backend/app/tools/terminal_tool.py")
    if "taskkill" in src:
        assert "shell=True" not in src.split("taskkill")[1]
    print("PASS C-1 terminal_tool.py")

def test_c1_utils():
    src = read("backend/app/utils.py")
    assert "taskkill /F /T /PID {" not in src
    print("PASS C-1 utils.py")

def test_c1_launcher():
    spec = importlib.util.spec_from_file_location("launcher", BASE / "backend/launcher.py")
    lnch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lnch)
    for bad in [-1, 70000, "evil"]:
        try:
            lnch.kill_process_on_port(bad)
            assert False, "Bad port not rejected: " + str(bad)
        except ValueError:
            pass
    print("PASS C-1 launcher port guard")

def test_c3_dap():
    src = read("backend/app/routes/debug.py")
    assert "threading.Lock" in src
    assert "_read_loop" in src
    assert "initialize" in src
    print("PASS C-3 DAPClient threaded")

def test_c4_banner():
    src = read("frontend/src/components/ExtensionsSidebar.tsx")
    assert "Preview" in src and "does not yet activate" in src
    print("PASS C-4 preview banner")

def test_c5_cost():
    src = read("backend/app/session/agent_session.py")
    assert "DEVPILOT_HARD_COST_LIMIT" not in src and "cost_confirmation_request" not in src
    print("PASS C-5 hard cost ceiling removed")

def test_h3_eviction():
    src = read("backend/app/rag.py")
    assert "_evict_old_chroma_indexes" in src and "shutil.rmtree" in src
    assert "_evict_old_chroma_indexes" in read("backend/app/main.py")
    print("PASS H-3 ChromaDB eviction")

def test_m1_ripgrep():
    src = read("backend/app/routes/health.py")
    assert "ripgrep_available" in src and "shutil.which" in src
    print("PASS M-1 ripgrep health")

def test_h4_deploy():
    spec = importlib.util.spec_from_file_location("dep", BASE / "backend/app/deployment.py")
    dep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dep)
    cases = [("requirements.txt", "Railway"), ("package.json", "Vercel"), ("Dockerfile", "Docker")]
    for fname, expected in cases:
        with tempfile.TemporaryDirectory() as td:
            pathlib.Path(td, fname).write_text("x")
            r = asyncio.run(dep.generate_deploy_command(td))
            assert r["platform"] == expected, f"{fname} -> {r[chr(112)+chr(108)+chr(97)+chr(116)+chr(102)+chr(111)+chr(114)+chr(109)]}"
    print("PASS H-4 deploy commands")

def test_missing5_git():
    src = read("backend/app/routes/git.py")
    for needle in ["_VALID_BRANCH_RE", "VALID_BRANCH_RE.match", "/api/git/branches", "/api/git/branch/create", "/api/git/push"]:
        assert needle in src, "Missing: " + needle
    print("PASS MISSING-5 git branch endpoints")

def test_m2_electron():
    src = read("electron/main.js")
    assert "setApplicationMenu" in src and "toggleDevTools" in src
    print("PASS M-2 electron native menu")

if __name__ == "__main__":
    tests = [test_c1_terminal_tool, test_c1_utils, test_c1_launcher, test_c3_dap,
             test_c4_banner, test_c5_cost, test_h3_eviction, test_m1_ripgrep,
             test_h4_deploy, test_missing5_git, test_m2_electron]
    failed = 0
    for t in tests:
        try: t()
        except Exception as e:
            print("FAIL " + t.__name__ + ": " + str(e))
            failed += 1
    if failed: print(str(failed) + " FAILED"); sys.exit(1)
    else: print("ALL " + str(len(tests)) + " PASSED")
