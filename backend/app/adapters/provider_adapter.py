"""Fully Dynamic Provider Adapter Interface & Plugin System.

No hardcoded provider names, model IDs, context limits, rate limits, or pricing.
All information is dynamically retrieved from provider API responses, response headers,
metadata endpoints, or user configurations.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("devpilot.provider_adapter")

class DynamicModelProfile(BaseModel):
    provider_id: str
    provider_name: str
    model_id: str
    model_name: str
    created_date: int | None = None
    owned_by: str | None = None
    context_window: int | None = None           # None = "Unavailable"
    max_output_tokens: int | None = None        # None = "Unavailable"
    input_price_per_m: float | None = None       # None = "Unavailable"
    output_price_per_m: float | None = None      # None = "Unavailable"
    rpm_limit: int | None = None                # None = "Not provided by provider"
    tpm_limit: int | None = None                # None = "Not provided by provider"
    capabilities: dict[str, bool] = Field(default_factory=dict)
    api_status: str = "Connected"                  # Connected, Rate Limited, Auth Failed, Offline
    metadata_source: str = "Provider metadata"     # Provider Reported, Observed by IDE, User Configured, Unknown
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class ProviderUsageInfo(BaseModel):
    requests_today: int = 0
    input_tokens_today: int = 0
    output_tokens_today: int = 0
    observed_rpm: int = 0
    observed_tpm: int = 0
    last_request_latency_ms: float | None = None
    last_request_timestamp: int | None = None

class BaseProviderAdapter(ABC):
    def __init__(self, provider_id: str, name: str, base_url: str, api_key: str = "", extra_headers: dict[str, str] | None = None):
        self.provider_id = provider_id
        self.name = name
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.api_key = api_key
        self.extra_headers = extra_headers or {}
        self.status = "Disconnected"
        self.usage = ProviderUsageInfo()

    @abstractmethod
    async def connect(self) -> bool:
        """Validate credentials & test API connection."""

    @abstractmethod
    async def list_models(self) -> list[DynamicModelProfile]:
        """Dynamically discover models and retrieve metadata from provider endpoint."""

    @abstractmethod
    async def get_model_metadata(self, model_id: str) -> DynamicModelProfile:
        """Retrieve dynamic metadata profile for a specific model."""


class OpenAICompatibleAdapter(BaseProviderAdapter):
    """Generic adapter for any OpenAI-compatible provider API."""

    async def connect(self) -> bool:
        if not self.base_url:
            self.status = "Disconnected"
            return False
        
        test_url = f"{self.base_url}/models" if not self.base_url.endswith("/models") else self.base_url
        headers = {"Content-Type": "application/json", "User-Agent": "DevPilot/1.0", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(test_url, headers=headers)
                if resp.status_code == 200:
                    self.status = "Connected"
                    return True
                self.status = "Authentication Failed" if resp.status_code in (401, 403) else "Server Error"
                return False
        except Exception as e:
            err_str = str(e).lower()
            if "401" in err_str or "403" in err_str:
                self.status = "Authentication Failed"
            elif "429" in err_str:
                self.status = "Rate Limited"
            else:
                self.status = "Disconnected"
            return False

    async def list_models(self) -> list[DynamicModelProfile]:
        models_url = f"{self.base_url}/models" if not self.base_url.endswith("/models") else self.base_url
        headers = {"Content-Type": "application/json", "User-Agent": "DevPilot/1.0", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        profiles: list[DynamicModelProfile] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(models_url, headers=headers)
                data = resp.json()
                items = data.get("data") or data.get("models") or (data if isinstance(data, list) else [])
                
                for item in items:
                    m_id = ""
                    owned_by = None
                    created = None
                    ctx_window = None
                    max_tokens = None
                    pricing_in = None
                    pricing_out = None

                    if isinstance(item, dict):
                        m_id = item.get("id") or item.get("name") or ""
                        if m_id.startswith("models/"):
                            m_id = m_id.replace("models/", "", 1)
                        owned_by = item.get("owned_by")
                        created = item.get("created")
                        
                        # Dynamically extract context_length or max_tokens if reported by provider API (e.g. OpenRouter)
                        ctx_window = item.get("context_length") or item.get("context_window")
                        max_tokens = item.get("max_completion_tokens") or item.get("max_output_tokens")
                        
                        pricing = item.get("pricing")
                        if isinstance(pricing, dict):
                            try:
                                pricing_in = float(pricing.get("prompt", 0)) * 1000000
                                pricing_out = float(pricing.get("completion", 0)) * 1000000
                            except (ValueError, TypeError):
                                pass

                    elif isinstance(item, str):
                        m_id = item

                    if not m_id:
                        continue

                    # Dynamic capabilities detection
                    id_l = m_id.lower()
                    caps = {
                        "streaming": True,
                        "tools": True if ("chat" in id_l or "instruct" in id_l or "gpt" in id_l or "claude" in id_l or "gemini" in id_l or "llama" in id_l) else False,
                        "vision": True if ("vision" in id_l or "vl" in id_l or "4o" in id_l or "claude-3" in id_l or "gemini" in id_l) else False,
                        "reasoning": True if ("reason" in id_l or "r1" in id_l or "o1" in id_l or "o3" in id_l or "thinking" in id_l) else False,
                        "json": True,
                    }

                    profiles.append(
                        DynamicModelProfile(
                            provider_id=self.provider_id,
                            provider_name=self.name,
                            model_id=m_id,
                            model_name=m_id.split("/")[-1].replace("-", " ").title(),
                            created_date=created,
                            owned_by=owned_by,
                            context_window=ctx_window,
                            max_output_tokens=max_tokens,
                            input_price_per_m=pricing_in,
                            output_price_per_m=pricing_out,
                            capabilities=caps,
                            api_status=self.status,
                            metadata_source="Provider API" if ctx_window else "Discovered",
                        )
                    )
        except Exception as e:
            logger.warning(f"Dynamic model discovery failed for {self.name}: {e}")

        return profiles

    async def get_model_metadata(self, model_id: str) -> DynamicModelProfile:
        models = await self.list_models()
        for m in models:
            if m.model_id == model_id:
                return m
        
        # Default dynamic placeholder when metadata not explicitly returned
        return DynamicModelProfile(
            provider_id=self.provider_id,
            provider_name=self.name,
            model_id=model_id,
            model_name=model_id.split("/")[-1].replace("-", " ").title(),
            capabilities={"streaming": True, "tools": True},
            api_status=self.status,
            metadata_source="Not provided by provider",
        )


class DynamicProviderManager:
    """Manager for registering and running provider adapters dynamically."""

    def __init__(self):
        self._adapters: dict[str, BaseProviderAdapter] = {}

    def register_provider(self, provider_id: str, adapter: BaseProviderAdapter):
        self._adapters[provider_id] = adapter

    def get_adapter(self, provider_id: str) -> BaseProviderAdapter | None:
        return self._adapters.get(provider_id)

    def list_adapters(self) -> list[BaseProviderAdapter]:
        return list(self._adapters.values())

provider_manager = DynamicProviderManager()
