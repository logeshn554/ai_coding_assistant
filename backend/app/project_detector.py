import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("devpilot.project_detector")

def detect_project_metadata(workspace_root: str) -> Dict[str, Any]:
    """
    Analyzes the workspace root directory, detects tech stack, framework, language, 
    package manager, and infers default install, run, build, and test commands.
    Returns metadata dict and saves to .devpilot/project.json.
    """
    if not workspace_root or not os.path.isdir(workspace_root):
        return {
            "projectId": "default",
            "name": "Untitled Workspace",
            "framework": "Plain Project",
            "language": "General",
            "packageManager": "system",
            "installCommand": "",
            "runCommand": "",
            "buildCommand": "",
            "testCommand": "",
            "workspace": workspace_root,
        }

    root_path = Path(workspace_root)
    proj_name = root_path.name or "DevPilot Project"

    metadata: Dict[str, Any] = {
        "projectId": f"proj_{abs(hash(workspace_root))}",
        "name": proj_name,
        "framework": "Generic Workspace",
        "language": "Text/Code",
        "packageManager": "npm",
        "installCommand": "",
        "runCommand": "",
        "buildCommand": "",
        "testCommand": "",
        "workspace": workspace_root,
    }

    # 1. Check package.json (Node.js / Web / Game / Desktop)
    pkg_json_path = root_path / "package.json"
    if pkg_json_path.exists():
        try:
            with open(pkg_json_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            
            pkg_name = data.get("name")
            if pkg_name:
                metadata["name"] = pkg_name

            scripts = data.get("scripts", {})
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

            # Detect package manager lockfile
            if (root_path / "pnpm-lock.yaml").exists():
                pkg_mgr = "pnpm"
            elif (root_path / "yarn.lock").exists():
                pkg_mgr = "yarn"
            elif (root_path / "bun.lockb").exists() or (root_path / "bun.lock").exists():
                pkg_mgr = "bun"
            else:
                pkg_mgr = "npm"

            metadata["packageManager"] = pkg_mgr
            run_prefix = f"{pkg_mgr} run" if pkg_mgr in ("npm", "pnpm") else pkg_mgr

            # Framework detection
            if "next" in deps:
                metadata["framework"] = "Next.js"
            elif "vite" in deps and "react" in deps:
                metadata["framework"] = "React + Vite"
            elif "vite" in deps and "vue" in deps:
                metadata["framework"] = "Vue + Vite"
            elif "vite" in deps:
                metadata["framework"] = "Vite"
            elif "react" in deps and "phaser" in deps:
                metadata["framework"] = "React + Phaser Game"
            elif "phaser" in deps:
                metadata["framework"] = "Phaser Game"
            elif "three" in deps:
                metadata["framework"] = "Three.js 3D"
            elif "react" in deps:
                metadata["framework"] = "React"
            elif "vue" in deps:
                metadata["framework"] = "Vue.js"
            elif "express" in deps or "@nestjs/core" in deps:
                metadata["framework"] = "Node.js Server"
            else:
                metadata["framework"] = "Node.js Application"

            metadata["language"] = "TypeScript" if (root_path / "tsconfig.json").exists() or "typescript" in deps else "JavaScript"

            # Commands
            metadata["installCommand"] = f"{pkg_mgr} install"
            
            if "dev" in scripts:
                metadata["runCommand"] = f"{run_prefix} dev"
            elif "start" in scripts:
                metadata["runCommand"] = f"{run_prefix} start"
            elif "serve" in scripts:
                metadata["runCommand"] = f"{run_prefix} serve"

            if "build" in scripts:
                metadata["buildCommand"] = f"{run_prefix} build"
            if "test" in scripts:
                metadata["testCommand"] = f"{run_prefix} test"

        except Exception as e:
            logger.error(f"Error parsing package.json: {e}")

    # 2. Check Python projects
    elif (root_path / "requirements.txt").exists() or (root_path / "pyproject.toml").exists() or any(root_path.glob("*.py")):
        metadata["packageManager"] = "pip"
        metadata["language"] = "Python"
        metadata["installCommand"] = "pip install -r requirements.txt" if (root_path / "requirements.txt").exists() else "pip install ."

        # Check for FastAPI / Flask / Django / Streamlit
        req_content = ""
        if (root_path / "requirements.txt").exists():
            try:
                with open(root_path / "requirements.txt", "r", encoding="utf-8", errors="ignore") as f:
                    req_content = f.read().lower()
            except Exception:
                pass

        if "fastapi" in req_content or (root_path / "main.py").exists() and "fastapi" in open(root_path / "main.py", errors="ignore").read().lower():
            metadata["framework"] = "FastAPI"
            metadata["runCommand"] = "uvicorn main:app --reload"
        elif "flask" in req_content:
            metadata["framework"] = "Flask"
            metadata["runCommand"] = "python main.py"
        elif "streamlit" in req_content:
            metadata["framework"] = "Streamlit"
            metadata["runCommand"] = "streamlit run app.py"
        elif "pygame" in req_content:
            metadata["framework"] = "Pygame"
            metadata["runCommand"] = "python main.py"
        elif (root_path / "main.py").exists():
            metadata["framework"] = "Python Application"
            metadata["runCommand"] = "python main.py"
        elif (root_path / "app.py").exists():
            metadata["framework"] = "Python Application"
            metadata["runCommand"] = "python app.py"
        else:
            metadata["framework"] = "Python Script"
            metadata["runCommand"] = "python main.py"

        metadata["testCommand"] = "pytest"

    # 3. Check Rust projects
    elif (root_path / "Cargo.toml").exists():
        metadata["framework"] = "Rust Project"
        metadata["language"] = "Rust"
        metadata["packageManager"] = "cargo"
        metadata["installCommand"] = "cargo check"
        metadata["runCommand"] = "cargo run"
        metadata["buildCommand"] = "cargo build"
        metadata["testCommand"] = "cargo test"

    # 4. Check Go projects
    elif (root_path / "go.mod").exists():
        metadata["framework"] = "Go Application"
        metadata["language"] = "Go"
        metadata["packageManager"] = "go"
        metadata["installCommand"] = "go mod download"
        metadata["runCommand"] = "go run ."
        metadata["buildCommand"] = "go build ."
        metadata["testCommand"] = "go test ./..."

    # 5. Check Godot Engine
    elif (root_path / "project.godot").exists():
        metadata["framework"] = "Godot Engine Game"
        metadata["language"] = "GDScript / C#"
        metadata["packageManager"] = "godot"
        metadata["runCommand"] = "godot --path ."

    # 6. Check Unity
    elif (root_path / "ProjectSettings").exists() or (root_path / "Assets").exists():
        metadata["framework"] = "Unity Game Engine"
        metadata["language"] = "C#"
        metadata["packageManager"] = "unity"
        metadata["runCommand"] = "Unity Editor"

    # 7. Check Unreal Engine
    elif list(root_path.glob("*.uproject")):
        metadata["framework"] = "Unreal Engine"
        metadata["language"] = "C++ / Blueprints"
        metadata["packageManager"] = "unreal"
        metadata["runCommand"] = "UnrealEditor"

    # Save metadata to .devpilot/project.json
    try:
        devpilot_dir = root_path / ".devpilot"
        devpilot_dir.mkdir(exist_ok=True)
        meta_file = devpilot_dir / "project.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write .devpilot/project.json: {e}")

    return metadata
