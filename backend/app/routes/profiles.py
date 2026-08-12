import logging
import urllib.request
import urllib.error
import json
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..state import config_manager, logger

router = APIRouter()

def _is_masked_key(key: str) -> bool:
    """Returns True if the API key string is a masked placeholder (contains dots/asterisks/bullets).
    Empty string is NOT considered masked — it means no key was provided.
    """
    if not key or not key.strip():
        return False  # empty string = no key, not masked
    return any(c in key for c in ("\u2022", "...", "*"))


def _resolve_api_key(req_key: str, profile_id: Optional[str] = None) -> str:
    """
    Resolves the actual API key to use:
    1. If the key is not masked -> use it as-is (user typed it directly).
    2. If the key IS masked (contains ..., *, bullets) -> fetch real key from config.
    3. Always falls back to empty string rather than dummy-key to surface real errors.
    """
    if not _is_masked_key(req_key):
        return req_key.strip() if req_key else ""

    # Key is masked – look up stored real key
    if profile_id:
        stored = config_manager.get_profile(profile_id)
        if stored:
            real_key = stored.get("api_key", "")
            if real_key and not _is_masked_key(real_key):
                return real_key.strip()

    # Fallback: try active profile
    active = config_manager.get_active_profile()
    if active:
        real_key = active.get("api_key", "")
        if real_key and not _is_masked_key(real_key):
            return real_key.strip()

    return ""  # could not resolve — return empty so provider gives clear error

class ProfileSaveRequest(BaseModel):
    id: Optional[str] = None
    name: str
    api_key: Optional[str] = ""
    base_url: str
    model_name: Optional[str] = ""
    api_format: Optional[str] = "openai"

class ProfileSelectRequest(BaseModel):
    id: str

class ModelsFetchRequest(BaseModel):
    profile_id: Optional[str] = None
    api_key: str
    base_url: str
    api_format: Optional[str] = "openai"

@router.get("/api/profiles")
def get_profiles():
    return config_manager.list_profiles(mask_keys=True)

@router.post("/api/profiles")
def save_profile(profile: ProfileSaveRequest):
    try:
        logger.info(f"save_profile: name={profile.name!r}, base_url={profile.base_url!r}, has_key={bool(profile.api_key)}, fmt={profile.api_format}")
        data = profile.model_dump()
        # Ensure model_name and api_key are never None
        data["api_key"] = data.get("api_key") or ""
        data["model_name"] = data.get("model_name") or ""
        saved = config_manager.save_profile(data)
        logger.info(f"save_profile: OK, profile id={saved.get('id')}")
        return {"success": True, "profile": saved}
    except Exception as e:
        logger.error(f"save_profile FAILED: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/profiles/active")
def set_active_profile(req: ProfileSelectRequest):
    try:
        config_manager.set_active_profile(req.id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: str):
    try:
        config_manager.delete_profile(profile_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

from ..adapters.provider_adapter import OpenAICompatibleAdapter, DynamicModelProfile

@router.post("/api/models/fetch")
async def fetch_models(req: ModelsFetchRequest):
    api_key = _resolve_api_key(req.api_key, req.profile_id)
    logger.info(f"fetch_models: resolved key present={bool(api_key)}, url={req.base_url[:40] if req.base_url else ''}")

    provider_name = "AI Provider"
    if req.profile_id:
        stored = config_manager.get_profile(req.profile_id)
        if stored and stored.get("name"):
            provider_name = stored.get("name")

    adapter = OpenAICompatibleAdapter(
        provider_id=req.profile_id or "custom",
        name=provider_name,
        base_url=req.base_url,
        api_key=api_key
    )

    discovered_profiles = await adapter.list_models()
    model_ids = [m.model_id for m in discovered_profiles]
    metadata_list = [m.model_dump() for m in discovered_profiles]

    return {
        "success": len(discovered_profiles) > 0,
        "models": model_ids,
        "metadata": metadata_list,
        "message": "Discovered models dynamically from provider endpoint" if len(discovered_profiles) > 0 else "Not provided by provider"
    }


@router.get("/api/models/metadata")
async def get_model_info(model_id: str, provider: Optional[str] = None):
    adapter = OpenAICompatibleAdapter(
        provider_id="temp",
        name=provider or "AI Provider",
        base_url="https://api.openai.com/v1"
    )
    meta = await adapter.get_model_metadata(model_id)
    return meta.model_dump()


@router.get("/api/providers/dashboard")
async def get_providers_dashboard():
    """Return configured providers, API connection status, discovered models, and observed usage stats."""
    profiles = config_manager.list_profiles(mask_keys=True)
    active_profile = config_manager.get_active_profile()
    
    dashboard_profiles = []
    for p in profiles.get("profiles", []):
        p_name = p.get("name", "Provider")
        p_model = p.get("model_name") or "default"
        p_url = p.get("base_url") or ""
        real_key = _resolve_api_key(p.get("api_key", ""), p.get("id"))
        
        adapter = OpenAICompatibleAdapter(
            provider_id=p.get("id", ""),
            name=p_name,
            base_url=p_url,
            api_key=real_key
        )

        is_connected = await adapter.connect() if p_url else False
        meta = await adapter.get_model_metadata(p_model)

        dashboard_profiles.append({
            "id": p.get("id"),
            "name": p_name,
            "base_url": p_url,
            "api_format": p.get("api_format", "openai"),
            "model_name": p_model,
            "is_active": p.get("id") == active_profile.get("id") if active_profile else False,
            "api_status": adapter.status if p_url else "Unconfigured",
            "has_key": bool(real_key),
            "model_metadata": meta.model_dump(),
            "rpm_limit": meta.rpm_limit,
            "tpm_limit": meta.tpm_limit,
            "metadata_source": meta.metadata_source,
        })
        
    return {
        "success": True,
        "providers": dashboard_profiles,
        "active_provider_id": active_profile.get("id") if active_profile else None
    }




@router.post("/api/test-connection")
async def test_connection(profile: ProfileSaveRequest):
    try:
        key = _resolve_api_key(profile.api_key, profile.id)
        url = profile.base_url
        model = profile.model_name
        url_l = (url or "").lower()
        model_l = (model or "").lower()
        logger.info(f"test_connection: key_present={bool(key)}, url={url[:40] if url else ''}, fmt={profile.api_format}")
                
        fmt = (profile.api_format or "").lower()
        if not key and fmt not in ("ollama", "other"):
            return {"success": False, "message": "No API key found. Please save the profile with a valid API key first, then test connection."}

        if fmt == "anthropic" or "anthropic.com" in url_l or "claude" in model_l:
            from anthropic import AsyncAnthropic
            base_url_val = url if (url and "api.anthropic.com" not in url) else None
            client = AsyncAnthropic(api_key=key, base_url=base_url_val)
            await client.messages.create(
                model=model or "claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        elif (fmt == "google" or "generativelanguage.googleapis.com" in url_l) and "openai" not in url_l:
            # Use native Google Gemini API via urllib
            m_name = model or "gemini-1.5-flash"
            model_path = m_name if m_name.startswith("models/") else f"models/{m_name}"
            test_url = f"{url.rstrip('/')}/{model_path}:generateContent" if url else f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
            test_url += f"?key={key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 1}
            }).encode("utf-8")
            import ssl
            ctx = ssl._create_unverified_context()
            req_obj = urllib.request.Request(
                test_url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req_obj, timeout=10, context=ctx) as resp:
                resp.read()
        else:
            from openai import AsyncOpenAI
            base_url_val = url if url else "https://api.openai.com/v1"
            # For local providers (ollama, lmstudio, etc.) allow empty key
            effective_key = key or "local"
            client = AsyncOpenAI(api_key=effective_key, base_url=base_url_val)
            await client.chat.completions.create(
                model=model or "gpt-4o",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        return {"success": True, "message": "Connection succeeded"}
    except Exception as e:
        return {"success": False, "message": str(e)}
