import json
import os
import sys
from typing import Any, Dict


def _get_app_base_dir() -> str:
    """Return writable base dir for config (exe folder when frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_server_config_path() -> str:
    return os.path.join(_get_app_base_dir(), "server_config.json")


def _default_config() -> Dict[str, Any]:
    return {
        "unifi_api": {
            "api_url": "http://127.0.0.1:5001",
            "api_key": "",
        },
        "unifi_controller": {
            "url": "https://127.0.0.1:8443",
            "username": "admin",
            "password": "admin123",
            "site": "default",
            "verify_ssl": False,
            "ca_bundle": "",
        },
        "server": {
            "host": "0.0.0.0",
            "port": 5001,
            "allow_no_auth": True,
            "api_keys": [],
            "admin_api_keys": [],
            "allowed_sites": ["default"],
            "allowed_origins": [],
            "enable_hsts": False,
        },
    }


def load_server_config() -> Dict[str, Any]:
    """Load server_config.json with safe defaults."""
    config = _default_config()
    path = get_server_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                # shallow merge
                for k, v in loaded.items():
                    if isinstance(v, dict) and isinstance(config.get(k), dict):
                        config[k].update(v)
                    else:
                        config[k] = v
        except Exception:
            pass
    return config
