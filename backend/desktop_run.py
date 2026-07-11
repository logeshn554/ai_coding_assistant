import sys
import os
import threading
import time
import socket
import webview

# Add the backend folder to python path so it can import app.main
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

def start_server(port):
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    # We find a free port dynamically so there's no conflict with existing processes
    port = get_free_port()
    
    # Start FastAPI server thread
    t = threading.Thread(target=start_server, args=(port,), daemon=True)
    t.start()
    
    # Wait a bit for uvicorn to bind and start
    time.sleep(1.0)
    
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
    
    # Run pywebview loop
    webview.start()
