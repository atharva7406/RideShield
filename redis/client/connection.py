import os
import sys
from dotenv import load_dotenv

# --- SHADOWING MITIGATION ---
def get_external_redis():
    """
    Robustly imports the external PyPI 'redis' package by temporarily
    hiding any local 'redis' modules from sys.modules and removing the
    project root from sys.path.
    """
    if "ext_redis" in sys.modules:
        return sys.modules["ext_redis"]

    original_path = list(sys.path)
    sys.path = [p for p in sys.path if "RideShield" not in p and p != ""]

    hidden = {}
    for k in list(sys.modules.keys()):
        if k == "redis" or k.startswith("redis."):
            hidden[k] = sys.modules.pop(k)

    import redis as _ext_redis
    sys.modules["ext_redis"] = _ext_redis

    for k, v in hidden.items():
        sys.modules[k] = v
    sys.path = original_path

    return _ext_redis

ext_redis = get_external_redis()
# -----------------------------

# Load environment variables from .env
load_dotenv()

# Global connection pool cache to avoid creating a new pool for every request
_redis_pool = None

def get_redis_client() -> ext_redis.Redis:
    """
    Returns a configured Redis client instance using the REDIS_URL from the environment.
    This uses a connection pool for efficiency and handles Upstash TLS requirements via the rediss:// scheme.
    """
    global _redis_pool

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable is not set")

    if _redis_pool is None:
        # Create a single connection pool
        # For Upstash (which uses TLS), standard 'rediss://' scheme works out of the box.
        _redis_pool = ext_redis.ConnectionPool.from_url(
            redis_url,
            decode_responses=True, # Automatically decode bytes to str
        )

    return ext_redis.Redis(connection_pool=_redis_pool)
