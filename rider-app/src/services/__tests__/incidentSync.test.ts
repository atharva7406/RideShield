import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiClient } from '../api';
import { offlineIncidentQueue } from '../offlineIncidentQueue';
import { reportIncident, syncNow, shutdownIncidentSync } from '../incidentSync';

jest.mock('../api', () => ({
  apiClient: { post: jest.fn() },
}));

const mockedPost = apiClient.post as jest.Mock;

function makeEvidence() {
  return {
    accelSamples: [{ timestamp: 1, x: 1, y: 1, z: 9.8 }],
    gyroSamples: [],
    gpsSamples: [],
  };
}

beforeEach(async () => {
  await AsyncStorage.clear();
  mockedPost.mockReset();
});

afterEach(() => {
  // A failed pass schedules a real backoff timer — clear it so it can't
  // fire during a later, unrelated test.
  shutdownIncidentSync();
});

describe('incidentSync — Phase 3 window metadata', () => {
  it('includes window_metadata in the upload payload when present', async () => {
    mockedPost.mockResolvedValue({ incident_id: 'backend-wm-1' });

    await reportIncident({
      clientIncidentId: 'client-wm-1',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
      windowMetadata: {
        clientIncidentId: 'client-wm-1',
        triggerTimestamp: 1000,
        windowStartTimestamp: 1,
        windowEndTimestamp: 2000,
        sampleCounts: { accel: 1, gyro: 0, gps: 0 },
        observedSamplingRateHz: { accel: 50, gyro: null, gps: null },
        completeness: {
          isComplete: false,
          hasPreEventData: true,
          hasPostEventData: false,
          hasGyro: false,
          hasGps: false,
          isLowSamplingRate: false,
          reasons: ['insufficient_post_event_samples', 'missing_gyro', 'missing_gps'],
        },
      },
    });

    const body = mockedPost.mock.calls[0][1];
    expect(body.window_metadata).toBeDefined();
    expect(body.window_metadata.trigger_timestamp).toBe(1000);
    expect(body.window_metadata.completeness.is_complete).toBe(false);
    expect(body.window_metadata.completeness.reasons).toContain('missing_gyro');
  });

  it('omits window_metadata entirely when not provided (backward compatible)', async () => {
    mockedPost.mockResolvedValue({ incident_id: 'backend-wm-2' });

    await reportIncident({
      clientIncidentId: 'client-wm-2',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });

    const body = mockedPost.mock.calls[0][1];
    expect(body.window_metadata).toBeUndefined();
  });
});

describe('incidentSync — online behavior', () => {
  it('reportIncident uploads the raw window (not a summary) including client_incident_id', async () => {
    mockedPost.mockResolvedValue({ incident_id: 'backend-1' });

    await reportIncident({
      clientIncidentId: 'client-online-1',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });

    expect(mockedPost).toHaveBeenCalledTimes(1);
    const [path, body] = mockedPost.mock.calls[0];
    expect(path).toBe('/incidents/from-window');
    expect(body.client_incident_id).toBe('client-online-1');
    expect(body.accel_samples).toEqual([{ timestamp: 1, x: 1, y: 1, z: 9.8 }]);

    const [item] = await offlineIncidentQueue.getAll();
    expect(item.syncStatus).toBe('SYNCED');
    expect(item.backendIncidentId).toBe('backend-1');
  });
});

describe('incidentSync — offline behavior', () => {
  it('a failed upload keeps the incident queued (not discarded) with the raw window intact', async () => {
    mockedPost.mockRejectedValue(new Error('Network request failed'));

    await reportIncident({
      clientIncidentId: 'client-offline-1',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });

    const [item] = await offlineIncidentQueue.getAll();
    expect(item.syncStatus).toBe('FAILED');
    expect(item.evidence).not.toBeNull();
    expect(item.evidence?.accelSamples).toHaveLength(1);
  });

  it('backend 5xx does not lose the incident', async () => {
    mockedPost.mockRejectedValue(new Error('HTTP 500'));

    await reportIncident({
      clientIncidentId: 'client-5xx',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });

    const pending = await offlineIncidentQueue.getPending();
    expect(pending.map((p) => p.clientIncidentId)).toEqual(['client-5xx']);
  });

  it('connectivity restoration (a later syncNow pass) uploads the queued incident and marks it synced', async () => {
    mockedPost.mockRejectedValueOnce(new Error('offline'));
    await reportIncident({
      clientIncidentId: 'client-retry-1',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });
    expect((await offlineIncidentQueue.getAll())[0].syncStatus).toBe('FAILED');

    mockedPost.mockResolvedValueOnce({ incident_id: 'backend-retry-1' });
    await syncNow();

    const [item] = await offlineIncidentQueue.getAll();
    expect(item.syncStatus).toBe('SYNCED');
    expect(item.backendIncidentId).toBe('backend-retry-1');
    // The same clientIncidentId was reused on retry — never a new one minted.
    expect(mockedPost.mock.calls[1][1].client_incident_id).toBe('client-retry-1');
  });

  it('a retry sends the exact same client_incident_id as the original attempt', async () => {
    mockedPost.mockRejectedValueOnce(new Error('timeout'));
    await reportIncident({
      clientIncidentId: 'client-same-id',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });

    mockedPost.mockResolvedValueOnce({ incident_id: 'backend-x' });
    await syncNow();

    const firstCallId = mockedPost.mock.calls[0][1].client_incident_id;
    const secondCallId = mockedPost.mock.calls[1][1].client_incident_id;
    expect(firstCallId).toBe('client-same-id');
    expect(secondCallId).toBe('client-same-id');
  });
});

describe('incidentSync — queue/concurrency behavior', () => {
  it('does not run two sync passes concurrently', async () => {
    let resolveFirst: (v: { incident_id: string }) => void;
    const firstCallPromise = new Promise<{ incident_id: string }>((resolve) => {
      resolveFirst = resolve;
    });
    mockedPost.mockReturnValueOnce(firstCallPromise);

    await offlineIncidentQueue.enqueue({
      clientIncidentId: 'client-concurrent-1',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });

    const pass1 = syncNow();
    const pass2 = syncNow(); // should collapse into a no-op while pass1 is in flight

    resolveFirst!({ incident_id: 'backend-concurrent-1' });
    await Promise.all([pass1, pass2]);

    // Only one upload attempt was made despite two syncNow() calls overlapping.
    expect(mockedPost).toHaveBeenCalledTimes(1);
  });

  it('processes multiple queued incidents sequentially on a successful pass', async () => {
    mockedPost.mockResolvedValue({ incident_id: 'backend-seq' });

    await offlineIncidentQueue.enqueue({
      clientIncidentId: 'seq-1',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });
    await offlineIncidentQueue.enqueue({
      clientIncidentId: 'seq-2',
      shiftId: 'shift-1',
      riderId: null,
      createdAt: Date.now(),
      tier0: { confidence: 0.9, peakGForce: 6.1 },
      evidence: makeEvidence(),
    });

    await syncNow();

    expect(mockedPost).toHaveBeenCalledTimes(2);
    const all = await offlineIncidentQueue.getAll();
    expect(all.every((i) => i.syncStatus === 'SYNCED')).toBe(true);
  });
});
