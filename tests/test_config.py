"""Tests for API key config resolution."""

import json
from pathlib import Path

from evds_mcp.config import resolve_api_key, CONFIG_PATH


def test_resolve_from_file(tmp_path, monkeypatch):
    """Key found in config file."""
    config_file = tmp_path / ".evds-mcp.json"
    config_file.write_text(json.dumps({"api_key": "test-key-123"}))
    monkeypatch.setattr("evds_mcp.config.CONFIG_PATH", config_file)
    monkeypatch.delenv("EVDS_API_KEY", raising=False)

    result = resolve_api_key()
    assert result == "test-key-123"


def test_resolve_from_env(tmp_path, monkeypatch):
    """No config file, key from env var."""
    config_file = tmp_path / ".evds-mcp.json"
    monkeypatch.setattr("evds_mcp.config.CONFIG_PATH", config_file)
    monkeypatch.setenv("EVDS_API_KEY", "env-key-456")

    result = resolve_api_key()
    assert result == "env-key-456"


def test_resolve_file_takes_precedence(tmp_path, monkeypatch):
    """Config file takes precedence over env var."""
    config_file = tmp_path / ".evds-mcp.json"
    config_file.write_text(json.dumps({"api_key": "file-key"}))
    monkeypatch.setattr("evds_mcp.config.CONFIG_PATH", config_file)
    monkeypatch.setenv("EVDS_API_KEY", "env-key")

    result = resolve_api_key()
    assert result == "file-key"


def test_resolve_missing_returns_none(tmp_path, monkeypatch):
    """No file, no env — returns None."""
    config_file = tmp_path / ".evds-mcp.json"
    monkeypatch.setattr("evds_mcp.config.CONFIG_PATH", config_file)
    monkeypatch.delenv("EVDS_API_KEY", raising=False)

    result = resolve_api_key()
    assert result is None


def test_resolve_empty_key_in_file(tmp_path, monkeypatch):
    """Config file exists but api_key is empty string."""
    config_file = tmp_path / ".evds-mcp.json"
    config_file.write_text(json.dumps({"api_key": ""}))
    monkeypatch.setattr("evds_mcp.config.CONFIG_PATH", config_file)
    monkeypatch.delenv("EVDS_API_KEY", raising=False)

    result = resolve_api_key()
    assert result is None


def test_resolve_malformed_json(tmp_path, monkeypatch):
    """Malformed JSON file — falls back to env."""
    config_file = tmp_path / ".evds-mcp.json"
    config_file.write_text("not json{{{")
    monkeypatch.setattr("evds_mcp.config.CONFIG_PATH", config_file)
    monkeypatch.setenv("EVDS_API_KEY", "env-fallback")

    result = resolve_api_key()
    assert result == "env-fallback"


def test_api_key_error_dict():
    """Error dict has required keys."""
    from evds_mcp.config import api_key_missing_error

    err = api_key_missing_error()
    assert err["hata"] is True
    assert err["kod"] == "API_KEY_EKSIK"
    assert "mesaj" in err
    assert "oneri" in err
