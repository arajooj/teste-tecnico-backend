from app.core.config import get_settings


def test_settings_defaults(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    settings = get_settings()

    assert settings.app_name == "Teste Tecnico Backend API"
    assert settings.environment == "development"
    assert settings.api_port == 8000
    assert settings.webhook_callback_base_url == "http://host.docker.internal:8000"


def test_settings_reads_environment(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_NAME", "Custom API")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("WEBHOOK_CALLBACK_BASE_URL", "http://api.local")

    settings = get_settings()

    assert settings.app_name == "Custom API"
    assert settings.environment == "test"
    assert settings.webhook_callback_base_url == "http://api.local"

    get_settings.cache_clear()
