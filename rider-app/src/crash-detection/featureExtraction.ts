import type { AccelSample, GyroSample, GPSSample, FeatureSet } from './types';
import { CRASH_DETECTION_CONFIG as CFG } from './config';

function mean(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function variance(values: number[]): number {
  if (values.length < 2) return 0;
  const m = mean(values);
  return mean(values.map((v) => (v - m) ** 2));
}

/** Max |Δaccel / Δt| across the buffer — a sudden jolt shows up as a jerk spike. */
function computeJerk(accel: readonly AccelSample[]): number {
  if (accel.length < 2) return 0;
  let maxJerk = 0;
  for (let i = 1; i < accel.length; i++) {
    const dtSec = (accel[i].timestamp - accel[i - 1].timestamp) / 1000;
    if (dtSec <= 0) continue;
    const jerk = Math.abs(accel[i].magnitude - accel[i - 1].magnitude) / dtSec;
    if (jerk > maxJerk) maxJerk = jerk;
  }
  return maxJerk;
}

/**
 * Speed drop around a reference instant: find the fastest speed just
 * before/at the reference, then the slowest speed after it. A vehicle
 * crash or sudden stop shows up as a large, fast drop; normal
 * deceleration is gradual over a longer span.
 *
 * The window is anchored to `anchorTimestamp` (the accel-peak time, when
 * available) rather than to "now" / the latest sample. If it were
 * anchored to "now", the signal would silently vanish once the event
 * scrolls outside a fixed lookback from the current moment — which
 * happens constantly, since evaluate() may run well after the impact.
 */
function computeSpeedDrop(gps: readonly GPSSample[], anchorTimestamp: number | null): number | null {
  if (gps.length < 2) return null;

  const anchor = anchorTimestamp ?? gps[gps.length - 1].timestamp;
  const windowStart = anchor - CFG.SPEED_DROP_WINDOW_MS / 2;
  const windowEnd = anchor + CFG.SPEED_DROP_WINDOW_MS;
  const windowSamples = gps.filter((s) => s.timestamp >= windowStart && s.timestamp <= windowEnd);
  if (windowSamples.length < 2) return null;

  let maxSpeed = windowSamples[0].speed;
  let maxSpeedIndex = 0;
  windowSamples.forEach((s, i) => {
    if (s.speed > maxSpeed) {
      maxSpeed = s.speed;
      maxSpeedIndex = i;
    }
  });

  const afterPeak = windowSamples.slice(maxSpeedIndex);
  const minSpeedAfter = Math.min(...afterPeak.map((s) => s.speed));

  return maxSpeed - minSpeedAfter;
}

/**
 * Looks at accel samples collected *after* the buffer's peak sample and
 * checks whether they've settled into a low-variance "resting" state.
 * Since the buffer only holds the past, this is necessarily a partial,
 * causal read — if the peak just happened, we may not have enough
 * post-peak data yet, in which case we deliberately return false rather
 * than guess.
 */
function computePostImpactStillness(accel: readonly AccelSample[]): boolean {
  if (accel.length < 3) return false;

  let peakIndex = 0;
  let peakValue = accel[0].magnitude;
  accel.forEach((s, i) => {
    if (s.magnitude > peakValue) {
      peakValue = s.magnitude;
      peakIndex = i;
    }
  });

  const afterPeak = accel.slice(peakIndex + 1);
  if (afterPeak.length === 0) return false;

  const spanMs = afterPeak[afterPeak.length - 1].timestamp - afterPeak[0].timestamp;
  if (spanMs < CFG.MIN_STILLNESS_DATA_MS) {
    return false; // not enough post-peak data collected yet
  }

  const relevant = afterPeak.filter(
    (s) => s.timestamp <= afterPeak[0].timestamp + CFG.STILLNESS_WINDOW_MS
  );
  return variance(relevant.map((s) => s.magnitude)) < CFG.STILLNESS_ACCEL_VARIANCE_THRESHOLD;
}

export function computeFeatures(
  accel: readonly AccelSample[],
  gyro: readonly GyroSample[],
  gps: readonly GPSSample[]
): FeatureSet {
  const now = accel.length > 0 ? accel[accel.length - 1].timestamp : Date.now();

  const accelMagnitudes = accel.map((s) => s.magnitude);
  const accelGForces = accel.map((s) => s.gForce);
  const accelPeak = accelMagnitudes.length ? Math.max(...accelMagnitudes) : 0;
  const accelPeakG = accelGForces.length ? Math.max(...accelGForces) : 0;
  const accelMagnitude = accel.length ? accel[accel.length - 1].magnitude : 0;

  // Baseline and ratio computed in G-units so they stay dimensionally
  // consistent with ACCEL_PEAK_THRESHOLD_G and ACCEL_PEAK_TO_BASELINE_RATIO_THRESHOLD.
  const peakGIdx = accelGForces.indexOf(accelPeakG);
  const baselineGSamples = accelGForces.filter((_, i) => i !== peakGIdx);
  const baselineG = baselineGSamples.length ? mean(baselineGSamples) : (accelPeakG || 1);
  const peakToBaselineRatio = accelPeakG / Math.max(baselineG, 0.05);
  const accelPeakTimestamp = accel.length ? accel[peakGIdx].timestamp : null;

  const gyroMagnitudes = gyro.map((s) => s.magnitude);
  const gyroMagnitude = gyro.length ? gyro[gyro.length - 1].magnitude : 0;
  // Peak matters more than "latest" here: a tumble can happen mid-window
  // and have already settled by the time we evaluate, same reasoning as
  // accelPeak above.
  const gyroPeak = gyroMagnitudes.length ? Math.max(...gyroMagnitudes) : 0;
  const gyroVariance = variance(gyroMagnitudes);

  return {
    timestamp: now,
    accelMagnitude,
    accelPeak,
    accelPeakG,
    jerk: computeJerk(accel),
    gyroMagnitude,
    gyroPeak,
    gyroVariance,
    peakToBaselineRatio,
    speedDrop: computeSpeedDrop(gps, accelPeakTimestamp),
    postImpactStillness: computePostImpactStillness(accel),
    accelPeakTimestamp,
  };
}
