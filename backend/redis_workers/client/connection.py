import os
import redis
from dotenv import load_dotenv

_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_backend_dir, "env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)
load_dotenv()

# Global connection pool cache to avoid creating a new pool for every request
_redis_pool = None

def get_redis_client() -> redis.Redis:
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
        _redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            decode_responses=True, # Automatically decode bytes to str
        )

    return redis.Redis(connection_pool=_redis_pool)
