import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import decimal
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import app.core.config  # noqa: F401 — triggers load_dotenv before db.core.session
from db.core.session import SessionLocal
from db.models.user import User
from db.models.shift import Shift
from db.models.shift_behaviour_summary import ShiftBehaviourSummary
from db.models.rider_behaviour_profile import RiderBehaviourProfile
from db.models.enums import UserRole, ShiftStatus
from app.services import rider_behaviour_profile_service
from app.services import rider_behaviour_risk_service as svc


@pytest.fixture
def test_rider():
    db = SessionLocal()
    rand_id = uuid.uuid4()
    rand_str = str(rand_id.int)[:8]
    user = User(
        id=rand_id,
        email=f"test_rbr_service_{rand_str}@example.com",
        phone_number=f"+1994{rand_str}",
        hashed_password="hashed_test_pass",
        full_name="Test RBR Service Rider",
        role=UserRole.RIDER,
        wallet_balance=500.0,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    try:
        db.query(RiderBehaviourProfile).filter(RiderBehaviourProfile.rider_id == user.id).delete()
        db.query(ShiftBehaviourSummary).filter(ShiftBehaviourSummary.rider_id == user.id).delete()
        db.query(Shift).filter(Shift.rider_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _make_shift(rider_id):
    db = SessionLocal()
    shift = Shift(
        rider_id=rider_id, status=ShiftStatus.COMPLETED,
        start_time=datetime.now(timezone.utc) - timedelta(hours=1),
        end_time=datetime.now(timezone.utc), premium_amount=5.0,
        policy_number=f"POL-RBRSVC-{uuid.uuid4().hex[:8].upper()}", distance_km=5.0,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    shift_id = shift.id
    db.close()
    return shift_id


def _insert_summary(rider_id, shift_id, created_at, hard_braking_rate=2.0):
    db = SessionLocal()
    db.add(ShiftBehaviourSummary(
        shift_id=shift_id, rider_id=rider_id,
        duration_seconds=600, distance_km=5.0, sample_count=50,
        average_speed=30.0, max_speed=45.0,
        hard_braking_count=2, hard_acceleration_count=1, overspeeding_count=0, sharp_turn_count=1,
        hard_braking_rate=hard_braking_rate, hard_acceleration_rate=1.0,
        overspeeding_rate=0.5, sharp_turn_rate=1.0,
        max_g=1.4, accel_std=0.2, jerk_mean=0.1,
        sampling_density=5.0, data_quality_score=0.9, is_valid=True,
        created_at=created_at,
    ))
    db.commit()
    db.close()


def _real_profile(rider_id, n_shifts=6):
    for i in range(n_shifts):
        shift_id = _make_shift(rider_id)
        _insert_summary(rider_id, shift_id, datetime.now(timezone.utc) - timedelta(hours=i))
    db = SessionLocal()
    profile = rider_behaviour_profile_service.rebuild_rider_profile(db, rider_id)
    db.commit()
    db.refresh(profile)
    db.close()
    return profile


class TestColdStart:
    def test_none_profile_returns_cold_start(self):
        result = svc.assess_rider_risk(None)
        assert result.is_cold_start is True
        assert result.risk_score is None
        assert result.source == "baseline_fallback"
        assert result.scoring_method == "cold_start"


class TestDecimalSafetyWithRealOrmProfile:
    """The exact test category that caught a real bug in Phase 2 and was
    proactively guarded against here — verify the guard actually works
    against a real, Decimal-typed ORM row, not just plain-float fixtures."""

    def test_real_orm_profile_has_decimal_fields(self, test_rider):
        profile = _real_profile(test_rider.id)
        assert isinstance(profile.overall_behaviour_score, decimal.Decimal)
        assert isinstance(profile.recent_max_g, decimal.Decimal)

    def test_assess_rider_risk_does_not_crash_on_real_orm_profile(self, test_rider):
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)  # must not raise
        assert result.risk_score is not None
        assert 0.0 <= result.risk_score <= 100.0

    def test_result_fields_are_plain_floats(self, test_rider):
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert isinstance(result.risk_score, float)
        assert isinstance(result.confidence, float)


class TestMlAvailablePath:
    def test_uses_xgboost_when_available(self, test_rider):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "xgboost"
        assert result.scoring_method == "xgboost"
        assert result.model_version

    def test_xgboost_confidence_and_band_come_from_baseline_context(self, test_rider, monkeypatch):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert 0.0 <= result.confidence <= 1.0
        assert result.risk_band in ("VERY_LOW", "LOW", "MODERATE", "HIGH", "VERY_HIGH")


class TestFallbackToBaseline:
    def test_ml_reported_unavailable_falls_back(self, test_rider, monkeypatch):
        monkeypatch.setattr(svc, "is_ml_available", lambda: False)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "baseline_fallback"
        assert result.scoring_method == "deterministic_baseline"
        assert result.risk_score is not None

    def test_missing_model_file_falls_back(self, test_rider, monkeypatch, tmp_path):
        from behaviour_risk_engine import model_config as brmcfg
        monkeypatch.setattr(brmcfg, "MODEL_PATH", tmp_path / "does_not_exist.json")
        monkeypatch.setattr(svc, "_booster", None)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "baseline_fallback"
        assert result.risk_score is not None

    def test_corrupted_model_file_falls_back(self, test_rider, monkeypatch, tmp_path):
        corrupted = tmp_path / "corrupted.json"
        corrupted.write_text("this is not a valid xgboost model file")
        from behaviour_risk_engine import model_config as brmcfg
        monkeypatch.setattr(brmcfg, "MODEL_PATH", corrupted)
        monkeypatch.setattr(svc, "_booster", None)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "baseline_fallback"
        assert result.risk_score is not None

    def test_prediction_exception_falls_back(self, test_rider, monkeypatch):
        # Simulates the model loading fine but throwing during predict —
        # the exact "single point of failure" scenario this exists to
        # protect against.
        monkeypatch.setattr(svc, "is_ml_available", lambda: True)

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated inference failure")

        monkeypatch.setattr(svc, "predict_calibrated_from_features", _boom)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "baseline_fallback"
        assert result.risk_score is not None

    def test_invalid_feature_extraction_falls_back(self, test_rider, monkeypatch):
        monkeypatch.setattr(svc, "is_ml_available", lambda: True)

        def _boom(profile):
            raise ValueError("simulated bad feature extraction")

        monkeypatch.setattr(svc, "_profile_to_features", _boom)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "baseline_fallback"
        assert result.risk_score is not None


class TestModelVersionPresent:
    def test_baseline_fallback_reports_a_model_version(self, test_rider, monkeypatch):
        monkeypatch.setattr(svc, "is_ml_available", lambda: False)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.model_version


class TestIsolationFromCrashMlEngine:
    def test_service_does_not_import_ml_incident_engine(self):
        import ast
        with open(svc.__file__, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        assert not any("ml_incident_engine" in m for m in imported_modules)


class TestPhase5CalibrationIntegration:
    """Phase 5: the service calls predict_calibrated_from_features(), which
    internally degrades to the raw XGBoost prediction whenever no
    calibration artifact has been deployed (the normal state whenever
    calibration hasn't beaten the raw model's test RMSE — see
    calibrate_and_evaluate.py's pre-registered deploy rule). These tests
    verify that degradation is invisible to callers of assess_rider_risk():
    the ML path is used regardless of whether calibration is active."""

    def test_scoring_method_is_xgboost_or_xgboost_calibrated_when_ml_available(self, test_rider):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "xgboost"
        assert result.scoring_method in ("xgboost", "xgboost_calibrated")

    def test_missing_calibration_artifact_still_uses_xgboost_not_baseline(self, test_rider, monkeypatch, tmp_path):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        from behaviour_risk_engine import model_config as brmcfg
        monkeypatch.setattr(brmcfg, "CALIBRATION_PATH", tmp_path / "does_not_exist.json")
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        # Missing calibration is a normal state (calibration only deploys
        # when it beats raw RMSE) — must NOT trigger the baseline fallback.
        assert result.source == "xgboost"
        assert result.scoring_method == "xgboost"
        assert result.model_version  # the raw (non-"-calibrated") version

    def test_corrupted_calibration_artifact_degrades_to_raw_not_baseline(self, test_rider, monkeypatch, tmp_path):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        from behaviour_risk_engine import model_config as brmcfg
        corrupted = tmp_path / "corrupted_calibration.json"
        corrupted.write_text("not valid json {{{")
        monkeypatch.setattr(brmcfg, "CALIBRATION_PATH", corrupted)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "xgboost"
        assert result.scoring_method == "xgboost"

    def test_valid_calibration_artifact_is_used_and_reflected_in_scoring_method(self, test_rider, monkeypatch, tmp_path):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        from behaviour_risk_engine import model_config as brmcfg, calibration as calib
        cal_path = tmp_path / "valid_calibration.json"
        calib.save_calibration({"x_thresholds": [0.0, 50.0, 100.0], "y_thresholds": [0.0, 50.0, 100.0]}, cal_path)
        monkeypatch.setattr(brmcfg, "CALIBRATION_PATH", cal_path)
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert result.source == "xgboost"
        assert result.scoring_method == "xgboost_calibrated"
        assert result.model_version == brmcfg.CALIBRATED_MODEL_VERSION

    def test_result_risk_score_always_clamped_to_0_100(self, test_rider):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        profile = _real_profile(test_rider.id)
        result = svc.assess_rider_risk(profile)
        assert 0.0 <= result.risk_score <= 100.0

    def test_deterministic_for_same_profile(self, test_rider):
        if not svc.is_ml_available():
            pytest.skip("No trained behaviour-risk model artifact present in this environment")
        profile = _real_profile(test_rider.id)
        r1 = svc.assess_rider_risk(profile)
        r2 = svc.assess_rider_risk(profile)
        assert r1.risk_score == r2.risk_score
        assert r1.scoring_method == r2.scoring_method
