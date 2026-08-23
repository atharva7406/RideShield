import os
import sys
from dotenv import load_dotenv

# --- SHADOWING MITIGATION ---
def get_external_redis():
    """
    Robustly imports the external PyPI 'redis' package by temporarily
    hiding any local 'redis' modules from sys.modules and removing
    paths containing the local 'redis' package from sys.path.
    """
    if "ext_redis" in sys.modules:
        return sys.modules["ext_redis"]

    original_path = list(sys.path)

    # Remove paths containing local 'redis' package while strictly preserving site-packages / dist-packages
    filtered_path = []
    for p in original_path:
        if not p:
            continue
        p_lower = p.lower()
        if "site-packages" in p_lower or "dist-packages" in p_lower:
            filtered_path.append(p)
        elif os.path.exists(os.path.join(p, "redis", "__init__.py")):
            continue
        else:
            filtered_path.append(p)

    sys.path = filtered_path

    hidden = {}
    for k in list(sys.modules.keys()):
        if k == "redis" or k.startswith("redis."):
            hidden[k] = sys.modules.pop(k)

    try:
        import redis as _ext_redis
        sys.modules["ext_redis"] = _ext_redis
    finally:
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
