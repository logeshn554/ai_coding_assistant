import os
import sys
import time
import socket
import subprocess
import webbrowser
import signal
def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def get_python_executable():
    # Resolve local virtual env python executable
    if sys.platform == "win32":
        venv_py = os.path.join("venv", "Scripts", "python.exe")
    else:
        venv_py = os.path.join("venv", "bin", "python")
        
    if os.path.exists(venv_py):
        return venv_py
    return sys.executable

def main():
    print("Starting DevPilot Launcher...")
    
    # 1. Start FastAPI backend
    python_bin = get_python_executable()
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    print(f"Starting Backend via {python_bin}...")
    backend_proc = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        env=env
    )
    
    # 2. Start Vite dev server in frontend
    frontend_dir = os.path.join(os.getcwd(), "frontend")
    print("Starting Frontend (Vite) dev server...")
    if sys.platform == "win32":
        frontend_proc = subprocess.Popen(
            ["npm.cmd", "run", "dev"],
            cwd=frontend_dir
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