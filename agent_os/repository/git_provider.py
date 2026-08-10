import subprocess
import os
from agent_os.repository.interfaces import ISourceControl

class GitSourceControl(ISourceControl):
    """Git tracking operations runner."""
    def __init__(self, workspace_root: str = "") -> None:
        self.workspace_root = workspace_root

    def get_diff(self) -> str:
        try:
            cwd = self.workspace_root if self.workspace_root else None
            # Run git diff for unstaged and staged changes
            res = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True,
                text=True,
                cwd=cwd,
                check=True
            )
            return res.stdout
        except Exception as e:
            return f"Error executing git diff: {e}"

    def commit_changes(self, message: str) -> str:
        try:
            cwd = self.workspace_root if self.workspace_root else None
            # Stage all changes
            subprocess.run(["git", "add", "."], cwd=cwd, check=True)
            # Commit changes
            res = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                cwd=cwd,
                check=True
            )
            return res.stdout
        except subprocess.CalledProcessError as cpe:
            return f"Commit failed or no changes to commit: {cpe.stderr or cpe.stdout}"
        except Exception as e:
            return f"Error executing git commit: {e}"
