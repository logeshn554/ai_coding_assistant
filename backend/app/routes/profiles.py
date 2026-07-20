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
    """Returns True if the API key string is empty or a masked placeholder."""
    if not key or not key.strip():
        return True
    return any(c in key for c in ("\u2022", "...", "*"))

class ProfileSaveRequest(BaseModel):
    id: Optional[str] = None
    name: str
    api_key: str
    base_url: str
    model_name: str
    api_format: str

class ProfileSelectRequest(BaseModel):
    id: str

class ModelsFetchRequest(BaseModel):
    profile_id: Optional[str] = None
    api_key: str
    base_url: str
    api_format: str

@router.get("/api/profiles")
def get_profiles():
    return config_manager.list_profiles(mask_keys=True)

@router.post("/api/profiles")
def save_profile(profile: ProfileSaveRequest):
    try:
        saved = config_manager.save_profile(profile.model_dump())
        return {"success": True, "profile": saved}
    except Exception as e:
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
def fetch_available_models(req: ModelsFetchRequest):
    api_key = req.api_key.strip()
    if _is_masked_key(api_key) and req.profile_id:
        profiles = config_manager.list_profiles(mask_keys=False).get("profiles", [])
        matched = next((p for p in profiles if p.get("id") == req.profile_id), None)
        if matched:
            api_key = matched.get("api_key", "").strip()

    if not api_key:
        return {"success": False, "models": []}

    try:
        url = req.base_url.strip()
        
        if req.api_format == "openai":
            if not url.endswith("/models"):
                url = url.rstrip("/") + "/models"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        elif req.api_format == "google":
            if "openai" in url.lower():
                if not url.endswith("/models"):
                    url = url.rstrip("/") + "/models"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0"
                }
            else:
                if not url or "generativelanguage.googleapis.com" in url:
                    url = "https://generativelanguage.googleapis.com/v1beta/models"
                else:
                    if not url.endswith("/models"):
                        url = url.rstrip("/") + "/models"
                headers = {
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0"
                }
        else:  # anthropic
            if not url.endswith("/models"):
                url = url.rstrip("/") + "/models"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }

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
        fmt = profile.api_format
        key = profile.api_key
        url = profile.base_url
        model = profile.model_name

        # If API key is masked or missing, retrieve the real key from the keyring.
        # Try the profile's own ID first; fall back to the active profile.
        if _is_masked_key(key):
            saved = None
            if profile.id:
                saved = config_manager.get_profile(profile.id)
            if not saved or _is_masked_key(saved.get("api_key", "")):
                saved = config_manager.get_active_profile()
            if saved and not _is_masked_key(saved.get("api_key", "")):
                key = saved["api_key"]
                
        if fmt == "anthropic":
            from anthropic import AsyncAnthropic
            base_url = url if (url and "api.anthropic.com" not in url) else None
            client = AsyncAnthropic(api_key=key, base_url=base_url)
            await client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        elif fmt == "google":
            if "openai" in url.lower():
                from openai import AsyncOpenAI
                base_url = url if url else "https://generativelanguage.googleapis.com/v1beta/openai/"
                client = AsyncOpenAI(api_key=key, base_url=base_url)
                await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
            else:
                # Use native Google Gemini API via urllib
                model_path = model if model.startswith("models/") else f"models/{model}"
                test_url = f"{url.rstrip('/')}/{model_path}:generateContent" if url else f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
                test_url += f"?key={key}"
                
                payload = json.dumps({
                    "contents": [{"parts": [{"text": "ping"}]}],
                    "generationConfig": {"maxOutputTokens": 1}
                }).encode("utf-8")
                
                req_obj = urllib.request.Request(
                    test_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req_obj, timeout=5) as resp:
                    resp.read()
        else:
            from openai import AsyncOpenAI
            base_url = url if url else None
            client = AsyncOpenAI(api_key=key, base_url=base_url)
            await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        return {"success": True, "message": "Connection succeeded"}
    except Exception as e:
        return {"success": False, "message": str(e)}
