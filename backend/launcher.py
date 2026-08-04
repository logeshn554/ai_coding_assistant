import os
import sys
import time
import socket
import subprocess
import webbrowser
import signal
def is_port_open(port):
    # Try both IPv4 (127.0.0.1) and localhost (IPv4/IPv6)
    for host in ('127.0.0.1', 'localhost'):
        try:
            with socket.create_connection((host, port), timeout=0.2) as s:
                return True
        except Exception:
            continue
    return False

def kill_process_on_port(port):
    # Guard: port must be a valid integer in range 1-65535 before interpolation
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise ValueError(f"Invalid port number: {port!r}")
    try:
        if sys.platform == "win32":
            # The netstat | findstr pipeline genuinely needs a shell (pipe operator).
            # The port is validated as a safe integer above, so interpolation is safe.
            out = subprocess.check_output(
                f"netstat -ano | findstr :{port}", shell=True
            ).decode()
            pids = set()
            for line in out.strip().split("\n"):
                if "LISTENING" in line or "ESTABLISHED" in line:
                    parts = line.strip().split()
                    if parts and parts[-1].isdigit():
                        pids.add(parts[-1])
            for pid in pids:
                if pid != "0":
                    # List-form: no shell interpretation of pid
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
        else:
            out = subprocess.check_output(
                ["lsof", "-t", f"-i:{port}"]
            ).decode()
            for pid in out.strip().split("\n"):
                if pid.strip().isdigit():
                    subprocess.run(
                        ["kill", "-9", pid.strip()],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
    except Exception:
        pass

def get_python_executable():
    # Resolve local virtual env python executable
    if sys.platform == "win32":
        venv_py = os.path.join("venv", "Scripts", "python.exe")
    else:
        venv_py = os.path.join("venv", "bin", "python")
        
    if os.path.exists(venv_py):
        return os.path.abspath(venv_py)
    return sys.executable

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    print("Starting DevPilot Launcher...")
    
    # Pre-clean ports to avoid address-in-use crashes
    print("Checking ports 8000 and 5173 for lingering instances...")
    kill_process_on_port(8000)
    kill_process_on_port(5173)
    
    # 1. Start FastAPI backend
    python_bin = get_python_executable()
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root
    
    # Try to load session token so it matches between backends
    from pathlib import Path
    token_file = Path.home() / ".devpilot" / "session_token.txt"
    session_token = "devpilot-session-token-change-me"
    if token_file.is_file():
        try:
            session_token = token_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    env["SESSION_TOKEN"] = session_token
    
    print(f"Starting Backend via {python_bin}...")
    backend_dir = os.path.join(project_root, "backend")
    backend_proc = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        env=env,
        cwd=backend_dir
    )
    
    # 2. Start Vite dev server in frontend
    frontend_dir = os.path.join(os.getcwd(), "frontend")
    print("Starting Frontend (Vite) dev server...")
    if sys.platform == "win32":
        frontend_proc = subprocess.Popen(
            "npm run dev",
            cwd=frontend_dir,
            shell=True
        )
    else:
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir
        )
        
    # Graceful shutdown handler
    def cleanup(signum=None, frame=None):
        print("\nShutting down launcher...")
        try:
            frontend_proc.terminate()
            backend_proc.terminate()
        except Exception:
            pass
        try:
            frontend_proc.wait(timeout=2)
            backend_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                frontend_proc.kill()
                backend_proc.kill()
            except Exception:
                pass
        print("Launcher shutdown complete.")
        sys.exit(0)
        
    # Wire signals
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Wait for ports to be ready
    print("Waiting for ports 8000 and 5173 to be ready...")
    backend_ready = False
    frontend_ready = False
    
    # Max wait time 30s
    start_time = time.time()
    while time.time() - start_time < 30:
        if not backend_ready:
            backend_ready = is_port_open(8000)
        if not frontend_ready:
            frontend_ready = is_port_open(5173)
            
        if backend_ready and frontend_ready:
            break
            
        # Check if either process died unexpectedly
        if backend_proc.poll() is not None:
            print("Error: Backend process exited prematurely.")
            cleanup()
        if frontend_proc.poll() is not None:
            print("Error: Frontend process exited prematurely.")
            cleanup()
            
        time.sleep(0.5)
        
    if backend_ready and frontend_ready:
        print("Both backend and frontend are ready! Opening browser...")
        webbrowser.open("http://localhost:5173")
    else:
        print("Warning: Timed out waiting for servers to start. Check logs above.")
        
    # Keep launcher alive
    try:
        while True:
            # Check processes periodically
            if backend_proc.poll() is not None or frontend_proc.poll() is not None:
                cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()