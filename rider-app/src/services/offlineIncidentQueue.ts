// ============================================================
// RideShield — Offline Incident Queue
// ============================================================
// Persistent local queue for crash-window evidence that couldn't be
// uploaded to /incidents/from-window immediately (offline, backend
// unreachable, timeout, 5xx). This is the loss-resistance layer behind
// the "connectivity must never determine whether the rider receives
// protection" rule — Tier 0 + L1 already fire before any of this runs
// (see useTelemetry.ts); this module only ever affects whether/when the
// evidence eventually reaches the backend, never whether the rider is
// alerted.
//
// One AsyncStorage key holds the whole queue as a JSON array. This is
// deliberately not SQLite/WatermelonDB — offline incidents are rare
// events (not a high-volume stream), so a single JSON blob read/written
// on each mutation is more than adequate and keeps this dependency-free.

import AsyncStorage from '@react-native-async-storage/async-storage';
import type { IncidentWindowMetadata } from '../crash-detection';

const STORAGE_KEY = 'rideshield_offline_incident_queue';

// How long a SYNCED entry is kept after success, purely so a delayed
// duplicate retry (e.g. a second app instance, or a retry racing a
// success response that got lost) can still be recognized locally.
// Not a correctness requirement (the backend is the source of truth
// once synced) — just a courtesy to avoid a pointless re-upload.
const SYNCED_RETENTION_MS = 24 * 60 * 60 * 1000; // 24h

export type QueueSyncStatus = 'PENDING' | 'SYNCED' | 'FAILED';

export interface QueuedMotionSample {
  timestamp: number;
  x: number;
  y: number;
  z: number;
}

export interface QueuedGpsSample {
  timestamp: number;
  latitude: number;
  longitude: number;
  speed: number;
}

export interface QueuedIncidentEvidence {
  accelSamples: QueuedMotionSample[];
  gyroSamples: QueuedMotionSample[];
  gpsSamples: QueuedGpsSample[];
}

export interface QueuedIncident {
  clientIncidentId: string;
  shiftId: string;
  riderId: string | null;
  /** Local device clock at the exact moment Tier 0 fired. */
  createdAt: number;
  tier0: {
    confidence: number;
    peakGForce: number;
  };
  sampleCounts: { accel: number; gyro: number; gps: number };
  samplingMetadata: {
    /** ms since epoch, timestamp precision unit for all samples above */
    timestampUnit: 'ms';
  };
  /** Raw sensor window. Set to null only after a successful sync, per the
   * storage policy below (kept until then no matter how many retries). */
  evidence: QueuedIncidentEvidence | null;
  /** Phase 3 — PRE/IMPACT/POST capture metadata (trigger timestamp, window
   * bounds, observed sampling rates, completeness/data-quality flags).
   * Optional so older-shaped queue entries (pre-Phase-3, if any survive on
   * a device across an app update) still deserialize fine. */
  windowMetadata: IncidentWindowMetadata | null;
  syncStatus: QueueSyncStatus;
  retryCount: number;
  lastRetryAt: number | null;
  lastError: string | null;
  /** Populated once the backend has acknowledged receipt. */
  backendIncidentId: string | null;
}

export type NewQueuedIncident = Pick<
  QueuedIncident,
  'clientIncidentId' | 'shiftId' | 'riderId' | 'createdAt' | 'tier0' | 'evidence'
> &
  Partial<Pick<QueuedIncident, 'windowMetadata'>>;

// ---------------------------------------------------------------------------
// Storage access — serialized through a single promise chain so concurrent
// callers (Tier 0 firing while a sync pass is mid-write) can't interleave a
// read-modify-write and silently drop each other's update.
// ---------------------------------------------------------------------------

let writeLock: Promise<unknown> = Promise.resolve();

function withLock<T>(fn: () => Promise<T>): Promise<T> {
  const result = writeLock.then(fn, fn);
  // Swallow rejection for chaining purposes only; the real error still
  // propagates to whoever awaited `result`.
  writeLock = result.catch(() => undefined);
  return result;
}

async function readAll(): Promise<QueuedIncident[]> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.warn('[offlineIncidentQueue] Failed to read queue, treating as empty:', e);
    return [];
  }
}

async function writeAll(items: QueuedIncident[]): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const offlineIncidentQueue = {
  /** Persists a new incident as PENDING. Call this BEFORE attempting the
   * upload, not after it fails — the evidence must hit disk before the
   * network call even starts, so an app crash mid-upload can't lose it. */
  async enqueue(entry: NewQueuedIncident): Promise<void> {
    await withLock(async () => {
      const items = await readAll();
      if (items.some((i) => i.clientIncidentId === entry.clientIncidentId)) {
        return; // already queued — same physical incident, ignore
      }
      const queued: QueuedIncident = {
        ...entry,
        windowMetadata: entry.windowMetadata ?? null,
        sampleCounts: {
          accel: entry.evidence?.accelSamples.length ?? 0,
          gyro: entry.evidence?.gyroSamples.length ?? 0,
          gps: entry.evidence?.gpsSamples.length ?? 0,
        },
        samplingMetadata: { timestampUnit: 'ms' },
        syncStatus: 'PENDING',
        retryCount: 0,
        lastRetryAt: null,
        lastError: null,
        backendIncidentId: null,
      };
      items.push(queued);
      await writeAll(items);
    });
  },

  async getAll(): Promise<QueuedIncident[]> {
    return readAll();
  },

  /** Entries still needing a sync attempt — PENDING or previously FAILED
   * (FAILED just means "the last attempt failed", it's still retryable,
   * distinct from SYNCED which is terminal). */
  async getPending(): Promise<QueuedIncident[]> {
    const items = await readAll();
    return items.filter((i) => i.syncStatus !== 'SYNCED');
  },

  async markSynced(clientIncidentId: string, backendIncidentId: string): Promise<void> {
    await withLock(async () => {
      const items = await readAll();
      const idx = items.findIndex((i) => i.clientIncidentId === clientIncidentId);
      if (idx === -1) return;
      items[idx] = {
        ...items[idx],
        syncStatus: 'SYNCED',
        backendIncidentId,
        lastError: null,
        // Storage policy: only drop the bulky raw evidence AFTER the
        // backend has acknowledged successful receipt — never before.
        evidence: null,
      };
      await writeAll(items);
    });
  },

  async recordFailure(clientIncidentId: string, error: string): Promise<void> {
    await withLock(async () => {
      const items = await readAll();
      const idx = items.findIndex((i) => i.clientIncidentId === clientIncidentId);
      if (idx === -1) return;
      items[idx] = {
        ...items[idx],
        syncStatus: 'FAILED',
        retryCount: items[idx].retryCount + 1,
        lastRetryAt: Date.now(),
        lastError: error,
      };
      await writeAll(items);
    });
  },

  /** Drops SYNCED entries older than the retention window. Safe to call
   * often — a no-op when there's nothing to prune. */
  async pruneSynced(now: number = Date.now()): Promise<void> {
    await withLock(async () => {
      const items = await readAll();
      const kept = items.filter(
        (i) => i.syncStatus !== 'SYNCED' || now - i.createdAt < SYNCED_RETENTION_MS
      );
      if (kept.length !== items.length) {
        await writeAll(kept);
      }
    });
  },

  /** Test/dev only. */
  async _clearAll(): Promise<void> {
    await withLock(async () => {
      await writeAll([]);
    });
  },
};
