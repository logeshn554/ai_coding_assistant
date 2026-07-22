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
def fetch_models(req: ModelsFetchRequest):
    api_key = req.api_key.strip()
    if _is_masked_key(api_key):
        profiles = config_manager.list_profiles(mask_keys=False).get("profiles", [])
        matched = next((p for p in profiles if p.get("id") == req.profile_id), None)
        if not matched:
            matched = config_manager.get_active_profile()
        if matched:
            api_key = matched.get("api_key", "").strip()

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
        key = profile.api_key
        url = profile.base_url
        model = profile.model_name
        url_l = (url or "").lower()
        model_l = (model or "").lower()

        # If API key is masked or missing, retrieve the real key from the keyring.
        if _is_masked_key(key):
            saved = None
            if profile.id:
                saved = config_manager.get_profile(profile.id)
            if not saved or _is_masked_key(saved.get("api_key", "")):
                saved = config_manager.get_active_profile()
            if saved and not _is_masked_key(saved.get("api_key", "")):
                key = saved["api_key"]
                
        if "anthropic.com" in url_l or "claude" in model_l:
            from anthropic import AsyncAnthropic
            base_url = url if (url and "api.anthropic.com" not in url) else None
            client = AsyncAnthropic(api_key=key, base_url=base_url)
            await client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        elif "generativelanguage.googleapis.com" in url_l and "openai" not in url_l:
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
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req_obj, timeout=5) as resp:
                resp.read()
        else:
            from openai import AsyncOpenAI
            base_url = url if url else "https://api.openai.com/v1"
            client = AsyncOpenAI(api_key=key, base_url=base_url)
            await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
        return {"success": True, "message": "Connection succeeded"}
    except Exception as e:
        return {"success": False, "message": str(e)}
