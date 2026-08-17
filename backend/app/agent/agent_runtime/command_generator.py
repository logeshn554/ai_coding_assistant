import os
import re
import sys


class TerminalCommandGenerator:
    """
    Utility to generate/translate shell commands based on the active operating system and shell.
    """

    @staticmethod
    def detect_shell() -> str:
        """
        Detects the active shell.
        Returns "powershell", "cmd", or "bash".
        """
        if sys.platform == "win32":
            # If we are in Windows, default to PowerShell, but check if we're forced to CMD
            if os.environ.get("LOOPIX_SHELL", "").lower() == "cmd":
                return "cmd"
            return "powershell"
        return "bash"

    @classmethod
    def generate_command(cls, unix_cmd: str, target_shell: str = None) -> str:
        """
        Translates a Unix-style command to a target shell (defaults to detected active shell).
        """
        if not target_shell:
            target_shell = cls.detect_shell()

        if target_shell == "bash":
            return unix_cmd

        # Translate Unix command components
        translated = unix_cmd

        # 1. tail conversion
        # Examples: "tail -n 30", "tail -30"
        tail_pattern = r"\|\s*tail\s*(?:-n\s*|-)?(\d+)"
        if target_shell == "powershell":
            translated = re.sub(tail_pattern, r"| Select-Object -Last \1", translated)
        elif target_shell == "cmd":
            # CMD doesn't have an easy pipe-tail, we just strip it or use nothing
            translated = re.sub(tail_pattern, r"", translated)

        # 2. head conversion
        # Examples: "head -n 10", "head -10"
        head_pattern = r"\|\s*head\s*(?:-n\s*|-)?(\d+)"
        if target_shell == "powershell":
            translated = re.sub(head_pattern, r"| Select-Object -First \1", translated)
        elif target_shell == "cmd":
            translated = re.sub(head_pattern, r"", translated)

        # 3. grep conversion
        # Example: "grep 'pattern'", "grep pattern"
        # We handle: | grep [-i] ['"]pattern['"]
        grep_pattern = r"\|\s*grep\s*(?:-i\s*)?['\"]?([^'\"\s|&;]+)['\"]?"
        if target_shell == "powershell":
            translated = re.sub(grep_pattern, r'| Select-String -Pattern "\1"', translated)
        elif target_shell == "cmd":
            translated = re.sub(grep_pattern, r'| findstr "\1"', translated)

        # 4. rm -rf conversion
        # Example: "rm -rf path"
        rm_rf_pattern = r"\brm\s+-rf\s+([^\s|&;]+)"
        if target_shell == "powershell":
            translated = re.sub(rm_rf_pattern, r"Remove-Item -Recurse -Force \1", translated)
        elif target_shell == "cmd":
            translated = re.sub(rm_rf_pattern, r"rmdir /s /q \1 2>nul || del /f /q \1", translated)

        # 5. chmod conversion
        # Example: "chmod +x script.sh"
        chmod_pattern = r"\bchmod\s+\+?[xrw\d]+\s+([^\s|&;]+)"
        if target_shell in ("powershell", "cmd"):
            # Chmod is not supported on Windows, so we just remove it or replace with echo
            translated = re.sub(chmod_pattern, r"echo 'chmod skipped on Windows'", translated)

        # 6. cat conversion
        # Example: "cat path"
        cat_pattern = r"\bcat\s+([^\s|&;]+)"
        if target_shell == "powershell":
            translated = re.sub(cat_pattern, r"Get-Content \1", translated)
        elif target_shell == "cmd":
            translated = re.sub(cat_pattern, r"type \1", translated)

        return translated
