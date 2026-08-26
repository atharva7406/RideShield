import uuid
from datetime import datetime, timezone
import pytest
from app.api.claims import haversine_distance

def test_haversine_distance():
    # Mumbai to Thane (approx 20-25 km)
    lat1, lon1 = 19.0760, 72.8777
    lat2, lon2 = 19.2183, 72.9781
    dist = haversine_distance(lat1, lon1, lat2, lon2)
    assert 15.0 <= dist <= 30.0

    # Same location should be 0
    assert haversine_distance(lat1, lon1, lat1, lon1) == 0.0
