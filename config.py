import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
CACHE_FILE = BASE_DIR / "dividend_cache.json"

def load_env():
    """Load key-value pairs from .env file without external dependencies."""
    env_vars = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip().strip('"').strip("'")
    return env_vars

_env = load_env()

# Upstox Token
UPSTOX_TOKEN = os.environ.get("TOKEN") or _env.get("TOKEN", "")

# Cache expiry in seconds (default: 15 minutes)
CACHE_TTL = 900

# Server config
SERVER_PORT = 5000
SERVER_HOST = "127.0.0.1"
