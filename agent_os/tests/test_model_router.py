import pytest
import asyncio
from agent_os.providers.model_router import ModelRouter, RateLimitError, ProviderError

@pytest.mark.anyio
async def test_model_router_capability_routing():
    router = ModelRouter()
    
    # 1. Routing to Anthropic/Claude
    res_claude = await router.generate(prompt="hello", model_name="claude-3-5-sonnet")
    assert "[ANTHROPIC RESPONSE]" in res_claude

    # 2. Routing to OpenAI/GPT
    res_gpt = await router.generate(prompt="hello", model_name="gpt-4o")
    assert "[OPENAI RESPONSE]" in res_gpt

@pytest.mark.anyio
async def test_model_router_fallback_and_health():
    router = ModelRouter()
    assert router.health_check("anthropic") is True

    # Disable Anthropic (simulate primary provider outage)
    router.set_provider_health("anthropic", False)
    assert router.health_check("anthropic") is False

    # Calling Claude now should automatically fall back to OpenAI (the next best provider)
    res_fallback = await router.generate(prompt="hello", model_name="claude-3-5-sonnet")
    assert "[OPENAI RESPONSE]" in res_fallback

@pytest.mark.anyio
async def test_model_router_rate_limiting():
    # Strict limit: 2 requests per minute
    router = ModelRouter(rpm_limit=2, max_retries=1, base_delay=0.001)

    # 1st request -> OK
    await router.generate(prompt="req1", model_name="openai")
    # 2nd request -> OK
    await router.generate(prompt="req2", model_name="openai")

    # 3rd request should fail with ProviderError containing RateLimitError because all providers will rate-limit
    with pytest.raises(ProviderError) as exc_info:
        await router.generate(prompt="req3", model_name="openai")
    assert "Rate limit exceeded" in str(exc_info.value)

@pytest.mark.anyio
async def test_model_router_streaming():
    router = ModelRouter()
    
    chunks = []
    async for chunk in router.stream(prompt="run build", model_name="gemini"):
        chunks.append(chunk)

    full_response = "".join(chunks)
    assert "[GEMINI RESPONSE]" in full_response
    assert "run build" in full_response
