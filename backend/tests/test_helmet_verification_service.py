import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import ast
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import app.core.config  # noqa: F401
from db.core.session import SessionLocal
from db.models.user import User
from db.models.helmet_verification import HelmetVerification
from db.models.enums import UserRole
from app.services import helmet_verification_service as svc


@pytest.fixture
def test_rider():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id, email=f"test_helmet_{rand_str}@example.com",
        phone_number=f"+1991{rand_str}", hashed_password="x",
        full_name="Test Helmet Rider", role=UserRole.RIDER, wallet_balance=500.0, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    try:
        db.query(HelmetVerification).filter(HelmetVerification.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class TestAcknowledgeHelmetSafety:
    def test_returns_a_passed_result(self):
        result = svc.acknowledge_helmet_safety()
        assert isinstance(result, svc.HelmetVerificationResult)
        assert result.helmet_worn is True
        assert result.confidence == 1.0
        assert result.model_version == svc.ACKNOWLEDGMENT_MODEL_VERSION

    def test_is_deterministic(self):
        # Unlike the removed ML-based checks, there's no model to run and
        # no way for two calls to disagree.
        first = svc.acknowledge_helmet_safety()
        second = svc.acknowledge_helmet_safety()
        assert first == second


class TestRecordAndConsume:
    def test_record_verification_persists_a_row(self, test_rider):
        db = SessionLocal()
        result = svc.HelmetVerificationResult(
            predicted_class="full_face_helmet", confidence=0.9, helmet_worn=True, model_version="test-v1",
        )
        record = svc.record_verification(db, test_rider.id, result)
        db.commit()
        db.refresh(record)
        assert record.id is not None
        assert record.helmet_worn is True
        assert record.consumed_at is None
        db.close()

    def test_get_usable_verification_finds_a_passed_unconsumed_recent_row(self, test_rider):
        db = SessionLocal()
        result = svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
        svc.record_verification(db, test_rider.id, result)
        db.commit()

        found = svc.get_usable_verification(db, test_rider.id)
        assert found is not None
        assert found.helmet_worn is True
        db.close()

    def test_get_usable_verification_ignores_failed_checks(self, test_rider):
        db = SessionLocal()
        result = svc.HelmetVerificationResult("no_helmet", 0.9, False, "test-v1")
        svc.record_verification(db, test_rider.id, result)
        db.commit()

        found = svc.get_usable_verification(db, test_rider.id)
        assert found is None
        db.close()

    def test_get_usable_verification_ignores_consumed_rows(self, test_rider):
        db = SessionLocal()
        result = svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
        record = svc.record_verification(db, test_rider.id, result)
        db.commit()
        svc.consume_verification(record, shift_id=None)
        db.commit()

        found = svc.get_usable_verification(db, test_rider.id)
        assert found is None
        db.close()

    def test_get_usable_verification_ignores_expired_rows(self, test_rider):
        db = SessionLocal()
        result = svc.HelmetVerificationResult("full_face_helmet", 0.95, True, "test-v1")
        record = svc.record_verification(db, test_rider.id, result)
        db.commit()
        # Backdate past the validity window.
        record.created_at = datetime.now(timezone.utc) - timedelta(
            minutes=svc.VERIFICATION_VALIDITY_MINUTES + 5
        )
        db.commit()

        found = svc.get_usable_verification(db, test_rider.id)
        assert found is None
        db.close()

    def test_get_usable_verification_prefers_most_recent(self, test_rider):
        db = SessionLocal()
        older = svc.record_verification(
            db, test_rider.id, svc.HelmetVerificationResult("full_face_helmet", 0.9, True, "test-v1")
        )
        db.commit()
        older.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.commit()

        newer = svc.record_verification(
            db, test_rider.id, svc.HelmetVerificationResult("half_face_helmet", 0.85, True, "test-v1")
        )
        db.commit()

        found = svc.get_usable_verification(db, test_rider.id)
        assert found.id == newer.id
        db.close()

    def test_consume_verification_stamps_shift_and_timestamp(self, test_rider):
        db = SessionLocal()
        record = svc.record_verification(
            db, test_rider.id, svc.HelmetVerificationResult("full_face_helmet", 0.9, True, "test-v1")
        )
        db.commit()
        fake_shift_id = uuid.uuid4()
        assert record.consumed_at is None
        svc.consume_verification(record, fake_shift_id)
        assert record.consumed_at is not None
        assert record.shift_id == fake_shift_id
        db.close()


class TestNoMlEngineImports:
    def test_service_imports_no_ml_engine_at_all(self):
        """The helmet gate is a checkbox acknowledgment now, not an ML
        classifier — this service shouldn't import ANY of this project's
        ML engines (ml_incident_engine, behaviour_risk_engine, or the
        now-deleted helmet_detection_engine)."""
        with open(svc.__file__, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert not any("ml_incident_engine" in m for m in imported_modules)
        assert not any("behaviour_risk_engine" in m for m in imported_modules)
        assert not any("helmet_detection_engine" in m for m in imported_modules)
