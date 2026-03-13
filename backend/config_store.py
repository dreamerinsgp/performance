"""Config storage and validation for infra settings."""
import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(__file__).parent.parent / "config"
INFRA_FILE = CONFIG_DIR / "infra.json"
PERFTEST_FILE = CONFIG_DIR / "perftest.json"


def get_infra_config() -> Optional[dict]:
    """Load infra config from JSON file."""
    if not INFRA_FILE.exists():
        return None
    try:
        with open(INFRA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_infra_config(config: dict) -> bool:
    """Save infra config to JSON file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(INFRA_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


def get_redis_dsn(config: dict) -> str:
    """Build Redis connection string from config."""
    r = config.get("redis", {})
    host = r.get("host", "127.0.0.1")
    port = r.get("port", 6379)
    return f"{host}:{port}"


def get_perftest_config() -> Optional[dict]:
    """Load perftest config."""
    if not PERFTEST_FILE.exists():
        return None
    try:
        with open(PERFTEST_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_perftest_config(config: dict) -> bool:
    """Save perftest config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(PERFTEST_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


def get_mysql_dsn(config: dict) -> str:
    """Build MySQL DSN from config."""
    m = config.get("mysql", {})
    return (
        f"mysql://{m.get('user', 'root')}:{m.get('password', '')}"
        f"@{m.get('host', '127.0.0.1')}:{m.get('port', 3306)}/{m.get('database', 'dexs')}"
    )
