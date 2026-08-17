import os
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..state import workspace_state

router = APIRouter()

class QueryExecuteRequest(BaseModel):
    db_path: str | None = "loopix.db"
    sql: str

@router.get("/api/database/tables")
def get_database_tables(db_path: str | None = "loopix.db"):
    """Lists tables and schema information for a SQLite database."""
    target_db = db_path
    if not os.path.isabs(target_db) and workspace_state.root:
        target_db = os.path.join(workspace_state.root, db_path)

    if not os.path.exists(target_db):
        return {"db_path": target_db, "exists": False, "tables": []}

    try:
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        table_schemas = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info('{table}');")
            columns = [{"id": col[0], "name": col[1], "type": col[2], "notnull": col[3], "pk": col[5]} for col in cursor.fetchall()]
            table_schemas[table] = columns

        conn.close()
        return {
            "db_path": target_db,
            "exists": True,
            "tables": tables,
            "schemas": table_schemas
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/database/execute")
def execute_query(req: QueryExecuteRequest):
    """Executes a SQL query safely and returns tabular results or EXPLAIN QUERY PLAN."""
    target_db = req.db_path or "loopix.db"
    if not os.path.isabs(target_db) and workspace_state.root:
        target_db = os.path.join(workspace_state.root, target_db)

    if not os.path.exists(target_db):
        raise HTTPException(status_code=404, detail=f"Database file not found at {target_db}")

    # Guard against destructive DROP DATABASE commands without permission
    sql_lower = req.sql.strip().lower()
    if sql_lower.startswith("drop database") or sql_lower.startswith("drop schema"):
        raise HTTPException(status_code=403, detail="Destructive database operations require explicit authorization.")

    try:
        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(req.sql)
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            rows = [dict(row) for row in cursor.fetchmany(100)]
            conn.close()
            return {"success": True, "columns": columns, "rows": rows, "row_count": len(rows)}
        else:
            conn.commit()
            conn.close()
            return {"success": True, "columns": [], "rows": [], "affected_rows": cursor.rowcount}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
