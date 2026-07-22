import os
import json
import logging
import subprocess
from pathlib import Path
import keyring

from keyring.backend import KeyringBackend

class DevPilotFileKeyring(KeyringBackend):
    """
    A simple file-based keyring backend that persists keys/passwords in a JSON file
    under the user's config directory. Useful in headless/Docker environments.
    """
    priority = 1

    def __init__(self, filepath=None):
        if filepath is None:
            self.filepath = Path.home() / ".devpilot" / ".keyring.json"
        else:
            self.filepath = Path(filepath)

    def _load_data(self) -> dict:
        try:
            if self.filepath.exists():
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_data(self, data: dict):
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def get_password(self, service, username):
        data = self._load_data()
        return data.get(service, {}).get(username)

    def set_password(self, service, username, password):
        data = self._load_data()
        data.setdefault(service, {})[username] = password
        self._save_data(data)

    def delete_password(self, service, username):
        data = self._load_data()
        if service in data and username in data[service]:
            del data[service][username]
            self._save_data(data)

# Force plaintext keyring in headless docker environment to prevent keyring errors or prompting for master password
if os.environ.get("DOCKER_MODE", "false").lower() == "true":
    try:
        keyring.set_keyring(DevPilotFileKeyring())
    except Exception as e:
        print(f"Warning: Failed to set DevPilotFileKeyring: {e}")

logger = logging.getLogger("devpilot.config")

CONFIG_DIR = Path.home() / ".devpilot"
CONFIG_FILE = CONFIG_DIR / "config.json"

class ConfigManager:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._init_config()

    def _init_config(self):
        """
        Initializes the config file with empty profiles and settings if it doesn't exist.
        """
        if not CONFIG_FILE.exists():
            default_config = {
                "active_profile_id": "default-ollama",
                "last_workspace": "",
                "profiles": [
                    {
                        "id": "default-ollama",
                        "name": "Ollama Local",
                        "base_url": "http://localhost:11434/v1",
                        "model_name": "",
                        "api_format": "openai"
                    }
                ]
            }
            self._save_raw_config(default_config)
            try:
                keyring.set_password("devpilot", "default-ollama", "")
            except Exception as e:
                logger.error(f"Failed to set initial keyring password: {e}")

    def _read_raw_config(self) -> dict:
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"active_profile_id": "", "profiles": []}

    def _save_raw_config(self, config_data: dict):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            raise IOError(f"Failed to save configuration: {str(e)}")

    def list_profiles(self, mask_keys: bool = True) -> dict:
        """
        Retrieves all connection profiles, optionally masking keys.
        """
        config = self._read_raw_config()
        profiles = []
        for p in config.get("profiles", []):
            try:
                decrypted_key = keyring.get_password("devpilot", p["id"]) or ""
            except Exception:
                decrypted_key = ""
            
            # Mask key for frontend representation
            key_val = decrypted_key
            if mask_keys:
                if not decrypted_key:
                    key_val = ""
                elif len(decrypted_key) <= 8:
                    key_val = "********"
                else:
                    key_val = f"{decrypted_key[:4]}...{decrypted_key[-4:]}"

            profiles.append({
                "id": p["id"],
                "name": p["name"],
                "api_key": key_val,
                "base_url": p["base_url"],
                "model_name": p["model_name"],
                "api_format": p["api_format"]
            })
            
        return {
            "active_profile_id": config.get("active_profile_id", ""),
            "profiles": profiles
        }

    def get_profile(self, profile_id: str) -> dict:
        """
        Gets a single profile by ID with decrypted API key.
        """
        config = self._read_raw_config()
        for p in config.get("profiles", []):
            if p["id"] == profile_id:
                try:
                    api_key = keyring.get_password("devpilot", profile_id) or ""
                except Exception:
                    api_key = ""
                return {
                    "id": p["id"],
                    "name": p["name"],
                    "api_key": api_key,
                    "base_url": p["base_url"],
                    "model_name": p["model_name"],
                    "api_format": p["api_format"]
                }
        return {}

    def get_active_profile(self) -> dict:
        config = self._read_raw_config()
        active_id = config.get("active_profile_id", "")
        profile = self.get_profile(active_id)
        if not profile and config.get("profiles"):
            # Fallback to first profile if active not found
            first_p = config["profiles"][0]
            profile = self.get_profile(first_p["id"])
        return profile

    def set_active_profile(self, profile_id: str):
        config = self._read_raw_config()
        # Verify it exists
        exists = any(p["id"] == profile_id for p in config.get("profiles", []))
        if not exists:
            raise ValueError(f"Profile '{profile_id}' does not exist.")
            
        config["active_profile_id"] = profile_id
        self._save_raw_config(config)

    def save_profile(self, profile_data: dict) -> dict:
        """
        Creates or updates a profile.
        If api_key is masked (contains '...'), it means keep the existing key.
        """
        config = self._read_raw_config()
        p_id = profile_data.get("id")
        
        # Check if updating an existing profile
        existing_profile = None
        if p_id:
            for p in config.get("profiles", []):
                if p["id"] == p_id:
                    existing_profile = p
                    break
        
        # If new profile, generate a unique ID
        if not existing_profile:
            import uuid
            p_id = str(uuid.uuid4())
            existing_profile = {
                "id": p_id,
                "name": profile_data["name"],
                "base_url": profile_data["base_url"],
                "model_name": profile_data["model_name"],
                "api_format": profile_data.get("api_format", "openai")
            }
            config.setdefault("profiles", []).append(existing_profile)
            
        # Update fields
        existing_profile["name"] = profile_data["name"]
        existing_profile["base_url"] = profile_data["base_url"]
        existing_profile["model_name"] = profile_data["model_name"]
        existing_profile["api_format"] = profile_data.get("api_format", "openai")
        
        # Handle API key update (checking if it was masked or is a new plaintext)
        new_key = profile_data.get("api_key", "")
        is_masked = "..." in new_key or "*" in new_key
        
        if not is_masked:
            try:
                keyring.set_password("devpilot", p_id, new_key)
            except Exception as e:
                logger.error(f"Failed to set keyring password for {p_id}: {e}")

        self._save_raw_config(config)
        return self.get_profile(p_id)

    def delete_profile(self, profile_id: str):
        config = self._read_raw_config()
        profiles = config.get("profiles", [])
        
        # Find and remove
        new_profiles = [p for p in profiles if p["id"] != profile_id]
        if len(new_profiles) == len(profiles):
            raise ValueError("Profile not found.")
            
        config["profiles"] = new_profiles
        
        # If we deleted the active profile, reset active_profile_id
        if config.get("active_profile_id") == profile_id:
            config["active_profile_id"] = new_profiles[0]["id"] if new_profiles else ""
            
        try:
            keyring.delete_password("devpilot", profile_id)
        except Exception:
            pass

        self._save_raw_config(config)

    def get_last_workspace(self) -> str:
        config = self._read_raw_config()
        return config.get("last_workspace", "")

    def set_last_workspace(self, path: str):
        config = self._read_raw_config()
        config["last_workspace"] = path
        self._save_raw_config(config)

    def get_project_permissions(self, project_id: str) -> list:
        config = self._read_raw_config()
        perms = config.get("project_permissions", {})
        return perms.get(project_id, [])

    def add_project_permission(self, project_id: str, command: str):
        config = self._read_raw_config()
        perms = config.setdefault("project_permissions", {})
        project_perms = perms.setdefault(project_id, [])
        if command not in project_perms:
            project_perms.append(command)
        self._save_raw_config(config)

    def remove_project_permission(self, project_id: str, command: str):
        config = self._read_raw_config()
        perms = config.get("project_permissions", {})
        project_perms = perms.get(project_id, [])
        if command in project_perms:
            project_perms.remove(command)
        self._save_raw_config(config)

    def get_exclude_list(self) -> list:
        config = self._read_raw_config()
        return config.get("exclude_list", [".git", "node_modules", "venv", "__pycache__", ".devpilot", "dist", "build"])

    def set_exclude_list(self, exclude_list: list):
        config = self._read_raw_config()
        config["exclude_list"] = exclude_list
        self._save_raw_config(config)

    def get_auto_backup_enabled(self) -> bool:
        config = self._read_raw_config()
        return config.get("auto_backup_enabled", True)

    def set_auto_backup_enabled(self, val: bool):
        config = self._read_raw_config()
        config["auto_backup_enabled"] = val
        self._save_raw_config(config)

    def get_agent_model_name(self) -> str:
        config = self._read_raw_config()
        return config.get("agent_model_name", "")

    def set_agent_model_name(self, name: str):
        config = self._read_raw_config()
        config["agent_model_name"] = name
        self._save_raw_config(config)

    def get_agent_models(self) -> dict:
        config = self._read_raw_config()
        return config.get("agent_models", {})

    def set_agent_models(self, agent_models: dict):
        config = self._read_raw_config()
        config["agent_models"] = agent_models
        self._save_raw_config(config)

    # ------------------------------------------------------------------
    # Terminal preferences
    # ------------------------------------------------------------------

    def get_default_shell(self) -> str:
        """Returns the user's preferred default terminal shell.
        Empty string means 'use OS default' (PowerShell on Windows, $SHELL on Unix).
        Valid values: '', 'cmd', 'powershell', 'bash', 'sh'.
        """
        config = self._read_raw_config()
        return config.get("default_shell", "")

    def set_default_shell(self, shell: str):
        """Persist the user's preferred terminal shell."""
        config = self._read_raw_config()
        config["default_shell"] = shell
        self._save_raw_config(config)

    def get_terminal_font_size(self) -> int:
        config = self._read_raw_config()
        return config.get("terminal_font_size", 13)

    def set_terminal_font_size(self, size: int):
        config = self._read_raw_config()
        config["terminal_font_size"] = max(8, min(size, 32))
        self._save_raw_config(config)

    def get_terminal_scrollback(self) -> int:
        config = self._read_raw_config()
        return config.get("terminal_scrollback", 5000)

    def set_terminal_scrollback(self, lines: int):
        config = self._read_raw_config()
        config["terminal_scrollback"] = max(500, min(lines, 100000))
        self._save_raw_config(config)

    def generate_bug_report(self) -> str:
        """Scans the full workspace using the `scan_for_bugs` tool and returns a concise report."""
        try:
            from .tools.scan_for_bugs import generate_bug_report_sync
            return generate_bug_report_sync()
        except Exception as e:
            logger.error(f"Bug scanning failed: {e}")
            return f"Bug scanning failed: {e}"