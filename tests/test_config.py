from app.core.config import get_settings


def test_settings_defaults(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    settings = get_settings()

    assert settings.app_name == "Teste Tecnico Backend API"
    assert settings.environment == "development"
    assert settings.api_port == 8000


def test_settings_reads_environment(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_NAME", "Custom API")
    monkeypatch.setenv("ENVIRONMENT", "test")

    settings = get_settings()

    assert settings.app_name == "Custom API"
    assert settings.environment == "test"

    get_settings.cache_clear()
