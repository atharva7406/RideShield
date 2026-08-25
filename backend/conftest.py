"""
Root pytest conftest.

Windows-only DLL load-order fix: onnxruntime's native extension
(onnxruntime_pybind11_state) must be imported before xgboost's native
extension is loaded into the same process, or onnxruntime's import fails
with "DLL load failed while importing onnxruntime_pybind11_state" — the
two packages ship conflicting copies of a shared native runtime, and
whichever loads first "wins". The real FastAPI app (main.py) happens to
import in an order that avoids this; pytest's test collection order
(ml_incident_engine/behaviour_risk_engine's tests, which pull in
xgboost, collected before helmet_detection_engine's tests, which pull in
onnxruntime) does not. Importing onnxruntime here, before pytest
collects anything else, makes test collection order-independent.
"""
try:
    import onnxruntime  # noqa: F401
except ImportError:
    pass
