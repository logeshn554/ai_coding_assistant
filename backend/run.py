import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Run server on localhost:8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
