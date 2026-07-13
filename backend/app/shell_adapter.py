import sys
import os
import subprocess

class ShellAdapter:
    """
    Abstracts shell execution command arguments and names across platforms.
    """
    @staticmethod
    def get_shell_name() -> str:
        if sys.platform == "win32":
            return "PowerShell"
        return "Bash"

    @staticmethod
    def get_shell_executable(interactive: bool = False) -> list:
        if sys.platform == "win32":
            if interactive:
                # Interactive terminal shell
                return ["powershell.exe", "-NoLogo", "-NoProfile"]
            else:
                # Running individual commands
                return ["powershell.exe", "-NoLogo", "-NonInteractive", "-Command"]
        else:
            shell_path = os.environ.get("SHELL") or "/bin/bash"
            if interactive:
                return [shell_path, "-i"]
            else:
                return [shell_path, "-c"]

    @staticmethod
    def generate_bug_report() -> str:
        """
        Invokes the `scan_for_bugs` tool to scan the entire workspace and returns
        a concise bug report.
        """
        try:
            from .tools.scan_for_bugs import generate_bug_report_sync
            return generate_bug_report_sync()
        except Exception as e:
            return f"Unexpected error during bug scan: {str(e)}"