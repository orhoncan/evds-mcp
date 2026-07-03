"""API key resolution: EVDS_API_KEY env → ~/.evds-mcp.json → None."""

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".evds-mcp.json"


def resolve_api_key() -> Optional[str]:
    """Resolve API key. Environment variable wins over config file."""
    env_key = os.environ.get("EVDS_API_KEY", "")
    if env_key:
        return env_key

    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            key = data.get("api_key", "")
            if key:
                return key
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def api_key_missing_error() -> dict:
    """Return structured error dict when API key is missing."""
    return {
        "hata": True,
        "kod": "API_KEY_EKSIK",
        "mesaj": (
            'API key bulunamadı. ~/.evds-mcp.json dosyasına {"api_key": "KEY"} yazın '
            "veya EVDS_API_KEY ortam değişkenini tanımlayın."
        ),
        "oneri": "https://evds2.tcmb.gov.tr adresinden API key alabilirsiniz.",
    }
