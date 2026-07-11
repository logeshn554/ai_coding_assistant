import os
import json
from pathlib import Path
from cryptography.fernet import Fernet

CONFIG_DIR = Path.home() / ".devpilot"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEY_FILE = CONFIG_DIR / ".key"

class ConfigManager:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.fernet = self._get_or_create_fernet()
        self._init_config()

    def _get_or_create_fernet(self) -> Fernet:
        """
        Loads the encryption key from KEY_FILE or creates a new one.
        """
        if KEY_FILE.exists():
            key = KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            KEY_FILE.write_bytes(key)
        return Fernet(key)

    def _init_config(self):
        """
        Initializes the config file with empty profiles and settings if it doesn't exist.
        """
        if not CONFIG_FILE.exists():
            default_config = {
                "active_profile_id": "default-anthropic",
                "last_workspace": "",
                "profiles": [
                    {
                        "id": "default-anthropic",
                        "name": "Anthropic Claude 3.5 Sonnet",
                        "api_key": "",
                        "base_url": "https://api.anthropic.com/v1",
                        "model_name": "claude-3-5-sonnet-20241022",
                        "api_format": "anthropic"
                    },
                    {
                        "id": "default-openai",
                        "name": "OpenAI GPT-4o",
                        "api_key": "",
                        "base_url": "https://api.openai.com/v1",
                        "model_name": "gpt-4o",
                        "api_format": "openai"
                    },
                    {
                        "id": "default-ollama",
                        "name": "Ollama (Local Llama 3)",
                        "api_key": "ollama",
                        "base_url": "http://localhost:11434/v1",
                        "model_name": "llama3",
                        "api_format": "openai"
                    }
                ]
            }
            self._save_raw_config(default_config)


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

    def _encrypt(self, text: str) -> str:
        if not text:
            return ""
        return self.fernet.encrypt(text.encode("utf-8")).decode("utf-8")

    def _decrypt(self, cipher_text: str) -> str:
        if not cipher_text:
            return ""
        try:
            return self.fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except Exception:
            return "" # Failed to decrypt (e.g. invalid key or format)

    def list_profiles(self, mask_keys: bool = True) -> dict:
        """
        Retrieves all connection profiles, optionally masking keys.
        """
        config = self._read_raw_config()
        profiles = []
        for p in config.get("profiles", []):
            decrypted_key = self._decrypt(p.get("api_key", ""))
            
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
                return {
                    "id": p["id"],
                    "name": p["name"],
                    "api_key": self._decrypt(p.get("api_key", "")),
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
                "api_key": "",
                "base_url": profile_data["base_url"],
                "model_name": profile_data["model_name"],
                "api_format": profile_data["api_format"]
            }
            config.setdefault("profiles", []).append(existing_profile)
            
        # Update fields
        existing_profile["name"] = profile_data["name"]
        existing_profile["base_url"] = profile_data["base_url"]
        existing_profile["model_name"] = profile_data["model_name"]
        existing_profile["api_format"] = profile_data["api_format"]
        
        # Handle API key update (checking if it was masked or is a new plaintext)
        new_key = profile_data.get("api_key", "")
        is_masked = "..." in new_key or "*" in new_key
        
        if not is_masked:
            # Overwrite with encrypted new key
            existing_profile["api_key"] = self._encrypt(new_key)
        # If it is masked, keep the old key already in the config file

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


