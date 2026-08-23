import json
from redis_workers.client.connection import get_redis_client

STREAM_KEY = "rideshield:telemetry"

def publish_telemetry_batch(payload: dict) -> str:
    """
    Validates, serializes, and publishes a telemetry batch payload to the Redis stream.

    Args:
        payload (dict): The telemetry batch payload containing shift_id, batch_sequence, and samples.

    Returns:
        str: The Redis-generated stream entry ID.
    """
    # 1. Validate payload against required fields
    required_keys = {"shift_id", "batch_sequence", "samples"}
    if not required_keys.issubset(payload.keys()):
        raise ValueError(f"Payload missing required keys. Expected at least: {required_keys}")

    if not isinstance(payload["samples"], list) or len(payload["samples"]) == 0:
        raise ValueError("Payload 'samples' must be a non-empty list")

    # 2. Serialize structured payload safely
    try:
        json_payload = json.dumps(payload)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Payload could not be serialized to JSON: {e}")

    # 3. XADD to rideshield:telemetry
    client = get_redis_client()
    entry_id = client.xadd(STREAM_KEY, {"data": json_payload})

    # 4. Return the Redis-generated stream entry ID
    return entry_id
