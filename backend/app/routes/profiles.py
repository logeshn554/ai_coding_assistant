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

@router.post("/api/models/fetch")
def fetch_models(req: ModelsFetchRequest):
    api_key = _resolve_api_key(req.api_key, req.profile_id)
    logger.info(f"fetch_models: resolved key present={bool(api_key)}, url={req.base_url[:40] if req.base_url else ''}")

    try:
        url = req.base_url.strip()
        url_l = url.lower()
        
        if "anthropic.com" in url_l:
            if not url.endswith("/models"):
                url = url.rstrip("/") + "/models"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        else:  # Generic OpenAI-compatible provider (OpenAI, Groq, Ollama, DeepSeek, Gemini, etc.)
            if not url.endswith("/models"):
                url = url.rstrip("/") + "/models"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                models = []
                if "data" in data and isinstance(data["data"], list):
                    models = [m.get("id") for m in data["data"] if m.get("id")]
                elif "models" in data and isinstance(data["models"], list):
                    for m in data["models"]:
                        if m.get("name"):
                            name = m.get("name")
                            if name.startswith("models/"):
                                name = name.replace("models/", "", 1)
                            models.append(name)
                        elif m.get("id"):
                            models.append(m.get("id"))
                elif isinstance(data, list):
                    models = data
                
                models = sorted(list(set(filter(None, models))))
                return {"success": True, "models": models}
        except Exception as e:
            logger.warning(f"Failed to fetch models from API: {str(e)}")
            return {"success": False, "models": [], "message": f"Offline presets: {e}"}
    except Exception as e:
        logger.warning(f"Error fetching models: {str(e)}")
        return {"success": False, "models": [], "message": str(e)}



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
