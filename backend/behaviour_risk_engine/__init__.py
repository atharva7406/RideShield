"""
RideShield Behaviour Risk Engine — Phase 4.

Offline, standalone module for training and evaluating an XGBoost
regression model that predicts a rider's continuous 0-100 behaviour risk
score from their RiderBehaviourProfile. Deliberately separate from
backend/ml_incident_engine/ (the crash-detection engine) — different
system, different data shape, different target, no shared code. Kept
separate from app/services/ too, matching ml_incident_engine's own
"offline dev pipeline vs. production backend" boundary — see
app/services/rider_behaviour_risk_service.py for the one file that bridges
the two.
"""
