// ============================================================
// RideShield — Incident Sync Worker
// ============================================================
// The single controlled synchronization mechanism for the offline
// incident queue (offlineIncidentQueue.ts). Nothing else in the app is
// allowed to POST a queued incident to the backend — this keeps sync
// concurrency, retry/backoff, and dedup-on-retry all in one place
// instead of scattered across callers.
//
// Explicitly NOT a second Incident Decision Engine: this module's only
// job is getting a queued incident window to POST /incidents/from-window
// eventually. Once that succeeds, the EXISTING backend flow (ML scoring,
// fallback-safety, run_incident_escalation) takes over exactly as it
// does for an immediate online upload — see incidents.py.

import NetInfo from '@react-native-community/netinfo';
import { apiClient } from './api';
import {
  offlineIncidentQueue,
  type NewQueuedIncident,
  type QueuedIncident,
} from './offlineIncidentQueue';

// Bounded per-attempt timeout. "isConnected === true" from NetInfo is not
// trusted as reachability — this is what actually decides online/offline:
// if the real request doesn't resolve within this window, it's treated as
// a failure and queued/retried, same as an explicit network error.
const UPLOAD_TIMEOUT_MS = 8000;

const BACKOFF_BASE_MS = 5000;
const BACKOFF_FACTOR = 2;
const BACKOFF_MAX_MS = 5 * 60 * 1000; // cap so a long-offline rider doesn't wait forever once back online

let isSyncing = false;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let netInfoUnsubscribe: (() => void) | null = null;

function computeBackoffDelay(retryCount: number): number {
  return Math.min(BACKOFF_BASE_MS * Math.pow(BACKOFF_FACTOR, retryCount), BACKOFF_MAX_MS);
}

function buildPayload(item: QueuedIncident) {
  const evidence = item.evidence;
  const wm = item.windowMetadata;
  return {
    shift_id: item.shiftId,
    client_incident_id: item.clientIncidentId,
    accel_samples: (evidence?.accelSamples ?? []).map((s) => ({
      timestamp: s.timestamp,
      x: s.x,
      y: s.y,
      z: s.z,
    })),
    gyro_samples: (evidence?.gyroSamples ?? []).map((s) => ({
      timestamp: s.timestamp,
      x: s.x,
      y: s.y,
      z: s.z,
    })),
    gps_samples: (evidence?.gpsSamples ?? []).map((s) => ({
      timestamp: s.timestamp,
      latitude: s.latitude,
      longitude: s.longitude,
      speed: s.speed,
    })),
    // Phase 3 — optional, backward-compatible: PRE/IMPACT/POST capture
    // metadata so the backend can see window bounds, sample counts,
    // observed sampling rates, and completeness/data-quality flags. Old
    // app builds simply don't send this field.
    ...(wm
      ? {
          window_metadata: {
            trigger_timestamp: wm.triggerTimestamp,
            window_start_timestamp: wm.windowStartTimestamp,
            window_end_timestamp: wm.windowEndTimestamp,
            accel_sample_count: wm.sampleCounts.accel,
            gyro_sample_count: wm.sampleCounts.gyro,
            gps_sample_count: wm.sampleCounts.gps,
            observed_accel_hz: wm.observedSamplingRateHz.accel,
            observed_gyro_hz: wm.observedSamplingRateHz.gyro,
            observed_gps_hz: wm.observedSamplingRateHz.gps,
            completeness: {
              is_complete: wm.completeness.isComplete,
              has_pre_event_data: wm.completeness.hasPreEventData,
              has_post_event_data: wm.completeness.hasPostEventData,
              has_gyro: wm.completeness.hasGyro,
              has_gps: wm.completeness.hasGps,
              is_low_sampling_rate: wm.completeness.isLowSamplingRate,
              reasons: wm.completeness.reasons,
            },
          },
        }
      : {}),
  };
}

async function attemptUpload(item: QueuedIncident): Promise<boolean> {
  if (!item.evidence) {
    // Evidence already dropped (shouldn't happen for a non-SYNCED entry,
    // but guards against a corrupted/partially-migrated record).
    return true;
  }
  try {
    const res = await apiClient.post<{ incident_id: string }>(
      '/incidents/from-window',
      buildPayload(item),
      UPLOAD_TIMEOUT_MS
    );
    await offlineIncidentQueue.markSynced(item.clientIncidentId, res.incident_id);
    return true;
  } catch (err: any) {
    await offlineIncidentQueue.recordFailure(item.clientIncidentId, err?.message ?? String(err));
    return false;
  }
}

function scheduleRetry(): void {
  if (retryTimer) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
  offlineIncidentQueue.getPending().then((pending) => {
    if (pending.length === 0) return;
    const maxRetryCount = Math.max(...pending.map((p) => p.retryCount));
    const delay = computeBackoffDelay(maxRetryCount);
    retryTimer = setTimeout(() => {
      retryTimer = null;
      syncNow();
    }, delay);
  });
}

/**
 * Processes the queue sequentially (concurrency of 1 — deliberately, so a
 * flaky connection doesn't fire a burst of simultaneous uploads). Safe to
 * call from multiple triggers (NetInfo reconnect, app start, right after
 * enqueue) — the isSyncing lock makes concurrent calls collapse into one
 * pass instead of running in parallel.
 */
export async function syncNow(): Promise<void> {
  if (isSyncing) return;
  isSyncing = true;
  try {
    await offlineIncidentQueue.pruneSynced();
    const pending = await offlineIncidentQueue.getPending();
    let hitFailure = false;
    for (const item of pending) {
      const ok = await attemptUpload(item);
      if (!ok) {
        // Stop this pass on the first failure rather than hammering the
        // rest of the queue immediately — a failure here almost always
        // means "still offline/unreachable", not "this one item is bad".
        // The remaining items get picked up by the next scheduled pass.
        hitFailure = true;
        break;
      }
    }
    if (hitFailure) {
      scheduleRetry();
    }
  } finally {
    isSyncing = false;
  }
}

/**
 * Call once (e.g. on app start / shift start) to start listening for
 * connectivity restoration and to flush any incidents queued from a
 * previous session. Idempotent.
 */
export function initIncidentSync(): void {
  if (netInfoUnsubscribe) return;
  netInfoUnsubscribe = NetInfo.addEventListener((state) => {
    if (state.isConnected) {
      syncNow();
    }
  });
  syncNow();
}

export function shutdownIncidentSync(): void {
  if (netInfoUnsubscribe) {
    netInfoUnsubscribe();
    netInfoUnsubscribe = null;
  }
  if (retryTimer) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
}

/**
 * Entry point for a freshly detected incident. Durably enqueues FIRST
 * (evidence survives even if the process dies before the upload starts),
 * then kicks off a sync pass. Deliberately not awaited by callers that
 * must not block on network/storage (see useTelemetry.ts) — call this
 * fire-and-forget; L1 must already have fired before this is even called.
 */
export async function reportIncident(entry: NewQueuedIncident): Promise<void> {
  await offlineIncidentQueue.enqueue(entry);
  await syncNow();
}
