import os
from typing import Optional
import json
import logging
import subprocess
from pathlib import Path
import keyring
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Centralized configuration management for DevPilot Backend."""
    
    APP_NAME: str = "DevPilot API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Server Settings
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    
    # Security & Auth
    SESSION_TOKEN: str = ""
    JWT_SECRET: str = ""
    
    # CORS Configuration
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ALLOW_REMOTE: bool = False
    DOCKER_MODE: bool = False
    
    # Storage & Database
    DATABASE_URL: str = "sqlite:///devpilot.db"
    REDIS_URL: str = "redis://localhost:6379"
    
    # LLM & AI Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    
    # Auto QA & Dev Server Settings
    AUTO_INSPECT_ON_SERVER_START: bool = False

    # Cost Circuit Breaker
    # Soft advisory — user is prompted to approve continuation above this threshold
    COST_LIMIT_USD: float = 5.0
    # Hard ceiling — session is forcibly terminated above this amount, no user override
    DEVPILOT_HARD_COST_LIMIT: float = 10.0

    # Web Search Fallback Settings
    WEB_SEARCH_FALLBACK_ENABLED: bool = False
    REPEAT_ERROR_THRESHOLD: int = 2

    # Docker Sandbox settings
    USE_SANDBOX: bool = False
    SANDBOX_IMAGE: str = "python:3.12-slim"

    # Logging settings
    LOG_JSON: bool = False
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def __init__(self, **values):
        super().__init__(**values)
        try:
            # Load or auto-generate JWT_SECRET on first run and store in encrypted keyring
            secret = keyring.get_password("devpilot", "jwt_secret")
            if not secret:
                import secrets
                secret = secrets.token_hex(32)
                keyring.set_password("devpilot", "jwt_secret", secret)
            self.JWT_SECRET = secret
        except Exception:
            # Fallback to in-memory generation if keyring is inaccessible
            import secrets
            self.JWT_SECRET = secrets.token_hex(32)

settings = Settings()

from keyring.backend import KeyringBackend

from cryptography.fernet import Fernet

class DevPilotFileKeyring(KeyringBackend):
    """
    An encrypted file-based keyring backend that persists keys/passwords securely using Fernet encryption
    under the user's config directory (~/.devpilot/.keyring.json). Useful in headless/Docker environments.
    """
    priority = 1

    def __init__(self, filepath=None):
        if filepath is None:
            self.filepath = Path.home() / ".devpilot" / ".keyring.json"
        else:
            self.filepath = Path(filepath)
        self.key_filepath = self.filepath.parent / ".keyring.key"

    def _get_fernet(self) -> Fernet:
        self.key_filepath.parent.mkdir(parents=True, exist_ok=True)
        if not self.key_filepath.exists():
            key = Fernet.generate_key()
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            try:
                fd = os.open(self.key_filepath, flags, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(key)
            except Exception:
                self.key_filepath.write_bytes(key)
                try:
                    os.chmod(self.key_filepath, 0o600)
                except Exception:
                    pass
        else:
            key = self.key_filepath.read_bytes()
        return Fernet(key)

    def _load_data(self) -> dict:
        try:
            if self.filepath.exists():
                raw = self.filepath.read_bytes()
                if not raw:
                    return {}
                try:
                    fernet = self._get_fernet()
                    decrypted = fernet.decrypt(raw).decode("utf-8")
                    return json.loads(decrypted)
                except Exception:
                    # Backward compatibility fallback for unencrypted legacy format
                    try:
                        return json.loads(raw.decode("utf-8"))
                    except Exception:
                        return {}
        except Exception:
            pass
        return {}

    def _save_data(self, data: dict):
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            fernet = self._get_fernet()
            payload = json.dumps(data, indent=4).encode("utf-8")
            encrypted = fernet.encrypt(payload)
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            try:
                fd = os.open(self.filepath, flags, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(encrypted)
            except Exception:
                self.filepath.write_bytes(encrypted)
                try:
                    os.chmod(self.filepath, 0o600)
                except Exception:
                    pass
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
        from filelock import FileLock
        lock_path = CONFIG_FILE.with_suffix(".lock")
        try:
            with FileLock(lock_path, timeout=5):
                if CONFIG_FILE.exists():
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        return json.load(f)
        except Exception:
            pass
        return {"active_profile_id": "", "profiles": []}

    def _save_raw_config(self, config_data: dict):
        from filelock import FileLock
        lock_path = CONFIG_FILE.with_suffix(".lock")
        try:
            with FileLock(lock_path, timeout=5):
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
            decrypted_key = p.get("api_key", "")
            try:
                k_key = keyring.get_password("devpilot", p["id"])
                if k_key:
                    decrypted_key = k_key
            except Exception:
                pass
            
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
                "name": p.get("name", "Unnamed Profile"),
                "api_key": key_val,
                "base_url": p.get("base_url", "https://api.openai.com/v1"),
                "model_name": p.get("model_name", ""),
                "api_format": p.get("api_format", "openai")
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
                api_key = p.get("api_key", "")
                try:
                    k_key = keyring.get_password("devpilot", profile_id)
                    if k_key:
                        api_key = k_key
                except Exception:
                    pass
                return {
                    "id": p["id"],
                    "name": p.get("name", "Unnamed Profile"),
                    "api_key": api_key,
                    "base_url": p.get("base_url", "https://api.openai.com/v1"),
                    "model_name": p.get("model_name", ""),
                    "api_format": p.get("api_format", "openai")
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
                "name": profile_data.get("name", "New Profile"),
                "base_url": profile_data.get("base_url", "https://api.openai.com/v1"),
                "model_name": profile_data.get("model_name", ""),
                "api_format": profile_data.get("api_format", "openai")
            }
            config.setdefault("profiles", []).append(existing_profile)
            
        # Always set active_profile_id if not set
        if not config.get("active_profile_id"):
            config["active_profile_id"] = p_id
            
        # Update fields
        existing_profile["name"] = profile_data.get("name", "New Profile")
        existing_profile["base_url"] = profile_data.get("base_url", "https://api.openai.com/v1")
        existing_profile["model_name"] = profile_data.get("model_name", "")
        existing_profile["api_format"] = profile_data.get("api_format", "openai")
        
        # Handle API key update (checking if it was masked or is a new plaintext)
        new_key = profile_data.get("api_key", "")
        is_masked = "..." in new_key or "*" in new_key
        
        if not is_masked:
            existing_profile["api_key"] = new_key
            try:
                keyring.set_password("devpilot", p_id, new_key)
            except Exception as e:
                logger.warning(f"Failed to set keyring password for {p_id}: {e}")

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

    def get_auto_inspect_on_server_start(self) -> bool:
        config = self._read_raw_config()
        return config.get("auto_inspect_on_server_start", False)

    def set_auto_inspect_on_server_start(self, val: bool):
        config = self._read_raw_config()
        config["auto_inspect_on_server_start"] = bool(val)
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

    def get_agent_profiles(self) -> dict:
        config = self._read_raw_config()
        return config.get("agent_profiles", {})

    def set_agent_profiles(self, agent_profiles: dict):
        config = self._read_raw_config()
        config["agent_profiles"] = agent_profiles
        self._save_raw_config(config)

    def get_image_analysis_model(self) -> str:
        config = self._read_raw_config()
        return config.get("image_analysis_model", "")

    def set_image_analysis_model(self, name: str):
        config = self._read_raw_config()
        config["image_analysis_model"] = str(name or "")
        self._save_raw_config(config)

    def get_devpilot_rpm(self) -> int:
        config = self._read_raw_config()
        return config.get("devpilot_rpm", 15)

    def set_devpilot_rpm(self, val: int):
        config = self._read_raw_config()
        config["devpilot_rpm"] = max(1, int(val))
        self._save_raw_config(config)

    def get_concurrency_mode(self) -> str:
        config = self._read_raw_config()
        return config.get("concurrency_mode", "parallel")

    def set_concurrency_mode(self, mode: str):
        config = self._read_raw_config()
        if mode not in ("sequential", "parallel"):
            mode = "parallel"
        config["concurrency_mode"] = mode
        self._save_raw_config(config)

    def get_mcp_servers(self) -> list:
        config = self._read_raw_config()
        return config.get("mcp_servers", [])

    def set_mcp_servers(self, servers: list):
        config = self._read_raw_config()
        config["mcp_servers"] = list(servers or [])
        self._save_raw_config(config)

    def add_mcp_server(self, server: dict) -> list:
        config = self._read_raw_config()
        servers = config.get("mcp_servers", [])
        sid = server.get("id") or server.get("name")
        # Remove existing server with same ID if present
        servers = [s for s in servers if (s.get("id") or s.get("name")) != sid]
        servers.append(server)
        config["mcp_servers"] = servers
        self._save_raw_config(config)
        return servers

    def delete_mcp_server(self, server_id: str) -> list:
        config = self._read_raw_config()
        servers = config.get("mcp_servers", [])
        servers = [s for s in servers if (s.get("id") or s.get("name")) != server_id]
        config["mcp_servers"] = servers
        self._save_raw_config(config)
        return servers

    def get_web_search_fallback_enabled(self) -> bool:
        config = self._read_raw_config()
        return config.get("web_search_fallback_enabled", False)

    def set_web_search_fallback_enabled(self, val: bool):
        config = self._read_raw_config()
        config["web_search_fallback_enabled"] = bool(val)
        self._save_raw_config(config)

    def get_repeat_error_threshold(self) -> int:
        config = self._read_raw_config()
        return config.get("repeat_error_threshold", 2)

    def set_repeat_error_threshold(self, val: int):
        config = self._read_raw_config()
        config["repeat_error_threshold"] = max(1, min(10, int(val)))
        self._save_raw_config(config)

    def get_tavily_api_key(self) -> str:
        try:
            key = keyring.get_password("devpilot", "tavily")
            if key:
                return key
        except Exception:
            pass
        config = self._read_raw_config()
        key_from_config = config.get("tavily_api_key", "")
        if key_from_config:
            try:
                keyring.set_password("devpilot", "tavily", key_from_config)
                config.pop("tavily_api_key", None)
                self._save_raw_config(config)
            except Exception:
                pass
            return key_from_config
        return os.environ.get("TAVILY_API_KEY", "")

    def set_tavily_api_key(self, key: str):
        try:
            keyring.set_password("devpilot", "tavily", str(key or ""))
        except Exception as e:
            logger.error(f"Failed to store Tavily API key in keyring: {e}")
        config = self._read_raw_config()
        if "tavily_api_key" in config:
            config.pop("tavily_api_key", None)
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

    # ------------------------------------------------------------------
    # Agent Behavior & Local Permissions Settings
    # ------------------------------------------------------------------

    def get_artifact_review_policy(self) -> str:
        config = self._read_raw_config()
        return config.get("artifact_review_policy", "Always Ask")

    def set_artifact_review_policy(self, policy: str):
        config = self._read_raw_config()
        config["artifact_review_policy"] = policy
        self._save_raw_config(config)

    def get_file_access_rules(self) -> list:
        config = self._read_raw_config()
        return config.get("file_access_rules", [])

    def set_file_access_rules(self, rules: list):
        config = self._read_raw_config()
        config["file_access_rules"] = rules
        self._save_raw_config(config)

    def get_network_access_rules(self) -> list:
        config = self._read_raw_config()
        return config.get("network_access_rules", [])

    def set_network_access_rules(self, rules: list):
        config = self._read_raw_config()
        config["network_access_rules"] = rules
        self._save_raw_config(config)

    def get_terminal_command_rules(self) -> list:
        config = self._read_raw_config()
        return config.get("terminal_command_rules", [])

    def set_terminal_command_rules(self, rules: list):
        config = self._read_raw_config()
        config["terminal_command_rules"] = rules
        self._save_raw_config(config)

    def get_unsandboxed_command_rules(self) -> list:
        config = self._read_raw_config()
        return config.get("unsandboxed_command_rules", [])

    def set_unsandboxed_command_rules(self, rules: list):
        config = self._read_raw_config()
        config["unsandboxed_command_rules"] = rules
        self._save_raw_config(config)

    def get_mcp_tool_rules(self) -> list:
        config = self._read_raw_config()
        return config.get("mcp_tool_rules", [])

    def set_mcp_tool_rules(self, rules: list):
        config = self._read_raw_config()
        config["mcp_tool_rules"] = rules
        self._save_raw_config(config)

    def get_temperature(self) -> float:
        config = self._read_raw_config()
        return config.get("temperature", 1.0)

    def set_temperature(self, val: float):
        config = self._read_raw_config()
        config["temperature"] = float(val)
        self._save_raw_config(config)

    def get_top_p(self) -> float:
        config = self._read_raw_config()
        return config.get("top_p", 1.0)

    def set_top_p(self, val: float):
        config = self._read_raw_config()
        config["top_p"] = float(val)
        self._save_raw_config(config)

    def get_max_tokens(self) -> int:
        config = self._read_raw_config()
        return config.get("max_tokens", 16384)

    def set_max_tokens(self, val: int):
        config = self._read_raw_config()
        config["max_tokens"] = int(val)
        self._save_raw_config(config)

    def get_seed(self) -> Optional[int]:
        config = self._read_raw_config()
        return config.get("seed", 42)

    def set_seed(self, val: Optional[int]):
        config = self._read_raw_config()
        config["seed"] = int(val) if val is not None else None
        self._save_raw_config(config)

    def get_stream(self) -> bool:
        config = self._read_raw_config()
        return config.get("stream", True)

    def set_stream(self, val: bool):
        config = self._read_raw_config()
        config["stream"] = bool(val)
        self._save_raw_config(config)

    def get_decision_engine(self) -> str:
        config = self._read_raw_config()
        return config.get("decision_engine", "rule_based")

    def set_decision_engine(self, val: str):
        config = self._read_raw_config()
        config["decision_engine"] = str(val)
        self._save_raw_config(config)

    def get_dual_llm_mode(self) -> bool:
        config = self._read_raw_config()
        return config.get("dual_llm_mode", False)

    def set_dual_llm_mode(self, val: bool):
        config = self._read_raw_config()
        config["dual_llm_mode"] = bool(val)
        self._save_raw_config(config)

config_manager = ConfigManager()

