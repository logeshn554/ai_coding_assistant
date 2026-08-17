import logging
from typing import Any

from ..tools.scan_for_bugs import generate_bug_report_async
from .llm import LLMAdapter

logger = logging.getLogger("loopix.router")


class MockLLMAdapter:
    """A lightweight mock LLM adapter that returns deterministic responses for testing."""

    async def stream_chat(self, messages, tools=None, system_prompt=None):
        """Yield a single text chunk with a mock response."""
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")[:200]
                break
        mock_response = f"[mock] Responded to: {last_user}" if last_user else "[mock] OK"
        yield {"type": "text", "content": mock_response}


def get_model_capabilities(model_name: str) -> dict[str, Any]:
    """Dynamically construct capabilities for any model name without hardcoded lists."""
    if not model_name:
        return {"context_window": 8192, "vision": False, "tool_calling": True}

    model_name_lower = model_name.lower()
    vision = "vision" in model_name_lower or "vl" in model_name_lower or "4o" in model_name_lower or "claude-3" in model_name_lower or "gemini" in model_name_lower

    # Infer context window from well-known model name patterns
    if "gemini" in model_name_lower:
        context_window = 1_000_000
    elif "claude" in model_name_lower:
        context_window = 200_000
    elif "gpt-4o" in model_name_lower or "o1" in model_name_lower or "o3" in model_name_lower:
        context_window = 128_000
    elif "gpt-4" in model_name_lower or "llama" in model_name_lower or "qwen" in model_name_lower or "mistral" in model_name_lower or "deepseek" in model_name_lower:
        context_window = 32_000
    else:
        # Default safe fallback — avoids NoneType comparison errors
        context_window = 8192

    return {"context_window": context_window, "vision": vision, "tool_calling": True}


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

    def _resolve_profile(self, profile: dict, is_agent: bool, task_type: str) -> dict:
        if is_agent and task_type:
            from ..config import config_manager as config
            agent_profiles = config.get_agent_profiles()
            mapped_profile_id = agent_profiles.get(task_type)
            if mapped_profile_id:
                mapped_profile = config.get_profile(mapped_profile_id)
                if mapped_profile:
                    logger.info(f"ModelRouter: Overriding active profile with mapped profile '{mapped_profile['name']}' for agent '{task_type}'")
                    return mapped_profile
        return profile

    def get_adapter(self, profile: dict, is_agent: bool = False, task_type: str = "general"):
        """
        Returns the appropriate LLM adapter based on the active profile and task category.
        """
        profile = self._resolve_profile(profile, is_agent, task_type)
        # Return mock adapter if profile specifies mock provider/model (used in tests)
        provider_flag = (profile.get("provider") or "").lower()
        key = profile.get("api_key", "")
        url = profile.get("base_url", "")
        model = profile.get("model_name", "") or profile.get("model") or ""
        if provider_flag == "mock" or model.lower() == "mock":
            return MockLLMAdapter()

        model_l = (model or "").lower()
        url_l = (url or "").lower()

        # Parse provider prefix if formatted as provider/model_name
        if "/" in model and not model.startswith("models/"):
            parts = model.split("/", 1)
            prefix_provider = parts[0].lower()
            model_name = parts[1]
            logger.info(f"ModelRouter: Detected provider prefix '{prefix_provider}' for model '{model_name}'")
            
            if prefix_provider == "anthropic" or "claude" in model_name.lower():
                return LLMAdapter(key, url, model_name, provider="anthropic")
            elif prefix_provider in ("google", "models") or "gemini" in model.lower():
                if not url or "openai" not in url_l:
                    url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                return LLMAdapter(key, url, model, provider="openai")
            else:
                # Return the full model name containing the slash/prefix (necessary for OpenRouter, custom NIM gateways, etc.)
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
        profile = self._resolve_profile(profile, is_agent, task_type)
        model_name = profile.get("model_name") or profile.get("model") or "unknown"
        self.check_capabilities(model_name, messages)

        adapter = self.get_adapter(profile, is_agent, task_type)
        response_text = ""
        try:
            async for chunk in adapter.stream_chat(messages, [], system_prompt):
                if chunk["type"] == "text":
                    response_text += chunk["content"]
        except Exception as e:
            logger.error(f"ModelRouter: Primary model path failed: {e!s}")
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
            logger.error(f"ModelRouter: Bug scan failed: {e!s}")
            raise e

# NOTE: Previous versions contained AgentReputationEngine, CostOptimizer,
# LatencyOptimizer, and ProviderHealthMonitor classes with hardcoded model
# data. These were removed to comply with the dynamic multi-provider
# architecture. Reputation/cost/latency tracking should be implemented
# dynamically using data from provider profiles or runtime observations.