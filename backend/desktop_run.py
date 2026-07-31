import sys
import os
import threading
import time
import socket
import webview
import subprocess
import json
import urllib.request

# Ensure project root is in sys.path and set as current working directory
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(backend_dir)
os.chdir(project_root)
sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)

import uvicorn

class DesktopAPI:
    def __init__(self, window=None):
        self._window = window

    def select_folder(self):
        """
        Opens a native folder dialog and returns the path.
        """
        if not self._window:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            # Return normalized path with forward slashes for cross-platform compatibility in the frontend
            return os.path.abspath(result[0]).replace("\\", "/")
        return None


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def is_backend_ready(port):
    try:
        url = f"http://127.0.0.1:{port}/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_frontend_built():
    dist_index = os.path.join(project_root, "frontend", "dist", "index.html")
    if not os.path.exists(dist_index):
        print("Frontend dist/index.html not found. Building frontend production bundle...")
        frontend_dir = os.path.join(project_root, "frontend")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        try:
            subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir, check=True)
            print("Frontend build completed successfully.")
        except Exception as e:
            print(f"Warning: Failed to build frontend automatically: {e}")

def start_server(port):
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    ensure_frontend_built()

    # Find a free port dynamically
    port = get_free_port()
    
    # Start FastAPI server thread
    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()
    
    # Poll HTTP health endpoint until backend is fully ready
    print(f"Waiting for backend HTTP server readiness on http://127.0.0.1:{port}/...")
    start_time = time.time()
    while time.time() - start_time < 20:
        if is_backend_ready(port):
            print("Backend HTTP server is online and responding.")
            break
        time.sleep(0.3)

    # Define and initialize API
    api = DesktopAPI()
    
    # Create the pywebview desktop window
    window = webview.create_window(
        title="DevPilot AI Editor",
        url=f"http://127.0.0.1:{port}/",
        js_api=api,
        width=1280,
        height=800,
        min_size=(1000, 600)
    )
    api._window = window
    
    # Run pywebview loop with Edge Chromium on Windows if available
    gui_engine = "edgechromium" if sys.platform == "win32" else None
    try:
        webview.start(gui=gui_engine, debug=True)
    except Exception:
        webview.start(debug=True)