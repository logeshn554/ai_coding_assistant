import json
import os

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
SNIPPETS_FILE_PATH = os.path.expanduser("~/.devpilot/snippets.json")

class SnippetItem(BaseModel):
    id: str
    title: str
    language: str
    code: str
    description: str | None = ""

def _get_snippets() -> list[dict]:
    os.makedirs(os.path.dirname(SNIPPETS_FILE_PATH), exist_ok=True)
    if os.path.exists(SNIPPETS_FILE_PATH):
        try:
            with open(SNIPPETS_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    defaults = [
        {
            "id": "snip_1",
            "title": "FastAPI Async Route Template",
            "language": "python",
            "code": "@router.get(\"/api/example\")\nasync def example_endpoint():\n    return {\"status\": \"ok\", \"data\": []}",
            "description": "Standard async FastAPI route handler"
        },
        {
            "id": "snip_2",
            "title": "React Component with Hooks",
            "language": "typescript",
            "code": "import React, { useState, useEffect } from 'react';\n\nexport const MyComponent: React.FC = () => {\n  const [state, setState] = useState(null);\n  return (\n    <div className=\"p-4 bg-zinc-900 text-white rounded-lg\">\n      <span>My Component</span>\n    </div>\n  );\n};",
            "description": "Clean functional React component snippet"
        },
        {
            "id": "snip_3",
            "title": "Try-Catch Async Wrapper",
            "language": "javascript",
            "code": "try {\n  const response = await fetch(url);\n  const data = await response.json();\n} catch (error) {\n  console.error('API Call Failed:', error);\n}",
            "description": "Safely fetch API endpoint with error handling"
        }
    ]
    with open(SNIPPETS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(defaults, f)
    return defaults

def _save_snippets(snippets: list[dict]):
    os.makedirs(os.path.dirname(SNIPPETS_FILE_PATH), exist_ok=True)
    with open(SNIPPETS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(snippets, f)

@router.get("/api/snippets")
def get_snippets():
    return {"snippets": _get_snippets()}

@router.post("/api/snippets")
def save_snippet(item: SnippetItem):
    snippets = _get_snippets()
    snippets = [s for s in snippets if s["id"] != item.id]
    new_item = {
        "id": item.id,
        "title": item.title,
        "language": item.language,
        "code": item.code,
        "description": item.description or ""
    }
    snippets.append(new_item)
    _save_snippets(snippets)
    return {"success": True, "snippet": new_item}

@router.delete("/api/snippets/{snippet_id}")
def delete_snippet(snippet_id: str):
    snippets = _get_snippets()
    filtered = [s for s in snippets if s["id"] != snippet_id]
    _save_snippets(filtered)
    return {"success": True}
