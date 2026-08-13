import pytest
from backend.app.config import Settings

def test_production_fails_on_sqlite():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="sqlite:///devpilot.db",
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "PostgreSQL is required in production" in str(excinfo.value)

def test_production_fails_on_debug():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            DEBUG=True,
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "DEBUG mode is forbidden" in str(excinfo.value)

def test_production_fails_on_disabled_sandbox():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            USE_SANDBOX=False,
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "Sandbox environment is mandatory" in str(excinfo.value)

def test_production_fails_on_wildcard_cors():
    with pytest.raises(RuntimeError) as excinfo:
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            USE_SANDBOX=True,
            CORS_ORIGINS=["*"],
            JWT_SECRET="super-secret-production-jwt-key-xyz"
        )
    assert "Wildcard CORS origins are forbidden" in str(excinfo.value)

def test_production_succeeds_on_valid_setup():
    settings = Settings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql://user:pass@localhost/db",
        USE_SANDBOX=True,
        CORS_ORIGINS=["http://localhost:3000"],
        JWT_SECRET="super-secret-production-jwt-key-xyz"
    )
    assert settings.ENVIRONMENT == "production"
    assert settings.DATABASE_URL == "postgresql://user:pass@localhost/db"
