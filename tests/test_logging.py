import logging
from logging.handlers import RotatingFileHandler
from types import SimpleNamespace

from localdictate.logging_setup import configure_logging


def test_windowed_app_logs_without_a_console(tmp_path, monkeypatch):
    import localdictate.logging_setup as module
    logger = logging.Logger("windowed-test")
    monkeypatch.setattr(module, "logging", SimpleNamespace(getLogger=lambda name: logger,
                                                          INFO=logging.INFO,
                                                          Formatter=logging.Formatter))
    monkeypatch.setattr(module, "sys", SimpleNamespace(stderr=None))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    configured = configure_logging()
    try:
        assert len(configured.handlers) == 1
        assert isinstance(configured.handlers[0], RotatingFileHandler)
        configured.info("windowed logging works")
        assert "windowed logging works" in (tmp_path / "ParrotFlow/logs/parrot-flow.log").read_text()
    finally:
        for handler in configured.handlers:
            handler.close()
