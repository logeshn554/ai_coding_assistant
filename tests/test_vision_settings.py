import pytest
from backend.app.config import config_manager
from backend.app.vision import analyze_image, _extract_ocr_fallback

def test_image_analysis_mode_config():
    initial_mode = config_manager.get_image_analysis_mode()
    try:
        config_manager.set_image_analysis_mode("ocr")
        assert config_manager.get_image_analysis_mode() == "ocr"

        config_manager.set_image_analysis_mode("model")
        assert config_manager.get_image_analysis_mode() == "model"

        config_manager.set_image_analysis_mode("auto")
        assert config_manager.get_image_analysis_mode() == "auto"

        # Invalid mode fallback
        config_manager.set_image_analysis_mode("invalid_mode")
        assert config_manager.get_image_analysis_mode() == "auto"
    finally:
        config_manager.set_image_analysis_mode(initial_mode)

def test_secondary_agent_model_config():
    initial_model = config_manager.get_secondary_agent_model()
    try:
        config_manager.set_secondary_agent_model("gpt-4o-mini")
        assert config_manager.get_secondary_agent_model() == "gpt-4o-mini"
    finally:
        config_manager.set_secondary_agent_model(initial_model)

@pytest.mark.asyncio
async def test_analyze_image_ocr_mode():
    initial_mode = config_manager.get_image_analysis_mode()
    try:
        config_manager.set_image_analysis_mode("ocr")
        # Non-existent file test
        res = await analyze_image("non_existent_file.png")
        assert res.mode == "ocr"
        assert "[Image File Not Found" in res.text
    finally:
        config_manager.set_image_analysis_mode(initial_mode)
