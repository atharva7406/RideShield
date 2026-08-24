"""
Procedural synthetic telemetry-window generator.

There is no external dataset here — every window is synthesized from
physics-informed, randomized parameter ranges (see config.GENERATION_PARAMS).
This module never touches the production database or any real rider data.

Each event is a ~5-second window (config.WINDOW_DURATION_S) of accelerometer
+ gyroscope samples at config.ACCEL_GYRO_SAMPLE_RATE_HZ and GPS/speed samples
at config.GPS_SAMPLE_RATE_HZ, in the same physical units as
db/models/telemetry.py's TelemetrySample columns (accel_x/y/z in m/s^2,
speed in km/h, gyro_x/y/z in deg/s, gps_accuracy in meters).

Design goal: classes must overlap on individual features (see
config.GENERATION_PARAMS's comment on intentional overlap) so a model
trained on this data has to learn the multi-signal combination, the same
principle the existing on-device rule engine already uses
(rider-app/src/crash-detection/crashDetector.ts: an accel spike alone is
never sufficient, it must be corroborated by a gyro or speed-drop signal).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace

import numpy as np

from . import config as cfg


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------


@dataclass
class TelemetryWindow:
    """One ~5s synthetic telemetry window plus its labels/metadata.

    Field names for the sensor arrays deliberately match
    db/models/telemetry.py's TelemetrySample columns so the same window can
    later be built from a real DB query with no shape changes.
    """

    # Metadata (not present in the production DB schema — training-only
    # bookkeeping, lives only inside this module's generated datasets).
    event_id: str
    rider_id: str
    shift_id: str
    class_label: str
    is_augmented: bool
    source_event_id: str  # == event_id for non-augmented (original) events

    # Sensor data — same physical units/fields as TelemetrySample.
    accel_t_ms: np.ndarray  # absolute-ish epoch ms, one per accel/gyro sample
    accel_x: np.ndarray
    accel_y: np.ndarray
    accel_z: np.ndarray

    gyro_t_ms: np.ndarray  # same timestamps as accel_t_ms (single IMU stream)
    gyro_x: np.ndarray
    gyro_y: np.ndarray
    gyro_z: np.ndarray

    gps_t_ms: np.ndarray
    gps_lat: np.ndarray
    gps_lng: np.ndarray
    gps_speed_kmh: np.ndarray
    gps_altitude: np.ndarray
    gps_accuracy: np.ndarray

    def copy_with(self, **overrides) -> "TelemetryWindow":
        return replace(self, **overrides)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _gaussian_pulse(t_ms: np.ndarray, center_ms: float, width_ms: float, amplitude: float) -> np.ndarray:
    """A smooth bump centered at `center_ms`. `width_ms` is treated as the
    pulse's std-dev-like spread, not its full duration."""
    width_ms = max(width_ms, 1.0)
    return amplitude * np.exp(-0.5 * ((t_ms - center_ms) / width_ms) ** 2)


def _one_sided_rising_pulse(t_ms: np.ndarray, center_ms: float, width_ms: float, amplitude: float) -> np.ndarray:
    """Like _gaussian_pulse but zero for t > center_ms: a sharp rise with no
    decaying tail. Used only for the crash impact, where the physical story
    is "sudden deceleration then stillness," not a symmetric bump — a
    symmetric pulse's tail was still ~90%+ of peak amplitude for a couple of
    samples immediately after the peak, which meant post-impact "stillness"
    never actually looked still. See generate_dataset() call sites for the
    matching noise-reduction cutover."""
    width_ms = max(width_ms, 1.0)
    pulse = amplitude * np.exp(-0.5 * ((t_ms - center_ms) / width_ms) ** 2)
    return np.where(t_ms <= center_ms, pulse, 0.0)


def _smooth_random_walk(rng: np.random.Generator, n: int, start: float, step_std: float,
                         low: float, high: float) -> np.ndarray:
    """A clipped random walk — used for speed profiles so they wander
    realistically instead of jittering sample-to-sample."""
    steps = rng.normal(0.0, step_std, n)
    walk = start + np.cumsum(steps) - np.cumsum(steps)[0]  # start exactly at `start`
    walk = np.clip(walk, low, high)
    return walk


def _base_time_axes(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, float]:
    start_ts_ms = float(rng.integers(1_700_000_000_000, 1_800_000_000_000))
    accel_t = start_ts_ms + np.arange(cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW) * cfg.ACCEL_GYRO_DT_MS
    gps_t = start_ts_ms + np.arange(cfg.GPS_SAMPLES_PER_WINDOW) * cfg.GPS_DT_MS
    return accel_t, gps_t, start_ts_ms


def _base_normal_profile(rng: np.random.Generator) -> dict:
    """The riding profile every class starts from before its
    class-specific event is layered on top."""
    p = cfg.GENERATION_PARAMS["normal"]
    n_ag = cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    n_gps = cfg.GPS_SAMPLES_PER_WINDOW

    accel_x = rng.normal(0.0, p["accel_noise_std_g"] * cfg.GRAVITY_MS2, n_ag)
    accel_y = rng.normal(0.0, p["accel_noise_std_g"] * cfg.GRAVITY_MS2, n_ag)
    accel_z = cfg.GRAVITY_MS2 + rng.normal(0.0, p["accel_noise_std_g"] * cfg.GRAVITY_MS2, n_ag)

    gyro_x = rng.normal(0.0, p["gyro_noise_std_deg_s"], n_ag)
    gyro_y = rng.normal(0.0, p["gyro_noise_std_deg_s"], n_ag)
    gyro_z = rng.normal(0.0, p["gyro_noise_std_deg_s"], n_ag)

    speed_start = rng.uniform(*p["speed_kph_range"])
    speed = _smooth_random_walk(
        rng, n_gps, speed_start, p["speed_walk_step_kph"],
        low=0.0, high=80.0,
    )

    gps_accuracy = rng.uniform(3.0, 8.0, n_gps)
    altitude = rng.uniform(200.0, 250.0) + np.cumsum(rng.normal(0, 0.05, n_gps))

    return dict(
        accel_x=accel_x, accel_y=accel_y, accel_z=accel_z,
        gyro_x=gyro_x, gyro_y=gyro_y, gyro_z=gyro_z,
        speed=speed, gps_accuracy=gps_accuracy, altitude=altitude,
    )


def _rng_uuid(rng: np.random.Generator) -> str:
    """A UUID derived from the seeded rng, not from system randomness —
    uuid.uuid4() would silently break seed-reproducibility (its entropy
    doesn't come from `rng` at all)."""
    return str(uuid.UUID(bytes=rng.bytes(16), version=4))


def _draw_stillness_tier(rng: np.random.Generator, class_label: str) -> str:
    probs = cfg.STILLNESS_TIER_PROBABILITIES[class_label]
    tiers = list(probs.keys())
    return rng.choice(tiers, p=[probs[t] for t in tiers])


def _apply_post_event_motion_profile(
    accel_x: np.ndarray, accel_y: np.ndarray, accel_z: np.ndarray,
    gyro_x: np.ndarray, gyro_y: np.ndarray, gyro_z: np.ndarray,
    accel_t: np.ndarray, anchor_ms: float, rng: np.random.Generator, tier: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Overwrites accel/gyro samples after `anchor_ms` with a noise level
    set by `tier` ('clear' | 'partial' | 'none'). 'none' is a no-op — the
    class's own profile (already-normal riding noise, or an unmodified
    pulse tail) is left as-is. See config.py's stillness-tier docstring for
    why the boolean outcome is deliberately not chosen directly."""
    if tier == "none":
        return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z

    mask = accel_t > anchor_ms
    n = int(mask.sum())
    if n == 0:
        return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z

    if tier == "clear":
        accel_std_g = cfg.STILLNESS_CLEAR_ACCEL_STD_G
        gyro_std = cfg.STILLNESS_CLEAR_GYRO_STD_DEG_S
    else:  # "partial"
        accel_std_g = rng.uniform(*cfg.STILLNESS_PARTIAL_ACCEL_STD_G_RANGE)
        gyro_std = rng.uniform(*cfg.STILLNESS_PARTIAL_GYRO_STD_DEG_S_RANGE)

    accel_x, accel_y, accel_z = accel_x.copy(), accel_y.copy(), accel_z.copy()
    gyro_x, gyro_y, gyro_z = gyro_x.copy(), gyro_y.copy(), gyro_z.copy()
    accel_std_ms2 = accel_std_g * cfg.GRAVITY_MS2
    accel_x[mask] = rng.normal(0.0, accel_std_ms2, n)
    accel_y[mask] = rng.normal(0.0, accel_std_ms2, n)
    accel_z[mask] = cfg.GRAVITY_MS2 + rng.normal(0.0, accel_std_ms2, n)
    gyro_x[mask] = rng.normal(0.0, gyro_std, n)
    gyro_y[mask] = rng.normal(0.0, gyro_std, n)
    gyro_z[mask] = rng.normal(0.0, gyro_std, n)
    return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z


def _resolve_force(rng: np.random.Generator, force: bool | None, probability: float) -> bool:
    """`force=None` draws probabilistically (normal generation);
    `force=True`/`False` overrides the draw — used by regression tests to
    request a scenario deterministically instead of hoping a random draw
    happens to trigger it. Even when forced, the same rng is NOT consumed,
    so downstream calls stay reproducible relative to whichever path was
    actually taken."""
    if force is not None:
        return force
    return bool(rng.uniform() < probability)


def _apply_concurrent_turn(
    accel_x: np.ndarray, accel_y: np.ndarray, accel_z: np.ndarray,
    gyro_x: np.ndarray, gyro_y: np.ndarray, gyro_z: np.ndarray,
    accel_t: np.ndarray, center_ms: float, width_ms: float, rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """'pothole + sharp turn' / 'hard braking + turn': a sustained (wide,
    not spiky) secondary gyro elevation layered on top of the caller's own
    signature, representing a simultaneous turn. Additive (+=), unlike
    _apply_post_event_motion_profile which replaces — this is happening
    DURING the primary event, not after it."""
    turn_gyro_peak = rng.uniform(*cfg.CONCURRENT_TURN_GYRO_DEG_S_RANGE)
    turn_width_ms = max(width_ms * 2.5, 300.0)  # wider/more sustained than the primary pulse
    turn_pulse = _gaussian_pulse(accel_t, center_ms, turn_width_ms, turn_gyro_peak)
    axis = rng.integers(0, 3)
    sign = rng.choice([-1, 1])
    gyros = [gyro_x, gyro_y, gyro_z]
    gyros[axis] = gyros[axis] + turn_pulse * sign
    # A real simultaneous turn also has some lateral accel, smaller than the
    # primary event's own contribution.
    lateral_g = rng.uniform(0.3, 0.8)
    accel_y = accel_y + _gaussian_pulse(accel_t, center_ms, turn_width_ms, lateral_g * cfg.GRAVITY_MS2) * sign
    return accel_x, accel_y, accel_z, gyros[0], gyros[1], gyros[2]


def apply_sensor_misalignment(
    window: "TelemetryWindow", rng: np.random.Generator,
) -> "TelemetryWindow":
    """'noisy/misaligned sensor readings': a small FIXED tilt (not a fully
    arbitrary orientation, see config.SENSOR_MISALIGNMENT_TILT_DEG_RANGE)
    applied across the whole window, plus elevated baseline noise —
    simulates a poorly-mounted or lower-quality phone. Class-agnostic:
    called from generate_event() after the class-specific generator runs,
    so it can apply to any class without changing its label."""
    tilt_deg = rng.uniform(*cfg.SENSOR_MISALIGNMENT_TILT_DEG_RANGE)
    rot = _small_angle_rotation_matrix(rng, tilt_deg)
    accel = rot @ np.vstack([window.accel_x, window.accel_y, window.accel_z])
    gyro = rot @ np.vstack([window.gyro_x, window.gyro_y, window.gyro_z])

    noise_mult = rng.uniform(*cfg.SENSOR_MISALIGNMENT_NOISE_MULTIPLIER_RANGE)
    n = len(window.accel_x)
    extra_accel_std = (noise_mult - 1.0) * cfg.GENERATION_PARAMS["normal"]["accel_noise_std_g"] * cfg.GRAVITY_MS2
    extra_gyro_std = (noise_mult - 1.0) * cfg.GENERATION_PARAMS["normal"]["gyro_noise_std_deg_s"]
    accel[0] = accel[0] + rng.normal(0, extra_accel_std, n)
    accel[1] = accel[1] + rng.normal(0, extra_accel_std, n)
    accel[2] = accel[2] + rng.normal(0, extra_accel_std, n)
    gyro[0] = gyro[0] + rng.normal(0, extra_gyro_std, n)
    gyro[1] = gyro[1] + rng.normal(0, extra_gyro_std, n)
    gyro[2] = gyro[2] + rng.normal(0, extra_gyro_std, n)

    return window.copy_with(
        accel_x=accel[0], accel_y=accel[1], accel_z=accel[2],
        gyro_x=gyro[0], gyro_y=gyro[1], gyro_z=gyro[2],
    )


def _small_angle_rotation_matrix(rng: np.random.Generator, tilt_deg: float) -> np.ndarray:
    """A rotation by exactly `tilt_deg` around a random axis (Rodrigues'
    formula) — unlike _random_rotation_matrix (uniform over all of SO(3)),
    this represents a plausible SMALL mounting misalignment, not an
    arbitrary orientation."""
    axis = rng.normal(size=3)
    axis = axis / np.linalg.norm(axis)
    angle = np.deg2rad(tilt_deg)
    k = np.array([
        [0.0, -axis[2], axis[1]],
        [axis[2], 0.0, -axis[0]],
        [-axis[1], axis[0], 0.0],
    ])
    return np.eye(3) + np.sin(angle) * k + (1.0 - np.cos(angle)) * (k @ k)


def _apply_crash_settling_phase(
    accel_x: np.ndarray, accel_y: np.ndarray, accel_z: np.ndarray,
    gyro_x: np.ndarray, gyro_y: np.ndarray, gyro_z: np.ndarray,
    accel_t: np.ndarray, center_ms: float, accel_peak_g: float, gyro_peak: float,
    rng: np.random.Generator, force_full_stillness: bool | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Replaces the old instant clear/partial/none noise switch for crash
    with a physically phased model: impact -> a decaying SETTLING window
    (real residual motion that fades, not silence) -> a final level the
    settling decays toward. Calibrated against the reference CSV's
    crash_post_impact phase (real residual gyroMag mean ~35 deg/s).

    Whether it "settles fully" decides what that final level IS, and how
    long the decay realistically takes to get there:
      - settles fully: comes to rest almost immediately (matches the old
        "clear" tier's near-instant cutover — that case wasn't the one
        needing improvement). The "hot" level here is intentionally a
        modest multiple of the quiet target, NOT tied to the impact's own
        peak magnitude — a genuine multi-hundred-deg/s or multi-g "hot"
        start (even for 1-2 samples) is more than enough to make the
        combined 1s window compute_post_impact_stillness() inspects read
        as "not still" regardless of how short the decay is, since that
        threshold is strict (0.05 on raw m/s^2 variance) — tying "hot" to
        the actual crash peak made force_full_stillness=True structurally
        unreachable (found via a failing regression test, not by
        inspection: 0/30 draws read as still with the peak-scaled version).
      - doesn't settle: a real, LONGER decay (peak-scaled "hot" start is
        appropriate here — this case's whole point is a genuine, sizeable
        residual level to end at, not silence) toward a real residual
        (not still, not full-normal-noise-level) motion level it then
        stays at for the remainder — the phone slid, the rider moved, but
        it never goes silent.
    """
    settles_fully = _resolve_force(rng, force_full_stillness, cfg.CRASH_FULL_STILLNESS_PROBABILITY)

    if settles_fully:
        settling_duration_ms = rng.uniform(20.0, 60.0)
        target_accel_std_g = cfg.STILLNESS_CLEAR_ACCEL_STD_G
        target_gyro = cfg.STILLNESS_CLEAR_GYRO_STD_DEG_S
        hot_gyro = target_gyro * rng.uniform(3.0, 6.0)
        hot_accel_std_g = target_accel_std_g * rng.uniform(3.0, 6.0)
    else:
        settling_duration_ms = rng.uniform(*cfg.CRASH_SETTLING_DURATION_S_RANGE) * 1000
        target_accel_std_g = rng.uniform(*cfg.CRASH_SETTLING_RESIDUAL_ACCEL_STD_G_RANGE)
        target_gyro = rng.uniform(*cfg.CRASH_SETTLING_RESIDUAL_GYRO_DEG_S_RANGE)
        hot_gyro = max(gyro_peak * rng.uniform(0.15, 0.35), target_gyro * 1.5)
        hot_accel_std_g = max(accel_peak_g * rng.uniform(0.05, 0.12), target_accel_std_g * 1.5)

    accel_x, accel_y, accel_z = accel_x.copy(), accel_y.copy(), accel_z.copy()
    gyro_x, gyro_y, gyro_z = gyro_x.copy(), gyro_y.copy(), gyro_z.copy()

    settling_mask = (accel_t > center_ms) & (accel_t <= center_ms + settling_duration_ms)
    n_settling = int(settling_mask.sum())
    if n_settling > 0:
        t_in_phase = (accel_t[settling_mask] - center_ms) / settling_duration_ms
        decay_gyro = target_gyro + (hot_gyro - target_gyro) * np.exp(-3.0 * t_in_phase)
        decay_accel_std_g = target_accel_std_g + (hot_accel_std_g - target_accel_std_g) * np.exp(-3.0 * t_in_phase)
        decay_accel_std_ms2 = decay_accel_std_g * cfg.GRAVITY_MS2
        accel_x[settling_mask] = rng.normal(0.0, decay_accel_std_ms2, n_settling)
        accel_y[settling_mask] = rng.normal(0.0, decay_accel_std_ms2, n_settling)
        accel_z[settling_mask] = cfg.GRAVITY_MS2 + rng.normal(0.0, decay_accel_std_ms2, n_settling)
        gyro_x[settling_mask] = rng.normal(0.0, decay_gyro, n_settling)
        gyro_y[settling_mask] = rng.normal(0.0, decay_gyro, n_settling)
        gyro_z[settling_mask] = rng.normal(0.0, decay_gyro, n_settling)

    final_mask = accel_t > (center_ms + settling_duration_ms)
    n_final = int(final_mask.sum())
    if n_final > 0:
        target_accel_std_ms2 = target_accel_std_g * cfg.GRAVITY_MS2
        accel_x[final_mask] = rng.normal(0.0, target_accel_std_ms2, n_final)
        accel_y[final_mask] = rng.normal(0.0, target_accel_std_ms2, n_final)
        accel_z[final_mask] = cfg.GRAVITY_MS2 + rng.normal(0.0, target_accel_std_ms2, n_final)
        gyro_x[final_mask] = rng.normal(0.0, target_gyro, n_final)
        gyro_y[final_mask] = rng.normal(0.0, target_gyro, n_final)
        gyro_z[final_mask] = rng.normal(0.0, target_gyro, n_final)

    return accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z


def _base_lat_lng(rng: np.random.Generator, n_gps: int) -> tuple[np.ndarray, np.ndarray]:
    # Arbitrary plausible starting coordinates (Delhi area, matching the
    # simulated-location fallback already used in rider-app/useLocation.ts)
    # with a small drift — the crash classifier does not use raw lat/lng as
    # a feature, this is just here so the window is DB-shape-complete.
    base_lat, base_lng = 28.6139, 77.2090
    lat = base_lat + np.cumsum(rng.normal(0, 1e-6, n_gps))
    lng = base_lng + np.cumsum(rng.normal(0, 1e-6, n_gps))
    return lat, lng


# ---------------------------------------------------------------------------
# Per-class generators
# ---------------------------------------------------------------------------


def _generate_normal(rng: np.random.Generator) -> dict:
    base = _base_normal_profile(rng)

    # No single "event" to anchor a post-event quiet segment to — instead,
    # occasionally make the *whole* window read as a genuine stop (e.g. at
    # a traffic light), which is a realistic source of low motion for a
    # "normal riding" sample and keeps this class's stillness rate
    # authentically low-but-nonzero rather than a hardcoded zero.
    tier = _draw_stillness_tier(rng, "normal")
    if tier != "none":
        n_ag = len(base["accel_x"])
        accel_t = np.arange(n_ag) * cfg.ACCEL_GYRO_DT_MS
        (base["accel_x"], base["accel_y"], base["accel_z"],
         base["gyro_x"], base["gyro_y"], base["gyro_z"]) = _apply_post_event_motion_profile(
            base["accel_x"], base["accel_y"], base["accel_z"],
            base["gyro_x"], base["gyro_y"], base["gyro_z"],
            accel_t, anchor_ms=-1.0,  # whole window: anchor before t=0
            rng=rng, tier=tier,
        )

    return base


def _generate_hard_braking(rng: np.random.Generator, force_concurrent_turn: bool | None = None) -> dict:
    p = cfg.GENERATION_PARAMS["hard_braking"]
    base = _base_normal_profile(rng)
    accel_t = np.arange(cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW) * cfg.ACCEL_GYRO_DT_MS
    gps_t = np.arange(cfg.GPS_SAMPLES_PER_WINDOW) * cfg.GPS_DT_MS

    center_ms = rng.uniform(*p["pulse_center_s_range"]) * 1000
    duration_ms = rng.uniform(*p["pulse_duration_s_range"]) * 1000
    peak_g = rng.uniform(*p["pulse_peak_g_range"])
    width_ms = duration_ms / 2.0

    # Forward/deceleration axis — negative-going pulse on x.
    base["accel_x"] = base["accel_x"] - _gaussian_pulse(accel_t, center_ms, width_ms, peak_g * cfg.GRAVITY_MS2)

    gyro_bump = rng.uniform(*p["gyro_bump_deg_s_range"])
    base["gyro_y"] = base["gyro_y"] + _gaussian_pulse(accel_t, center_ms, width_ms, gyro_bump)

    # "hard braking + turn": braking into a corner — occasionally layer a
    # real, sustained secondary gyro elevation on top of the plain-braking
    # signature. See config.CONCURRENT_TURN_*.
    if _resolve_force(rng, force_concurrent_turn, cfg.CONCURRENT_TURN_PROBABILITY["hard_braking"]):
        (base["accel_x"], base["accel_y"], base["accel_z"],
         base["gyro_x"], base["gyro_y"], base["gyro_z"]) = _apply_concurrent_turn(
            base["accel_x"], base["accel_y"], base["accel_z"],
            base["gyro_x"], base["gyro_y"], base["gyro_z"],
            accel_t, center_ms, width_ms, rng,
        )

    drop_kph = rng.uniform(*p["speed_drop_kph_range"])
    drop_duration_ms = rng.uniform(*p["speed_drop_duration_s_range"]) * 1000
    # Smooth-step speed drop centered at the same event, rider keeps moving after.
    drop_profile = drop_kph / (1.0 + np.exp(-(gps_t - center_ms) / (drop_duration_ms / 4.0)))
    base["speed"] = np.clip(base["speed"] - drop_profile, 0.0, None)

    # Usually the rider keeps moving after braking, but occasionally they
    # were braking *to a stop* (red light, obstacle) — a brief low-motion
    # period right after. See config.STILLNESS_TIER_PROBABILITIES.
    tier = _draw_stillness_tier(rng, "hard_braking")
    (base["accel_x"], base["accel_y"], base["accel_z"],
     base["gyro_x"], base["gyro_y"], base["gyro_z"]) = _apply_post_event_motion_profile(
        base["accel_x"], base["accel_y"], base["accel_z"],
        base["gyro_x"], base["gyro_y"], base["gyro_z"],
        # Anchored at the pulse's own peak (center_ms), not center+duration:
        # compute_post_impact_stillness() only inspects the 1s window right
        # after the window's global magnitude peak, and for the longer
        # pulses here (sharp_turn's can run ~2s) anchoring any later placed
        # the quiet zone entirely past where that window closes, making the
        # clear/partial tiers silently unreachable. The override below
        # fully replaces samples regardless of the underlying (still
        # additive, still symmetric) pulse shape, so anchoring this early
        # is safe — it doesn't affect the "none" tier majority at all.
        accel_t, anchor_ms=center_ms, rng=rng, tier=tier,
    )

    return base


def _generate_pothole(
    rng: np.random.Generator,
    force_concurrent_turn: bool | None = None,
    force_high_speed: bool | None = None,
) -> dict:
    p = cfg.GENERATION_PARAMS["pothole"]

    # "pothole at higher speed": calibrated against the reference CSV's
    # pothole_non_crash (speed mean ~32, up to ~45 km/h) — realistically
    # potholes are disproportionately hit while riding fast, not at any
    # uniformly random speed. Impact amplitude scales up with it too (impact
    # energy scales with speed). See config.POTHOLE_HIGH_SPEED_*.
    is_high_speed = _resolve_force(rng, force_high_speed, cfg.POTHOLE_HIGH_SPEED_PROBABILITY)
    base = _base_normal_profile(rng)
    if is_high_speed:
        speed_start = rng.uniform(*cfg.POTHOLE_HIGH_SPEED_KPH_RANGE)
        base["speed"] = _smooth_random_walk(
            rng, len(base["speed"]), speed_start,
            cfg.GENERATION_PARAMS["normal"]["speed_walk_step_kph"], low=0.0, high=90.0,
        )
    accel_t = np.arange(cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW) * cfg.ACCEL_GYRO_DT_MS
    gps_t = np.arange(cfg.GPS_SAMPLES_PER_WINDOW) * cfg.GPS_DT_MS

    center_ms = rng.uniform(*p["pulse_center_s_range"]) * 1000
    duration_ms = rng.uniform(*p["pulse_duration_s_range"]) * 1000
    peak_g = rng.uniform(*p["pulse_peak_g_range"])
    if is_high_speed:
        peak_g *= rng.uniform(*cfg.POTHOLE_HIGH_SPEED_AMPLITUDE_SCALE_RANGE)
    width_ms = duration_ms / 2.0

    # Sharp, short, mostly-vertical spike — no sustained rotation, no real
    # speed change, and it recovers almost immediately (occasionally with a
    # brief quiet patch, e.g. the road smooths out momentarily — but this
    # should stay rare and not look like a genuine crash-settle).
    base["accel_z"] = base["accel_z"] + _gaussian_pulse(accel_t, center_ms, width_ms, peak_g * cfg.GRAVITY_MS2)

    gyro_bump = rng.uniform(*p["gyro_bump_deg_s_range"])
    base["gyro_x"] = base["gyro_x"] + _gaussian_pulse(accel_t, center_ms, width_ms / 2.0, gyro_bump)

    # "pothole + sharp turn": hitting a pothole while mid-turn — still a
    # pothole event (that's what happened to the road surface), but with
    # real sustained gyro elevation, not just the transient bump above.
    if _resolve_force(rng, force_concurrent_turn, cfg.CONCURRENT_TURN_PROBABILITY["pothole"]):
        (base["accel_x"], base["accel_y"], base["accel_z"],
         base["gyro_x"], base["gyro_y"], base["gyro_z"]) = _apply_concurrent_turn(
            base["accel_x"], base["accel_y"], base["accel_z"],
            base["gyro_x"], base["gyro_y"], base["gyro_z"],
            accel_t, center_ms, width_ms, rng,
        )

    dip_kph = rng.uniform(*p["speed_dip_kph_range"])
    dip_profile = _gaussian_pulse(gps_t, center_ms, duration_ms * 2, dip_kph)
    base["speed"] = np.clip(base["speed"] - dip_profile, 0.0, None)

    tier = _draw_stillness_tier(rng, "pothole")
    (base["accel_x"], base["accel_y"], base["accel_z"],
     base["gyro_x"], base["gyro_y"], base["gyro_z"]) = _apply_post_event_motion_profile(
        base["accel_x"], base["accel_y"], base["accel_z"],
        base["gyro_x"], base["gyro_y"], base["gyro_z"],
        # Anchored at the pulse's own peak (center_ms), not center+duration:
        # compute_post_impact_stillness() only inspects the 1s window right
        # after the window's global magnitude peak, and for the longer
        # pulses here (sharp_turn's can run ~2s) anchoring any later placed
        # the quiet zone entirely past where that window closes, making the
        # clear/partial tiers silently unreachable. The override below
        # fully replaces samples regardless of the underlying (still
        # additive, still symmetric) pulse shape, so anchoring this early
        # is safe — it doesn't affect the "none" tier majority at all.
        accel_t, anchor_ms=center_ms, rng=rng, tier=tier,
    )

    return base


def _generate_sharp_turn(rng: np.random.Generator, force_evasive: bool | None = None) -> dict:
    p = cfg.GENERATION_PARAMS["sharp_turn"]
    base = _base_normal_profile(rng)
    accel_t = np.arange(cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW) * cfg.ACCEL_GYRO_DT_MS
    gps_t = np.arange(cfg.GPS_SAMPLES_PER_WINDOW) * cfg.GPS_DT_MS

    center_ms = rng.uniform(*p["pulse_center_s_range"]) * 1000
    duration_ms = rng.uniform(*p["pulse_duration_s_range"]) * 1000
    width_ms = duration_ms / 2.0  # wide/sustained, not spiky

    # "crash-like acceleration without crash": an evasive-swerve variant —
    # real, large accel/gyro reaching into crash-adjacent territory, but
    # still no speed drop, so the multi-signal logic correctly keeps it out
    # of the crash class. See config.SHARP_TURN_EVASIVE_PROBABILITY /
    # EVASIVE_*.
    is_evasive = _resolve_force(rng, force_evasive, cfg.SHARP_TURN_EVASIVE_PROBABILITY)
    if is_evasive:
        gyro_peak = rng.uniform(*cfg.EVASIVE_GYRO_DEG_S_RANGE)
        accel_peak_g = rng.uniform(*cfg.EVASIVE_ACCEL_PEAK_G_RANGE)
    else:
        gyro_peak = rng.uniform(*p["gyro_peak_deg_s_range"])
        accel_peak_g = rng.uniform(*p["accel_peak_g_range"])

    base["gyro_z"] = base["gyro_z"] + _gaussian_pulse(accel_t, center_ms, width_ms, gyro_peak)
    base["accel_y"] = base["accel_y"] + _gaussian_pulse(accel_t, center_ms, width_ms, accel_peak_g * cfg.GRAVITY_MS2)

    dip_kph = rng.uniform(*p["speed_dip_kph_range"])
    dip_profile = _gaussian_pulse(gps_t, center_ms, duration_ms, dip_kph)
    base["speed"] = np.clip(base["speed"] - dip_profile, 0.0, None)

    tier = _draw_stillness_tier(rng, "sharp_turn")
    (base["accel_x"], base["accel_y"], base["accel_z"],
     base["gyro_x"], base["gyro_y"], base["gyro_z"]) = _apply_post_event_motion_profile(
        base["accel_x"], base["accel_y"], base["accel_z"],
        base["gyro_x"], base["gyro_y"], base["gyro_z"],
        # Anchored at the pulse's own peak (center_ms), not center+duration:
        # compute_post_impact_stillness() only inspects the 1s window right
        # after the window's global magnitude peak, and for the longer
        # pulses here (sharp_turn's can run ~2s) anchoring any later placed
        # the quiet zone entirely past where that window closes, making the
        # clear/partial tiers silently unreachable. The override below
        # fully replaces samples regardless of the underlying (still
        # additive, still symmetric) pulse shape, so anchoring this early
        # is safe — it doesn't affect the "none" tier majority at all.
        accel_t, anchor_ms=center_ms, rng=rng, tier=tier,
    )

    return base


def _generate_crash(rng: np.random.Generator, force_full_stillness: bool | None = None) -> dict:
    p = cfg.GENERATION_PARAMS["crash"]
    base = _base_normal_profile(rng)
    accel_t = np.arange(cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW) * cfg.ACCEL_GYRO_DT_MS
    gps_t = np.arange(cfg.GPS_SAMPLES_PER_WINDOW) * cfg.GPS_DT_MS

    center_ms = rng.uniform(*p["impact_center_s_range"]) * 1000
    duration_ms = rng.uniform(*p["impact_duration_s_range"]) * 1000
    width_ms = duration_ms / 2.0

    accel_peak_g = rng.uniform(*p["accel_peak_g_range"])
    # Spread the impact across all three axes (arbitrary directionality).
    # One-sided: rises to the peak, then cuts to zero contribution rather
    # than ringing down — the post-impact noise-reduction below (post_mask)
    # supplies the "settles to still" behaviour instead, cleanly, with no
    # gap where a decaying tail could still dominate the variance window.
    axis_weights = rng.dirichlet(np.ones(3))
    pulse = _one_sided_rising_pulse(accel_t, center_ms, width_ms, accel_peak_g * cfg.GRAVITY_MS2)
    base["accel_x"] = base["accel_x"] + pulse * axis_weights[0] * rng.choice([-1, 1])
    base["accel_y"] = base["accel_y"] + pulse * axis_weights[1] * rng.choice([-1, 1])
    base["accel_z"] = base["accel_z"] + pulse * axis_weights[2] * rng.choice([-1, 1])

    gyro_peak = rng.uniform(*p["gyro_peak_deg_s_range"])
    gyro_offset_ms = rng.uniform(*p["gyro_timing_offset_ms_range"])
    gyro_axis_weights = rng.dirichlet(np.ones(3))
    gyro_pulse = _one_sided_rising_pulse(accel_t, center_ms + gyro_offset_ms, width_ms, gyro_peak)
    base["gyro_x"] = base["gyro_x"] + gyro_pulse * gyro_axis_weights[0] * rng.choice([-1, 1])
    base["gyro_y"] = base["gyro_y"] + gyro_pulse * gyro_axis_weights[1] * rng.choice([-1, 1])
    base["gyro_z"] = base["gyro_z"] + gyro_pulse * gyro_axis_weights[2] * rng.choice([-1, 1])

    drop_kph = rng.uniform(*p["speed_drop_kph_range"])
    drop_duration_ms = rng.uniform(*p["speed_drop_duration_s_range"]) * 1000
    residual_kph = rng.uniform(*p["residual_speed_kph_range"])
    pre_speed = float(np.interp(center_ms, gps_t, base["speed"]))
    drop_profile = (pre_speed - residual_kph) / (1.0 + np.exp(-(gps_t - center_ms) / (drop_duration_ms / 4.0)))
    base["speed"] = np.clip(base["speed"] - drop_profile, 0.0, None)

    # Post-impact motion: NOT always "stillness", and not an instant on/off
    # switch either — real crashes go through a decaying settling phase
    # (real, fading residual motion) before EITHER reaching true stillness
    # OR staying at a real (not silent) residual level for good, depending
    # on force_full_stillness / config.CRASH_FULL_STILLNESS_PROBABILITY.
    # See _apply_crash_settling_phase's docstring.
    (base["accel_x"], base["accel_y"], base["accel_z"],
     base["gyro_x"], base["gyro_y"], base["gyro_z"]) = _apply_crash_settling_phase(
        base["accel_x"], base["accel_y"], base["accel_z"],
        base["gyro_x"], base["gyro_y"], base["gyro_z"],
        accel_t, center_ms, accel_peak_g, gyro_peak, rng, force_full_stillness,
    )

    # The vehicle's GPS speed dropping toward the residual level after
    # impact is kept independent of the accel/gyro stillness tier above —
    # even a crash where the phone keeps moving (sliding, rider thrown)
    # still generally means the vehicle itself has stopped or nearly so.
    base["speed"] = np.where(gps_t > (center_ms + duration_ms * 2),
                              np.minimum(base["speed"], residual_kph + rng.normal(0, 0.3, len(gps_t))),
                              base["speed"])

    return base


_GENERATORS = {
    "normal": _generate_normal,
    "hard_braking": _generate_hard_braking,
    "pothole": _generate_pothole,
    "sharp_turn": _generate_sharp_turn,
    "crash": _generate_crash,
}


# ---------------------------------------------------------------------------
# Public: single-event generation
# ---------------------------------------------------------------------------


def generate_event(
    class_label: str,
    rng: np.random.Generator,
    rider_id: str,
    shift_id: str,
    event_id: str | None = None,
    force_concurrent_turn: bool | None = None,
    force_high_speed: bool | None = None,
    force_evasive: bool | None = None,
    force_full_stillness: bool | None = None,
    force_misalignment: bool | None = None,
) -> TelemetryWindow:
    """The `force_*` kwargs override this event's composite/ambiguous
    scenarios (see config.py's "Joint/composite ambiguity scenarios"
    section) instead of leaving them to the probabilistic default — used by
    regression tests to request a scenario deterministically. Each is only
    meaningful for the class(es) that actually have that scenario; passed
    to any other class, it's silently ignored (e.g. force_evasive on a
    "crash" event does nothing — evasive is a sharp_turn-only scenario)."""
    if class_label not in _GENERATORS:
        raise ValueError(f"Unknown class_label {class_label!r}, expected one of {cfg.EVENT_CLASSES}")

    accel_t, gps_t, _ = _base_time_axes(rng)

    if class_label == "hard_braking":
        profile = _generate_hard_braking(rng, force_concurrent_turn=force_concurrent_turn)
    elif class_label == "pothole":
        profile = _generate_pothole(rng, force_concurrent_turn=force_concurrent_turn, force_high_speed=force_high_speed)
    elif class_label == "sharp_turn":
        profile = _generate_sharp_turn(rng, force_evasive=force_evasive)
    elif class_label == "crash":
        profile = _generate_crash(rng, force_full_stillness=force_full_stillness)
    else:
        profile = _generate_normal(rng)

    lat, lng = _base_lat_lng(rng, cfg.GPS_SAMPLES_PER_WINDOW)

    event_id = event_id or _rng_uuid(rng)
    window = TelemetryWindow(
        event_id=event_id,
        rider_id=rider_id,
        shift_id=shift_id,
        class_label=class_label,
        is_augmented=False,
        source_event_id=event_id,
        accel_t_ms=accel_t,
        accel_x=profile["accel_x"],
        accel_y=profile["accel_y"],
        accel_z=profile["accel_z"],
        gyro_t_ms=accel_t.copy(),
        gyro_x=profile["gyro_x"],
        gyro_y=profile["gyro_y"],
        gyro_z=profile["gyro_z"],
        gps_t_ms=gps_t,
        gps_lat=lat,
        gps_lng=lng,
        gps_speed_kmh=profile["speed"],
        gps_altitude=profile["altitude"],
        gps_accuracy=profile["gps_accuracy"],
    )

    # "noisy/misaligned sensor readings": class-agnostic, can apply to any
    # class without changing its label. See apply_sensor_misalignment.
    if _resolve_force(rng, force_misalignment, cfg.SENSOR_MISALIGNMENT_PROBABILITY):
        window = apply_sensor_misalignment(window, rng)

    return window


# ---------------------------------------------------------------------------
# Augmentation
# ---------------------------------------------------------------------------


def _random_rotation_matrix(rng: np.random.Generator) -> np.ndarray:
    """A uniformly random 3D rotation matrix (simulates an arbitrary but
    fixed phone-mounting orientation). Applying this to every accel/gyro
    (x, y, z) triplet in a window changes the raw axis values but must
    leave magnitude-based features unchanged — that invariance is asserted
    in tests/test_feature_extraction.py."""
    # Random rotation via QR decomposition of a random Gaussian matrix
    # (Mezzadri's method) — uniform over SO(3) up to a sign fix.
    a = rng.normal(size=(3, 3))
    q, r = np.linalg.qr(a)
    d = np.diagonal(r)
    q = q @ np.diag(np.sign(d))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return q


def add_sensor_noise(window: TelemetryWindow, rng: np.random.Generator,
                      accel_noise_std: float = 0.05, gyro_noise_std: float = 1.0,
                      gps_speed_noise_std: float = 0.5) -> TelemetryWindow:
    n_ag = len(window.accel_x)
    n_gps = len(window.gps_speed_kmh)
    return window.copy_with(
        accel_x=window.accel_x + rng.normal(0, accel_noise_std, n_ag),
        accel_y=window.accel_y + rng.normal(0, accel_noise_std, n_ag),
        accel_z=window.accel_z + rng.normal(0, accel_noise_std, n_ag),
        gyro_x=window.gyro_x + rng.normal(0, gyro_noise_std, n_ag),
        gyro_y=window.gyro_y + rng.normal(0, gyro_noise_std, n_ag),
        gyro_z=window.gyro_z + rng.normal(0, gyro_noise_std, n_ag),
        gps_speed_kmh=np.clip(window.gps_speed_kmh + rng.normal(0, gps_speed_noise_std, n_gps), 0.0, None),
    )


def apply_time_jitter(window: TelemetryWindow, rng: np.random.Generator,
                       max_jitter_ms: float = 3.0) -> TelemetryWindow:
    """Perturbs sample timestamps (not values) to simulate irregular sensor
    callback timing. Ordering is preserved (jitter is small relative to the
    20ms sample spacing)."""
    n_ag = len(window.accel_t_ms)
    jitter = rng.uniform(-max_jitter_ms, max_jitter_ms, n_ag)
    accel_t = np.sort(window.accel_t_ms + jitter)
    return window.copy_with(accel_t_ms=accel_t, gyro_t_ms=accel_t.copy())


def apply_random_rotation(window: TelemetryWindow, rng: np.random.Generator) -> TelemetryWindow:
    rot = _random_rotation_matrix(rng)
    accel = rot @ np.vstack([window.accel_x, window.accel_y, window.accel_z])
    gyro = rot @ np.vstack([window.gyro_x, window.gyro_y, window.gyro_z])
    return window.copy_with(
        accel_x=accel[0], accel_y=accel[1], accel_z=accel[2],
        gyro_x=gyro[0], gyro_y=gyro[1], gyro_z=gyro[2],
    )


def apply_sensor_drift(window: TelemetryWindow, rng: np.random.Generator,
                        max_drift_g: float = 0.05, max_drift_deg_s: float = 2.0) -> TelemetryWindow:
    """A slow linear bias drift over the window (sensor calibration drift),
    kept deliberately subtle so it's a realism nuisance, not a
    class-changing perturbation."""
    n_ag = len(window.accel_x)
    ramp = np.linspace(0.0, 1.0, n_ag)
    accel_drift_axis = rng.integers(0, 3)
    gyro_drift_axis = rng.integers(0, 3)
    accel_drift = ramp * rng.uniform(-max_drift_g, max_drift_g) * cfg.GRAVITY_MS2
    gyro_drift = ramp * rng.uniform(-max_drift_deg_s, max_drift_deg_s)

    accel = [window.accel_x.copy(), window.accel_y.copy(), window.accel_z.copy()]
    accel[accel_drift_axis] = accel[accel_drift_axis] + accel_drift
    gyro = [window.gyro_x.copy(), window.gyro_y.copy(), window.gyro_z.copy()]
    gyro[gyro_drift_axis] = gyro[gyro_drift_axis] + gyro_drift

    return window.copy_with(
        accel_x=accel[0], accel_y=accel[1], accel_z=accel[2],
        gyro_x=gyro[0], gyro_y=gyro[1], gyro_z=gyro[2],
    )


_AUGMENTATIONS = [add_sensor_noise, apply_time_jitter, apply_random_rotation, apply_sensor_drift]


def augment_event(base: TelemetryWindow, rng: np.random.Generator, n_variants: int) -> list[TelemetryWindow]:
    """Produces `n_variants` augmented siblings of `base`. Each variant gets
    a random subset (at least one) of the augmentation functions applied,
    with randomized parameters, and is tagged is_augmented=True with
    source_event_id pointing back at `base.event_id` so grouped splitting
    (dataset.py) can keep siblings together."""
    variants = []
    for _ in range(n_variants):
        n_ops = rng.integers(1, len(_AUGMENTATIONS) + 1)
        ops = rng.choice(_AUGMENTATIONS, size=n_ops, replace=False)
        w = base
        for op in ops:
            w = op(w, rng)
        w = w.copy_with(
            event_id=_rng_uuid(rng),
            is_augmented=True,
            source_event_id=base.event_id,
        )
        variants.append(w)
    return variants


# ---------------------------------------------------------------------------
# Public: full dataset generation
# ---------------------------------------------------------------------------


def generate_dataset(
    events_per_class: int = 200,
    augmentations_per_event: int = 3,
    num_riders: int = 20,
    shifts_per_rider: int = 3,
    seed: int = 42,
) -> list[TelemetryWindow]:
    """Generates a full synthetic dataset: `events_per_class` original
    events per class, each with `augmentations_per_event` augmented
    siblings. Rider/shift ids are synthetic grouping keys, not references
    to any real database row."""
    rng = np.random.default_rng(seed)

    rider_ids = [f"synthetic-rider-{i:04d}" for i in range(num_riders)]
    shift_pool = {
        rider_id: [f"synthetic-shift-{rider_id}-{j:02d}" for j in range(shifts_per_rider)]
        for rider_id in rider_ids
    }

    windows: list[TelemetryWindow] = []
    for class_label in cfg.EVENT_CLASSES:
        for _ in range(events_per_class):
            rider_id = rng.choice(rider_ids)
            shift_id = rng.choice(shift_pool[rider_id])
            base_event = generate_event(class_label, rng, rider_id=rider_id, shift_id=shift_id)
            windows.append(base_event)
            windows.extend(augment_event(base_event, rng, augmentations_per_event))

    return windows
