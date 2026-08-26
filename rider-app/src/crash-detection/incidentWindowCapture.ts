// ============================================================
// RideShield — PRE/IMPACT/POST Incident Window Capture
// ============================================================
// Turns a Tier-0 trigger into a deliberate, evidence-quality sensor
// window instead of "whatever the rolling buffer happens to hold at the
// instant evaluate() fires". Lifecycle:
//
//   NORMAL
//     -> Tier 0 POSSIBLE INCIDENT (caller's job, not this module's)
//     -> CAPTURING_POST_EVENT (this module: wait POST_EVENT_CAPTURE_MS)
//     -> FINALIZE (slice PRE + IMPACT + POST out of the buffer, sanitize,
//                  compute completeness/data-quality metadata)
//
// Does NOT touch L1 or the safety alert — those already fired, synchronously,
// before this module is ever called (see useTelemetry.ts). This module's
// only job is producing the best evidence window for upload; it must never
// be on the critical path for rider safety.

import type { AccelSample, GyroSample, GPSSample } from './types';
import type { CrashDetector } from './crashDetector';
import { CRASH_DETECTION_CONFIG as CFG } from './config';

export interface WindowCompleteness {
  isComplete: boolean;
  hasPreEventData: boolean;
  hasPostEventData: boolean;
  hasGyro: boolean;
  hasGps: boolean;
  isLowSamplingRate: boolean;
  reasons: string[];
}

export interface IncidentWindowMetadata {
  clientIncidentId: string;
  /** The physical impact instant (accelPeakTimestamp), not "now". */
  triggerTimestamp: number;
  windowStartTimestamp: number | null;
  windowEndTimestamp: number | null;
  sampleCounts: { accel: number; gyro: number; gps: number };
  observedSamplingRateHz: { accel: number | null; gyro: number | null; gps: number | null };
  completeness: WindowCompleteness;
}

export interface FinalizedIncidentWindow {
  metadata: IncidentWindowMetadata;
  accelSamples: AccelSample[];
  gyroSamples: GyroSample[];
  gpsSamples: GPSSample[];
}

/**
 * Drops non-finite/garbage timestamps, sorts chronologically, and removes
 * exact duplicate samples — malformed input (a sensor glitch, a clock
 * jump) must degrade the window's completeness, never throw and take the
 * evidence pipeline down with it.
 */
function sanitizeSamples<T extends { timestamp: number }>(samples: readonly T[]): T[] {
  const finite = samples.filter((s) => Number.isFinite(s.timestamp));
  const sorted = [...finite].sort((a, b) => a.timestamp - b.timestamp);
  const deduped: T[] = [];
  for (const s of sorted) {
    const prev = deduped[deduped.length - 1];
    if (prev && prev.timestamp === s.timestamp && JSON.stringify(prev) === JSON.stringify(s)) {
      continue; // exact duplicate (same timestamp AND same reading)
    }
    deduped.push(s);
  }
  return deduped;
}

function sliceToWindow<T extends { timestamp: number }>(
  samples: readonly T[],
  startMs: number,
  endMs: number
): T[] {
  return samples.filter((s) => s.timestamp >= startMs && s.timestamp <= endMs);
}

function observedRateHz(samples: readonly { timestamp: number }[]): number | null {
  if (samples.length < 2) return null;
  const spanMs = samples[samples.length - 1].timestamp - samples[0].timestamp;
  if (spanMs <= 0) return null;
  return ((samples.length - 1) / spanMs) * 1000;
}

function buildCompleteness(
  triggerTimestamp: number,
  accel: readonly AccelSample[],
  gyro: readonly GyroSample[],
  gps: readonly GPSSample[]
): WindowCompleteness {
  const preCount = accel.filter((s) => s.timestamp < triggerTimestamp).length;
  const postCount = accel.filter((s) => s.timestamp > triggerTimestamp).length;
  const rate = observedRateHz(accel);

  const hasPreEventData = preCount >= CFG.MIN_PRE_EVENT_SAMPLES;
  const hasPostEventData = postCount >= CFG.MIN_POST_EVENT_SAMPLES;
  const hasGyro = gyro.length > 0;
  const hasGps = gps.length > 0;
  const isLowSamplingRate = rate !== null && rate < CFG.LOW_SAMPLING_RATE_THRESHOLD_HZ;

  const reasons: string[] = [];
  if (!hasPreEventData) reasons.push('insufficient_pre_event_samples');
  if (!hasPostEventData) reasons.push('insufficient_post_event_samples');
  if (!hasGyro) reasons.push('missing_gyro');
  if (!hasGps) reasons.push('missing_gps');
  if (isLowSamplingRate) reasons.push('low_sampling_rate');
  if (rate === null) reasons.push('rate_unknown');

  return {
    isComplete: hasPreEventData && hasPostEventData && !isLowSamplingRate,
    hasPreEventData,
    hasPostEventData,
    hasGyro,
    hasGps,
    isLowSamplingRate,
    reasons,
  };
}

/**
 * Waits POST_EVENT_CAPTURE_MS after `triggerTimestamp`, then finalizes the
 * incident window. Deliberately NOT cancelable by the caller unmounting —
 * this is short-lived (<= POST_EVENT_CAPTURE_MS) evidence capture for an
 * already-fired alert, not something that should be silently dropped by a
 * screen transition.
 */
export function captureIncidentWindow(params: {
  detector: CrashDetector;
  triggerTimestamp: number;
  clientIncidentId: string;
  /** Overridable only for tests; real callers always use the config default. */
  postEventCaptureMs?: number;
}): Promise<FinalizedIncidentWindow> {
  const { detector, triggerTimestamp, clientIncidentId } = params;
  const postEventCaptureMs = params.postEventCaptureMs ?? CFG.POST_EVENT_CAPTURE_MS;

  return new Promise((resolve) => {
    setTimeout(() => {
      const windowStart = triggerTimestamp - CFG.PRE_EVENT_CAPTURE_MS;
      const windowEnd = triggerTimestamp + postEventCaptureMs;

      const accel = sliceToWindow(sanitizeSamples(detector.getAccelSnapshot()), windowStart, windowEnd);
      const gyro = sliceToWindow(sanitizeSamples(detector.getGyroSnapshot()), windowStart, windowEnd);
      const gps = sliceToWindow(sanitizeSamples(detector.getGPSSnapshot()), windowStart, windowEnd);

      const metadata: IncidentWindowMetadata = {
        clientIncidentId,
        triggerTimestamp,
        windowStartTimestamp: accel.length ? accel[0].timestamp : null,
        windowEndTimestamp: accel.length ? accel[accel.length - 1].timestamp : null,
        sampleCounts: { accel: accel.length, gyro: gyro.length, gps: gps.length },
        observedSamplingRateHz: {
          accel: observedRateHz(accel),
          gyro: observedRateHz(gyro),
          gps: observedRateHz(gps),
        },
        completeness: buildCompleteness(triggerTimestamp, accel, gyro, gps),
      };

      resolve({ metadata, accelSamples: accel, gyroSamples: gyro, gpsSamples: gps });
    }, postEventCaptureMs);
  });
}
