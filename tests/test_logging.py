from app.core import logging as app_logging


def test_configure_logging_uses_expected_format(monkeypatch):
    captured = {}

    def fake_basic_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(app_logging.logging, "basicConfig", fake_basic_config)

    app_logging.configure_logging()

    assert captured["level"] == app_logging.logging.INFO
    assert "%(levelname)s" in captured["format"]
