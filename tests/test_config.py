"""API key çözümleme testleri — env değişkeni config dosyasını ezmeli."""

import json

import evds_mcp.config as config


def test_env_config_dosyasini_ezer(tmp_path, monkeypatch):
    cfg = tmp_path / ".evds-mcp.json"
    cfg.write_text(json.dumps({"api_key": "dosya-key"}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    monkeypatch.setenv("EVDS_API_KEY", "env-key")
    assert config.resolve_api_key() == "env-key"


def test_env_yoksa_dosya(tmp_path, monkeypatch):
    cfg = tmp_path / ".evds-mcp.json"
    cfg.write_text(json.dumps({"api_key": "dosya-key"}), encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    monkeypatch.delenv("EVDS_API_KEY", raising=False)
    assert config.resolve_api_key() == "dosya-key"


def test_hicbiri_yoksa_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "yok.json")
    monkeypatch.delenv("EVDS_API_KEY", raising=False)
    assert config.resolve_api_key() is None


def test_bozuk_json_sessizce_gecilir(tmp_path, monkeypatch):
    cfg = tmp_path / ".evds-mcp.json"
    cfg.write_text("{bozuk", encoding="utf-8")
    monkeypatch.setattr(config, "CONFIG_PATH", cfg)
    monkeypatch.delenv("EVDS_API_KEY", raising=False)
    assert config.resolve_api_key() is None
