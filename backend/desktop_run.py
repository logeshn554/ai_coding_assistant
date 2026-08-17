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
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running in PyInstaller bundle
    project_root = sys._MEIPASS
    backend_dir = os.path.join(project_root, "backend")
else:
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(backend_dir)

os.environ.setdefault("MODE", "desktop")
os.environ.setdefault("ENVIRONMENT", "desktop")
os.environ.setdefault("ALLOW_DEGRADED_REDIS", "true")
os.environ.setdefault("USE_SANDBOX", "false")

os.chdir(project_root)
sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(backend_dir, "app", "agent"))

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


import webbrowser

def get_free_port():
    # Prioritize standard Loopix port 8000, then fallback alternatives
    for preferred_port in [8000, 8080, 62746, 8088]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', preferred_port))
            s.close()
            return preferred_port
        except Exception:
            continue
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
    if getattr(sys, 'frozen', False):
        return
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
    try:
        from backend.app.main import app
    except ImportError:
        from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    ensure_frontend_built()

    # Find a free port dynamically (prioritizing 8000)
    port = get_free_port()
    app_url = f"http://127.0.0.1:{port}/"
    
    # Start FastAPI server thread
    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()
    
    # Poll HTTP health endpoint until backend is fully ready
    print(f"Waiting for backend HTTP server readiness on {app_url}...")
    start_time = time.time()
    backend_online = False
    while time.time() - start_time < 20:
        if is_backend_ready(port):
            print(f"Backend HTTP server is online and responding at {app_url}")
            backend_online = True
            break
        time.sleep(0.3)

    if not backend_online:
        print(f"Warning: Backend health check timed out. Attempting to continue anyway...")

    # Define and initialize API
    api = DesktopAPI()
    
    # Try launching PyWebView window
    webview_launched = False
    try:
        window = webview.create_window(
            title="Loopix AI Editor",
            url=app_url,
            js_api=api,
            width=1280,
            height=800,
            min_size=(1000, 600)
        )
        api._window = window
        
        gui_engine = "edgechromium" if sys.platform == "win32" else None
        try:
            webview.start(gui=gui_engine, debug=False)
            webview_launched = True
        except Exception as e:
            print(f"PyWebView edgechromium failed: {e}. Trying default GUI engine...")
            try:
                webview.start(debug=False)
                webview_launched = True
            except Exception as e2:
                print(f"PyWebView default engine failed: {e2}")
    except Exception as e:
        print(f"PyWebView window creation error: {e}")

    # If PyWebView couldn't open, fallback to opening default web browser and keeping the server alive
    if not webview_launched:
        print(f"Opening Loopix in your default browser at {app_url}...")
        webbrowser.open(app_url)
        print("Loopix server is running. Press Ctrl+C in this terminal to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down Loopix...")