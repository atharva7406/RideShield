import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import uuid
import asyncio
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from main import app
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.incident import Incident
from db.models.enums import UserRole, IncidentStatus, ShiftStatus
from app.core.config import settings
from app.services.whatsapp_service import send_whatsapp_message

client = TestClient(app)

@pytest.fixture(scope="module")
def test_rider_user():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    # We use a 10-digit number that starts with 9 for normalizing
    phone = f"+91999{rand_str[-7:]}"
    user = User(
        id=rand_id,
        email=f"test_whatsapp_{rand_str}@example.com",
        phone_number=phone,
        hashed_password="hashed_test_pass",
        full_name="Test WhatsApp Rider",
        role=UserRole.RIDER,
        wallet_balance=0.0,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    # Cleanup
    try:
        db.query(Incident).filter(Incident.rider_id == user.id).delete()
        db.query(Shift).filter(Shift.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_send_whatsapp_message_twilio_success(monkeypatch):
    # Configure mock Twilio credentials
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "ACmock_sid")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "mock_token")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+14155238886")

    # Mock response
    mock_response = AsyncMock()
    mock_response.status_code = 201
    mock_response.text = "Success"

    mock_post = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    success = asyncio.run(send_whatsapp_message("+919876543210", "YES"))
    assert success is True

    # Verify Twilio URL was hit with correct basic auth and form data
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "api.twilio.com" in args[0]
    assert kwargs["auth"] == ("ACmock_sid", "mock_token")
    assert kwargs["data"]["To"] == "whatsapp:+919876543210"
    assert kwargs["data"]["From"] == "whatsapp:+14155238886"
    # Verify sandbox optimization formatted the template body
    assert kwargs["data"]["Body"] == "Your RideShield safety verification code is YES (if safe) or HELP (for SOS)"


def test_send_whatsapp_message_mock_bypass():
    # If the recipient phone is a test phone number (+1555...), it should bypass both Twilio and Meta APIs and return True
    success = asyncio.run(send_whatsapp_message("+15551234567", "Test alert text"))
    assert success is True


def test_send_whatsapp_message_twilio_fail_meta_success(monkeypatch):
    # Configure credentials
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "ACmock_sid")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "mock_token")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "+14155238886")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "mock_phone_id")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "mock_access_token")

    # Mock responses
    mock_response_twilio = AsyncMock()
    mock_response_twilio.status_code = 500
    mock_response_twilio.text = "Twilio Server Error"

    mock_response_meta = AsyncMock()
    mock_response_meta.status_code = 200
    mock_response_meta.text = "Meta Success"

    call_count = 0
    async def mock_post(self, url, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if "api.twilio.com" in url:
            return mock_response_twilio
        elif "graph.facebook.com" in url:
            return mock_response_meta
        raise ValueError(f"Unexpected url {url}")

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    success = asyncio.run(send_whatsapp_message("+919876543210", "Test Body"))
    assert success is True
    # Should have called Twilio, failed, and then called Meta
    assert call_count == 2


def test_send_whatsapp_message_twilio_unconfigured_meta_success(monkeypatch):
    # Unconfigure Twilio
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", "")

    # Configure Meta
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "mock_phone_id")
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "mock_access_token")

    mock_response_meta = AsyncMock()
    mock_response_meta.status_code = 200
    mock_response_meta.text = "Meta Success"

    mock_post = AsyncMock(return_value=mock_response_meta)
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

    success = asyncio.run(send_whatsapp_message("+919876543210", "Test Body"))
    assert success is True

    # Should only call Meta API directly
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "graph.facebook.com" in args[0]


def test_twilio_webhook_incident_confirmation(test_rider_user, monkeypatch):
    db = SessionLocal()
    
    # 1. Create a test Shift for the rider (since incident shift_id is not-null)
    shift = Shift(
        id=uuid.uuid4(),
        rider_id=test_rider_user.id,
        status=ShiftStatus.ACTIVE,
        distance_km=0.0,
        premium_amount=0.0
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)

    # 2. Create a detected incident for the rider linked to the shift
    incident = Incident(
        id=uuid.uuid4(),
        shift_id=shift.id,
        rider_id=test_rider_user.id,
        status=IncidentStatus.DETECTED,
        detected_at=datetime.now(timezone.utc),
        peak_g_force=3.5,
        confidence_score=0.9,
        latitude=19.0760,
        longitude=72.8777
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    # Mock send_whatsapp_message to prevent outgoing HTTP calls
    mock_send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.api.whatsapp.send_whatsapp_message", mock_send)

    # 3. Call Twilio Webhook (representing rider saying OK)
    payload = {
        "From": f"whatsapp:{test_rider_user.phone_number}",
        "Body": "YES"
    }
    
    response = client.post("/api/whatsapp/twilio-webhook", data=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/xml")
    assert "<Response></Response>" in response.text

    # 4. Verify database updates
    db.refresh(incident)
    assert incident.status == IncidentStatus.FALSE_POSITIVE

    # Cleanup incident and shift
    db.query(Incident).filter(Incident.id == incident.id).delete()
    db.query(Shift).filter(Shift.id == shift.id).delete()
    db.commit()
    db.close()
