"""
Shared constants for the ML Incident Engine's data generation and feature
extraction stages (Phase 1). Model hyperparameters belong in a later,
model-specific config once Phase 3 (training) starts — this file only holds
things the data generator and the feature extractor both need to agree on.

-------------------------------------------------------------------------
IMPORTANT — sampling-rate mismatch between on-device and backend (READ THIS
before wiring anything in here into telemetry_service.py later):

  * On-device (rider-app), today: accelerometer + gyroscope are polled every
    20ms (50Hz) and the on-device CrashDetector evaluates a rolling 5-second
    buffer (rider-app/src/hooks/useAccelerometer.ts:24,
    rider-app/src/crash-detection/config.ts:13 -> BUFFER_WINDOW_MS: 5000).
    GPS/location is requested at a 200ms interval (5Hz) via
    Location.watchPositionAsync (rider-app/src/hooks/useLocation.ts:93).

  * What currently reaches the FastAPI backend, today: ONE sample, once per
    second (rider-app/src/hooks/useTelemetry.ts:157 posts
    `samples: [sample]` — a single-element array — every
    TELEMETRY_EMIT_INTERVAL_MS = 1000ms). backend/app/api/telemetry.py's
    `/telemetry/batch` endpoint was never built to carry a dense window.

  This module generates synthetic windows at the ON-DEVICE resolution
  (ACCEL_GYRO_SAMPLE_RATE_HZ / GPS_SAMPLE_RATE_HZ below), NOT the coarser
  1Hz rate the backend currently receives, because 1Hz data cannot resolve
  jerk, post-impact stillness, or gyro variance meaningfully. This is a
  deliberate choice, not an oversight — it matches the only place in this
  codebase that already has data at a resolution a crash classifier needs.

  CONSEQUENCE FOR LATER INTEGRATION (Phase 6): the rider app does not
  currently have a way to send a dense 50Hz/5s window to the backend — only
  the throttled 1Hz stream. Before the trained model can score real
  telemetry, either (a) a new payload/endpoint needs to be added so the app
  forwards its raw on-device buffer when the local CrashDetector flags a
  candidate, or (b) the model needs to be retrained/adapted for the coarser
  1Hz batch shape actually available server-side today. This is an explicit
  open decision for whoever does the Phase 6 wiring — do not assume it's
  solved just because Phase 1-5 work offline against realistic windows.
-------------------------------------------------------------------------
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Window / sampling-rate parameters
# ---------------------------------------------------------------------------

GRAVITY_MS2 = 9.81

# Matches rider-app's on-device accelerometer/gyroscope poll rate
# (useAccelerometer.ts SENSOR_POLL_MS = 20).
ACCEL_GYRO_SAMPLE_RATE_HZ = 50

# Matches rider-app's GPS watch interval (useLocation.ts,
# Config.TELEMETRY_SENSOR_INTERVAL_MS = 200ms).
GPS_SAMPLE_RATE_HZ = 5

# Matches the on-device CrashDetector's rolling buffer window
# (crash-detection/config.ts, BUFFER_WINDOW_MS = 5000).
WINDOW_DURATION_S = 5.0

ACCEL_GYRO_SAMPLES_PER_WINDOW = int(ACCEL_GYRO_SAMPLE_RATE_HZ * WINDOW_DURATION_S)  # 250
GPS_SAMPLES_PER_WINDOW = int(GPS_SAMPLE_RATE_HZ * WINDOW_DURATION_S)  # 25

ACCEL_GYRO_DT_MS = 1000.0 / ACCEL_GYRO_SAMPLE_RATE_HZ  # 20ms
GPS_DT_MS = 1000.0 / GPS_SAMPLE_RATE_HZ  # 200ms

# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------

EVENT_CLASSES = ["normal", "hard_braking", "pothole", "sharp_turn", "crash"]
CRASH_CLASS = "crash"

# ---------------------------------------------------------------------------
# Feature-extraction thresholds ported 1:1 from
# rider-app/src/crash-detection/config.ts (CRASH_DETECTION_CONFIG), so that
# TS-parity feature functions in feature_extraction.py behave identically to
# the on-device rule engine. These are the same "V1 prototype, not yet
# empirically validated" values noted in the original TS file's own comment.
# ---------------------------------------------------------------------------

SPEED_DROP_WINDOW_MS = 2000
STILLNESS_WINDOW_MS = 1000
MIN_STILLNESS_DATA_MS = 300
STILLNESS_ACCEL_VARIANCE_THRESHOLD = 0.05

# Extension-feature parameters (new in the Python pipeline, no TS
# equivalent — see feature_extraction.py docstrings for what each backs).
ABNORMAL_MOTION_BASELINE_RATIO = 1.5

# ---------------------------------------------------------------------------
# Post-event "stillness" noise tiers.
#
# Earlier versions of this generator gave `crash` a single, always-applied
# quiet post-impact segment, which made post_impact_stillness a ~100%
# accurate single-feature crash classifier on its own — a synthetic
# shortcut a model would happily learn instead of the intended multi-signal
# pattern (a real crash doesn't always settle: the phone can slide, the
# rider can move immediately; a pothole/stop can occasionally look briefly
# quiet too). Fixed by drawing a per-event tier and varying the *noise
# level* actually applied, not by directly sampling the stillness boolean
# — the true/false outcome is left to compute_post_impact_stillness()'s
# own variance threshold, same as it would be on real sensor data.
#
#   "clear":   noise low enough to reliably read as still.
#   "partial": noise std deliberately straddles
#              STILLNESS_ACCEL_VARIANCE_THRESHOLD's boundary, so with only
#              ~50 samples in the detector's 1s window, whether it reads as
#              still or not is genuinely sample-dependent, not hand-picked.
#   "none":    post-event samples are left untouched (whatever motion the
#              class's own profile already produces there).
# ---------------------------------------------------------------------------

STILLNESS_CLEAR_ACCEL_STD_G = 0.015
STILLNESS_CLEAR_GYRO_STD_DEG_S = 1.0
STILLNESS_PARTIAL_ACCEL_STD_G_RANGE = (0.018, 0.032)  # spans below/above the variance threshold
STILLNESS_PARTIAL_GYRO_STD_DEG_S_RANGE = (2.0, 8.0)

# Per-class {tier: probability}, must sum to 1.0 per class. See module
# docstring above for why these are deliberately not 100/0. NOTE: "crash"
# is no longer driven by this table — see CRASH_SETTLING_* below, which
# replaced crash's instant tier switch with a physically-phased model.
STILLNESS_TIER_PROBABILITIES = {
    "normal":       {"clear": 0.01, "partial": 0.04, "none": 0.95},
    "hard_braking": {"clear": 0.03, "partial": 0.12, "none": 0.85},
    "pothole":      {"clear": 0.02, "partial": 0.10, "none": 0.88},
    "sharp_turn":   {"clear": 0.02, "partial": 0.08, "none": 0.90},
}

# ---------------------------------------------------------------------------
# Joint/composite ambiguity scenarios.
#
# The Phase 3 baseline (single multiclass XGBoost) scored 99% accuracy /
# PR-AUC 1.0000 on the Phase-1-only synthetic data — not because of a
# single-feature leak (that was checked: the errors it did make were
# sensible boundary cases, and no one feature dominated), but because even
# with every feature overlapping *pairwise* between classes, the *joint*
# combination across the full feature vector still wasn't ambiguous enough.
# Real sensor data has far more simultaneous/correlated ambiguity than five
# independently-parameterized archetypes produce. These scenarios add that:
# events that combine two classes' signatures, or push toward another
# class's territory on purpose, while keeping the label that a reasonable
# human annotator would actually assign.
#
# Some ranges below are loosely calibrated against a reference telemetry
# CSV the user supplied (1Hz per-sample data, event_type-labeled). That
# CSV's magnitudes are NOT copied directly — at 1Hz, a real crash/pothole
# spike lasting <200ms is likely captured off-peak (aliased), so its
# recorded magnitudes plausibly understate the true instantaneous peak a
# 50Hz on-device stream would see. It's used as a *relative* anchor (e.g.
# "potholes at realistic speed are meaningfully faster than 15-45 km/h",
# "post-impact motion decays, it doesn't vanish instantly"), not as exact
# target values.
# ---------------------------------------------------------------------------

# "pothole + sharp turn" / "hard braking + turn": a sustained (not spiky)
# secondary gyro elevation layered on top of the class's own signature,
# representing a simultaneous turn. Deliberately reaches into sharp_turn's
# own low range (120-300, see GENERATION_PARAMS) so it's a genuine overlap,
# not just "a bit more gyro than usual".
CONCURRENT_TURN_GYRO_DEG_S_RANGE = (60.0, 150.0)
CONCURRENT_TURN_PROBABILITY = {"pothole": 0.15, "hard_braking": 0.15}

# "pothole at higher speed": calibrated against the reference CSV's
# pothole_non_crash (speed mean ~32, up to ~45 km/h — well above this
# generator's plain 15-45 km/h *uniform* range, i.e. realistically potholes
# are disproportionately hit while riding fast, not at any random speed).
# Impact amplitude scales up too — impact energy scales with speed.
POTHOLE_HIGH_SPEED_PROBABILITY = 0.20
POTHOLE_HIGH_SPEED_KPH_RANGE = (35.0, 55.0)
POTHOLE_HIGH_SPEED_AMPLITUDE_SCALE_RANGE = (1.15, 1.5)

# "crash-like acceleration without crash": an evasive-swerve variant of
# sharp_turn reaching into crash-adjacent accel/gyro territory, but with no
# real speed drop — genuinely not a crash, just alarming-looking motion.
# Loosely anchored to the reference CSV's near_miss_non_crash (gyroMag up
# to ~68 deg/s at aliased 1Hz resolution; kept below crash's nominal range
# so it stays a "close but not a crash" case rather than a mislabeled one).
SHARP_TURN_EVASIVE_PROBABILITY = 0.12
EVASIVE_GYRO_DEG_S_RANGE = (180.0, 320.0)
EVASIVE_ACCEL_PEAK_G_RANGE = (1.8, 3.0)

# "crash with weak/partial post-impact stillness": replaces the old instant
# clear/partial/none noise switch for CRASH specifically with a physically
# phased model — impact, then a decaying SETTLING phase (residual motion
# that fades, doesn't vanish), then either true stillness or continued
# movement. Calibrated against the reference CSV's crash_post_impact phase
# (real residual gyroMag mean ~35 deg/s — clearly not silent).
CRASH_SETTLING_DURATION_S_RANGE = (0.6, 1.5)
CRASH_SETTLING_RESIDUAL_GYRO_DEG_S_RANGE = (10.0, 45.0)
CRASH_SETTLING_RESIDUAL_ACCEL_STD_G_RANGE = (0.03, 0.10)
CRASH_FULL_STILLNESS_PROBABILITY = 0.70  # after settling, chance of dropping to true quiet vs. continued motion

# "noisy/misaligned sensor readings": a class-agnostic generation-time
# mode (a poorly-mounted or lower-quality phone) — a small FIXED tilt
# applied across the whole window plus elevated baseline noise. Distinct
# from apply_random_rotation (an augmentation-stage, arbitrary full
# rotation used to test orientation invariance) — this is a moderate,
# base-generation realism factor that can apply to any class.
SENSOR_MISALIGNMENT_PROBABILITY = 0.08
SENSOR_MISALIGNMENT_TILT_DEG_RANGE = (10.0, 30.0)
SENSOR_MISALIGNMENT_NOISE_MULTIPLIER_RANGE = (1.5, 2.2)

# ---------------------------------------------------------------------------
# Synthetic-data generation parameter ranges.
#
# These are deliberately overlapping across classes on any single axis
# (e.g. pothole and crash both reach into the 2.0-4.0g accel-peak range) —
# that overlap is intentional (see README.md "Hard negatives" section) so a
# classifier trained on this data cannot succeed with a single-feature
# threshold rule; it has to learn the multi-signal combination.
#
# All ranges are uniform-random per generated event unless noted, so no two
# synthetic events in the same class are identical.
#
# IMPORTANT — what "*_peak_g_range" / "*_peak_deg_s_range" actually control:
# these are NOMINAL PULSE-AMPLITUDE parameters fed into generate_synthetic_data
# .py's impact-pulse construction, NOT a guaranteed floor on the observed
# accel_peak_g / gyro_peak feature values. For "crash" and "sharp_turn" in
# particular, the pulse amplitude is split across the 3 accel/gyro axes via
# a random Dirichlet weighting with an independently randomized sign per
# axis (see generate_synthetic_data.py's _generate_crash /
# _generate_sharp_turn) — the resulting 3D vector can partially cancel
# against itself and against the baseline gravity vector, so the *observed*
# vector-magnitude feature is often well below the configured amplitude.
# Empirically (seed 42, 800 generated crash events): configuring
# accel_peak_g_range=(3.5, 6.5) produced an observed accel_peak_g feature
# range of ~1.6-5.7g (mean ~3.5g). Do not read these ranges as "the
# generated accel_peak_g will always fall in this interval" — they don't.
# ---------------------------------------------------------------------------

GENERATION_PARAMS = {
    "normal": {
        "accel_noise_std_g": 0.03,      # ~0.3 m/s^2
        "gyro_noise_std_deg_s": 3.0,
        "speed_kph_range": (15.0, 45.0),
        "speed_walk_step_kph": 1.5,     # per accel/gyro-rate step, smoothed
    },
    "hard_braking": {
        "pulse_center_s_range": (1.0, 3.5),
        "pulse_duration_s_range": (0.6, 1.4),
        "pulse_peak_g_range": (1.6, 2.6),
        "gyro_bump_deg_s_range": (10.0, 25.0),
        "speed_drop_kph_range": (15.0, 30.0),
        "speed_drop_duration_s_range": (1.0, 1.6),
    },
    "pothole": {
        "pulse_center_s_range": (1.0, 3.5),
        "pulse_duration_s_range": (0.08, 0.25),
        "pulse_peak_g_range": (2.0, 4.0),   # overlaps crash's lower range
        "gyro_bump_deg_s_range": (15.0, 40.0),
        "speed_dip_kph_range": (0.0, 5.0),
    },
    "sharp_turn": {
        "pulse_center_s_range": (1.0, 3.0),
        "pulse_duration_s_range": (1.0, 2.0),
        "gyro_peak_deg_s_range": (120.0, 300.0),  # overlaps crash's lower range
        "accel_peak_g_range": (1.1, 1.8),
        "speed_dip_kph_range": (0.0, 8.0),
    },
    "crash": {
        "impact_center_s_range": (1.5, 3.0),
        "impact_duration_s_range": (0.05, 0.2),
        "accel_peak_g_range": (3.5, 6.5),   # overlaps pothole's upper range
        "gyro_peak_deg_s_range": (200.0, 450.0),  # overlaps sharp_turn's upper range
        "gyro_timing_offset_ms_range": (-50.0, 50.0),
        "speed_drop_kph_range": (20.0, 45.0),
        "speed_drop_duration_s_range": (0.5, 1.2),
        "residual_speed_kph_range": (0.0, 5.0),
        # Post-impact accel/gyro noise level is no longer a fixed value
        # here — it's drawn per-event from STILLNESS_TIER_PROBABILITIES /
        # STILLNESS_CLEAR_*/STILLNESS_PARTIAL_*_RANGE above.
    },
}
