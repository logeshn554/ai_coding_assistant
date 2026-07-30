import os
import pytest
from agent_os.core.config import DictionaryConfig

def test_dictionary_config_get():
    cfg = DictionaryConfig({"port": 8080, "debug": True})
    assert cfg.get("port") == 8080
    assert cfg.get("debug") is True
    assert cfg.get("nonexistent", "default") == "default"

def test_dictionary_config_env_override():
    os.environ["OS_ENV_KEY"] = "from_env"
    try:
        cfg = DictionaryConfig({"OS_ENV_KEY": "from_dict"})
        assert cfg.get("OS_ENV_KEY") == "from_env"
    finally:
        del os.environ["OS_ENV_KEY"]

def test_dictionary_config_get_typed():
    cfg = DictionaryConfig({"port": "8080", "debug": "true", "ratio": "0.75"})
    assert cfg.get_typed(int, "port") == 8080
    assert cfg.get_typed(bool, "debug") is True
    assert cfg.get_typed(float, "ratio") == 0.75
    assert cfg.get_typed(str, "port") == "8080"

def test_dictionary_config_update():
    cfg = DictionaryConfig()
    cfg.update("theme", "dark")
    assert cfg.get("theme") == "dark"
