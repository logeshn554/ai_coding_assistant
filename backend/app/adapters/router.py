import logging
from typing import Dict, Any, List, Optional
from .llm import LLMAdapter
from ..tools.scan_for_bugs import generate_bug_report_async

logger = logging.getLogger("devpilot.router")

# Capability Registry for known models
_MODEL_CAPABILITIES = {
    # Anthropic models
    "claude-3-5-sonnet": {"context_window": 200000, "vision": True, "tool_calling": True},
    "claude-3-5-opus": {"context_window": 200000, "vision": True, "tool_calling": True},
    "claude-3-opus": {"context_window": 200000, "vision": True, "tool_calling": True},
    "claude-3-sonnet": {"context_window": 200000, "vision": True, "tool_calling": True},
    "claude-3-haiku": {"context_window": 200000, "vision": True, "tool_calling": True},
    # OpenAI models
    "gpt-4o": {"context_window": 128000, "vision": True, "tool_calling": True},
    "gpt-4o-mini": {"context_window": 128000, "vision": True, "tool_calling": True},
    "gpt-4-turbo": {"context_window": 128000, "vision": True, "tool_calling": True},
    "gpt-4": {"context_window": 8192, "vision": False, "tool_calling": True},
    "gpt-3.5-turbo": {"context_window": 16385, "vision": False, "tool_calling": True},
    "o1": {"context_window": 128000, "vision": True, "tool_calling": True},
    "o3-mini": {"context_window": 200000, "vision": False, "tool_calling": True},
    # Gemini models
    "gemini-1.5-pro": {"context_window": 2000000, "vision": True, "tool_calling": True},
    "gemini-1.5-flash": {"context_window": 1000000, "vision": True, "tool_calling": True},
    "gemini-2.0-flash": {"context_window": 1048576, "vision": True, "tool_calling": True},
}

DEFAULT_CAPABILITY = {"context_window": 8192, "vision": False, "tool_calling": True}


def get_model_capabilities(model_name: str) -> Dict[str, Any]:
    """Retrieve capabilities from the registry for the given model name."""
    model_name_lower = model_name.lower()
    for key, caps in _MODEL_CAPABILITIES.items():
        if key in model_name_lower:
            return caps
    
    # Fuzzy fallback logic based on brand prefixes
    if "claude" in model_name_lower:
        return {"context_window": 200000, "vision": True, "tool_calling": True}
    if "gpt" in model_name_lower:
        return {"context_window": 128000, "vision": "gpt-4" in model_name_lower or "gpt-4o" in model_name_lower, "tool_calling": True}
    if "gemini" in model_name_lower:
        return {"context_window": 1000000, "vision": True, "tool_calling": True}
    if "llama" in model_name_lower or "qwen" in model_name_lower or "mistral" in model_name_lower:
        return {"context_window": 32768, "vision": "vision" in model_name_lower, "tool_calling": True}
    
    return DEFAULT_CAPABILITY


class ModelRouter:
    """
    Abstracts model endpoints behind a dynamic router interface.
    Supports multiple providers (OpenAI, Anthropic, Groq, local) via standard interface rules
    and falls back automatically on connection failure.
    """
    def __init__(self, default_profile: dict = None):
        self.default_profile = default_profile or {}

    def check_capabilities(self, model_name: str, messages: list) -> None:
        """Scan messages for image attachments and verify model capability."""
        caps = get_model_capabilities(model_name)
        has_image = False
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and (item.get("type") == "image_url" or "image" in item):
                        has_image = True
                        break
            elif isinstance(content, dict) and (content.get("type") == "image_url" or "image" in content):
                has_image = True

        if has_image and not caps.get("vision"):
            logger.warning(
                f"ModelRouter WARNING: Model '{model_name}' does not list vision capability in registry, "
                f"but messages contain image inputs. This request may fail."
            )

    def get_adapter(self, profile: dict, is_agent: bool = False, task_type: str = "general"):
        """
        Returns the appropriate LLM adapter based on the active profile and task category.
        """
        # 1. Check if a custom model mapping exists in config for agent routing
        from ..config import ConfigManager
        config = ConfigManager()
        
        key = profile.get("api_key", "")
        url = profile.get("base_url", "")
        model = profile.get("model_name", "") or profile.get("model") or ""

        url_l = (url or "").lower()
        model_l = (model or "").lower()

        # Parse provider prefix if formatted as provider/model_name
        if "/" in model and not model.startswith("models/"):
            parts = model.split("/", 1)
            provider = parts[0].lower()
            model_name = parts[1]
            logger.info(f"ModelRouter: Detected provider prefix '{provider}' for model '{model_name}'")
            
            if provider == "anthropic" or "claude" in model_name.lower():
                return LLMAdapter(key, url, model_name, provider="anthropic")
            elif provider in ("google", "models") or "gemini" in model.lower():
                if not url or "openai" not in url_l:
                    url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                return LLMAdapter(key, url, model, provider="openai")
            else:
                return LLMAdapter(key, url, model, provider="openai")

        # Standard routing based on api_format, base_url or model name
        fmt = (profile.get("api_format") or "").lower()
        if fmt == "anthropic" or "anthropic.com" in url_l or "claude" in model_l:
            return LLMAdapter(key, url, model, provider="anthropic")
        elif fmt == "google" or "generativelanguage.googleapis.com" in url_l:
            if "openai" not in url_l:
                url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            return LLMAdapter(key, url, model, provider="openai")

        return LLMAdapter(key, url, model, provider="openai")

    _fallback_listeners = []

    @classmethod
    def register_fallback_listener(cls, listener):
        cls._fallback_listeners.append(listener)

    @classmethod
    def unregister_fallback_listener(cls, listener):
        if listener in cls._fallback_listeners:
            cls._fallback_listeners.remove(listener)

    @classmethod
    def notify_fallback(cls, error_msg: str):
        for listener in cls._fallback_listeners:
            try:
                listener(error_msg)
            except Exception:
                pass

    async def completion(self, profile: dict, messages: list, system_prompt: str = None, is_agent: bool = False, task_type: str = "general") -> str:
        """
        Queries the routed model and aggregates streamed text chunks.
        """
        model_name = profile.get("model_name") or profile.get("model") or "unknown"
        self.check_capabilities(model_name, messages)

        adapter = self.get_adapter(profile, is_agent, task_type)
        response_text = ""
        try:
            async for chunk in adapter.stream_chat(messages, [], system_prompt):
                if chunk["type"] == "text":
                    response_text += chunk["content"]
        except Exception as e:
            logger.error(f"ModelRouter: Primary model path failed: {str(e)}")
            self.notify_fallback(str(e))
            raise e
        return response_text

    async def generate_bug_report(self, profile: dict = None) -> str:
        """
        Scans the entire workspace for bugs using the `scan_for_bugs` tool and returns a concise report.
        """
        try:
            logger.info("ModelRouter: Initiating workspace bug scan...")
            report = await generate_bug_report_async()
            logger.info("ModelRouter: Bug scan completed successfully.")
            return report.strip()
        except Exception as e:
            logger.error(f"ModelRouter: Bug scan failed: {str(e)}")
            raise e