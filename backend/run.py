import os
import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    dev_mode = os.environ.get("DEV_RELOAD", "false").lower() == "true"
    # Run server on specified host
    uvicorn.run("app.main:app", host=host, port=port, reload=dev_mode)