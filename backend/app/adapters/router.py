import logging
from .openai import OpenAIAdapter
from .anthropic import AnthropicAdapter
from ..tools.scan_for_bugs import generate_bug_report_async

logger = logging.getLogger("devpilot.router")

class ModelRouter:
    """
    Abstracts model endpoints behind a dynamic router interface.
    Supports multiple providers (OpenAI, Anthropic, Groq, local) via standard interface rules
    and falls back automatically on connection failure.
    """
    def __init__(self, default_profile: dict = None):
        self.default_profile = default_profile or {}

    def get_adapter(self, profile: dict, is_agent: bool = False, task_type: str = "general"):
        """
        Returns the appropriate LLM adapter based on the active profile and task category.
        """
        # 1. Check if a custom model mapping exists in config for agent routing
        from ..config import ConfigManager
        config = ConfigManager()
        
        fmt = profile.get("api_format", "openai")
        key = profile.get("api_key", "")
        url = profile.get("base_url", "")
        model = profile.get("model_name", "")

        if is_agent:
            agent_models = config.get_agent_models()
            custom_model = None
            if task_type and task_type in agent_models:
                custom_model = agent_models[task_type]
            if not custom_model:
                custom_model = config.get_agent_model_name()
            if custom_model:
                model = custom_model
                logger.info(f"ModelRouter: Overriding model for agent '{task_type}' with: {model}")

        # 2. Parse provider prefix if formatted as provider/model_name
        if "/" in model:
            parts = model.split("/", 1)
            provider = parts[0].lower()
            model_name = parts[1]
            logger.info(f"ModelRouter: Detected provider prefix '{provider}' for model '{model_name}'")
            
            if provider == "anthropic" or "claude" in model_name.lower():
                return AnthropicAdapter(key, url, model_name)
            elif provider == "openai":
                if model_name.lower().startswith("gpt-oss"):
                    return OpenAIAdapter(key, url, model)
                else:
                    return OpenAIAdapter(key, url, model_name)
            elif provider in ("google", "models") or "gemini" in model.lower():
                if not url or "openai" not in url.lower():
                    url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                # The Google OpenAI endpoint expects the 'models/...' prefix for API Studio models
                if provider == "models":
                    return OpenAIAdapter(key, url, model)
                return OpenAIAdapter(key, url, model_name)
            else:
                return OpenAIAdapter(key, url, model)

        # 3. Standard fallback based on format properties
        if fmt == "anthropic" or "claude" in model.lower():
            return AnthropicAdapter(key, url, model)
        elif fmt == "google" or "gemini" in model.lower():
            if not url or "openai" not in url.lower():
                url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            return OpenAIAdapter(key, url, model)
        return OpenAIAdapter(key, url, model)

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