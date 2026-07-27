import os
import sys
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.state import workspace_state
from app.workspace_graph import (
    build_workspace_graph,
    get_or_generate_node_summary,
    categorize_node,
    extract_database_models,
    parse_python_imports
)


def test_python_ast_imports():
    content = """
import os
import sys as system
from pathlib import Path, PurePath
from . import db
from ..routes import graph_route
from app.services import (
    UserService,
    AuthService
)
"""
    imports = parse_python_imports(content)
    mod_names = [m[0] for m in imports]
    levels = [m[1] for m in imports]

    assert "os" in mod_names
    assert "sys" in mod_names
    assert "pathlib" in mod_names
    assert "" in mod_names or "db" in mod_names  # relative level 1 import
    assert 1 in levels  # level 1 relative import
    assert 2 in levels  # level 2 relative import
    assert "app.services" in mod_names


def test_content_based_categorization():
    # 1. Database model
    py_db = """
from sqlalchemy import Column, Integer, String
from app.db import Base

class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String)
"""
    cat, db_info = categorize_node("app/models.py", py_db)
    assert cat == "database"
    assert db_info is not None
    assert db_info["tables"][0]["table_name"] == "users"
    assert "id" in db_info["tables"][0]["fields"]
    assert "username" in db_info["tables"][0]["fields"]

    # 2. React Hook
    ts_hook = """
import { useState, useEffect } from 'react';

export function useAuthToken() {
    const [token, setToken] = useState(null);
    useEffect(() => {
        setToken("abc");
    }, []);
    return token;
}
"""
    cat_hook, _ = categorize_node("src/hooks/useAuthToken.ts", ts_hook)
    assert cat_hook == "hook"

    # 3. API Route
    py_api = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/api/users")
async def get_users():
    return []
"""
    cat_api, _ = categorize_node("app/routes/users.py", py_api)
    assert cat_api == "api"

    # 4. Service class
    py_service = """
class AccountService:
    async def process_payment(self, amount):
        pass
"""
    cat_srv, _ = categorize_node("app/services/account.py", py_service)
    assert cat_srv == "service"

    # 5. React Component
    tsx_comp = """
import React from 'react';
export const UserCard: React.FC = () => {
    return <div className="card">User</div>;
};
"""
    cat_comp, _ = categorize_node("src/components/UserCard.tsx", tsx_comp)
    assert cat_comp == "component"


def test_js_ts_path_aliases_and_ast_graph(tmp_path):
    root = tmp_path / "app_repo"
    root.mkdir()

    # Create tsconfig with path alias
    tsconfig = root / "tsconfig.json"
    tsconfig.write_text(json.dumps({
        "compilerOptions": {
            "baseUrl": ".",
            "paths": {
                "@/*": ["src/*"]
            }
        }
    }))

    src_dir = root / "src"
    src_dir.mkdir()
    comp_dir = src_dir / "components"
    comp_dir.mkdir()

    btn = comp_dir / "Button.tsx"
    btn.write_text("import React from 'react'; export const Button = () => <button>Click</button>;")

    main = src_dir / "Main.tsx"
    main.write_text("import React from 'react'; import { Button } from '@/components/Button'; export const Main = () => <Button />;")

    graph = build_workspace_graph(str(root))
    assert len(graph["nodes"]) >= 2
    assert "summary" in graph
    assert graph["summary"]["total_nodes"] >= 2

    # Verify edge between Main.tsx and Button.tsx resolved via @/ alias
    main_node = next((n for n in graph["nodes"] if n["label"] == "Main.tsx"), None)
    btn_node = next((n for n in graph["nodes"] if n["label"] == "Button.tsx"), None)
    assert main_node is not None
    assert btn_node is not None

    edge = next((e for e in graph["edges"] if e["source"] == main_node["id"] and e["target"] == btn_node["id"]), None)
    assert edge is not None, "Edge between Main.tsx and Button.tsx via path alias should be found"


def test_explicit_truncation_metadata(tmp_path):
    root = tmp_path / "large_repo"
    root.mkdir()

    # Create 301 dummy files
    for i in range(301):
        f = root / f"f_{i}.py"
        f.write_text("x = 1\n")

    graph = build_workspace_graph(str(root))
    assert graph["summary"]["total_nodes"] == 300
    assert graph["summary"]["total_files_found"] == 301
    assert graph["summary"]["truncated"] is True
    assert graph["truncated"] is True
    assert graph["total_files_found"] == 301


@pytest.mark.asyncio
async def test_node_summary_caching(tmp_path):
    root = tmp_path / "summary_repo"
    root.mkdir()

    file_a = root / "service.py"
    file_a.write_text("class PaymentService:\n    async def process(self):\n        pass\n")

    graph = build_workspace_graph(str(root))
    node_a = graph["nodes"][0]

    # First call - generates and caches summary
    res1 = await get_or_generate_node_summary(str(root), node_a["id"])
    assert "summary" in res1
    assert res1["cached"] is False

    # Check cache file exists
    cache_file = root / ".devpilot" / "graph_cache.json"
    assert cache_file.exists()

    # Second call - should hit cache
    res2 = await get_or_generate_node_summary(str(root), node_a["id"])
    assert res2["cached"] is True
    assert res2["summary"] == res1["summary"]

    # Modify file - invalidates cache
    file_a.write_text("class PaymentService:\n    async def refund(self):\n        pass\n")
    res3 = await get_or_generate_node_summary(str(root), node_a["id"])
    assert res3["cached"] is False


def test_graph_api_endpoints(tmp_path):
    root = tmp_path / "api_repo"
    root.mkdir()
    f = root / "main.py"
    f.write_text("import os\n")

    workspace_state.root = str(root)
    client = TestClient(app)

    res = client.get("/api/workspace/graph")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    assert "summary" in data
    assert data["summary"]["total_nodes"] == 1

    # Test summary endpoint for node_0
    res_sum = client.get("/api/workspace/graph/summary/node_0")
    assert res_sum.status_code == 200
    sum_data = res_sum.json()
    assert "summary" in sum_data
    assert "cached" in sum_data
