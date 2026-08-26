import AsyncStorage from '@react-native-async-storage/async-storage';
import { offlineIncidentQueue, type NewQueuedIncident } from '../offlineIncidentQueue';

function makeEntry(overrides: Partial<NewQueuedIncident> = {}): NewQueuedIncident {
  return {
    clientIncidentId: 'client-1',
    shiftId: 'shift-1',
    riderId: null,
    createdAt: Date.now(),
    tier0: { confidence: 0.9, peakGForce: 5.2 },
    evidence: {
      accelSamples: [{ timestamp: 1, x: 1, y: 1, z: 9.8 }],
      gyroSamples: [{ timestamp: 1, x: 0, y: 0, z: 0 }],
      gpsSamples: [{ timestamp: 1, latitude: 19.07, longitude: 72.87, speed: 20 }],
    },
    ...overrides,
  };
}

beforeEach(async () => {
  await AsyncStorage.clear();
});

describe('offlineIncidentQueue', () => {
  it('enqueues an incident as PENDING with the raw evidence intact', async () => {
    await offlineIncidentQueue.enqueue(makeEntry());
    const all = await offlineIncidentQueue.getAll();
    expect(all).toHaveLength(1);
    expect(all[0].syncStatus).toBe('PENDING');
    expect(all[0].evidence?.accelSamples).toHaveLength(1);
    expect(all[0].sampleCounts).toEqual({ accel: 1, gyro: 1, gps: 1 });
    expect(all[0].retryCount).toBe(0);
  });

  it('does not create a duplicate entry for the same clientIncidentId', async () => {
    await offlineIncidentQueue.enqueue(makeEntry());
    await offlineIncidentQueue.enqueue(makeEntry());
    const all = await offlineIncidentQueue.getAll();
    expect(all).toHaveLength(1);
  });

  it('getPending excludes SYNCED entries', async () => {
    await offlineIncidentQueue.enqueue(makeEntry({ clientIncidentId: 'a' }));
    await offlineIncidentQueue.enqueue(makeEntry({ clientIncidentId: 'b' }));
    await offlineIncidentQueue.markSynced('a', 'backend-incident-1');

    const pending = await offlineIncidentQueue.getPending();
    expect(pending.map((p) => p.clientIncidentId)).toEqual(['b']);
  });

  it('markSynced drops the raw evidence but keeps identifying metadata', async () => {
    await offlineIncidentQueue.enqueue(makeEntry());
    await offlineIncidentQueue.markSynced('client-1', 'backend-incident-1');

    const [item] = await offlineIncidentQueue.getAll();
    expect(item.syncStatus).toBe('SYNCED');
    expect(item.backendIncidentId).toBe('backend-incident-1');
    expect(item.evidence).toBeNull();
    expect(item.clientIncidentId).toBe('client-1');
  });

  it('recordFailure increments retryCount and keeps the raw evidence for the next attempt', async () => {
    await offlineIncidentQueue.enqueue(makeEntry());
    await offlineIncidentQueue.recordFailure('client-1', 'network timeout');
    await offlineIncidentQueue.recordFailure('client-1', 'network timeout');

    const [item] = await offlineIncidentQueue.getAll();
    expect(item.syncStatus).toBe('FAILED');
    expect(item.retryCount).toBe(2);
    expect(item.lastError).toBe('network timeout');
    expect(item.evidence).not.toBeNull();
    expect(item.evidence?.accelSamples).toHaveLength(1);
  });

  it('a FAILED entry still shows up in getPending (it is retryable, not terminal)', async () => {
    await offlineIncidentQueue.enqueue(makeEntry());
    await offlineIncidentQueue.recordFailure('client-1', 'offline');
    const pending = await offlineIncidentQueue.getPending();
    expect(pending).toHaveLength(1);
  });

  it('pruneSynced removes only old SYNCED entries, never PENDING/FAILED ones', async () => {
    const oldCreatedAt = Date.now() - 48 * 60 * 60 * 1000; // 48h ago
    await offlineIncidentQueue.enqueue(makeEntry({ clientIncidentId: 'old-synced', createdAt: oldCreatedAt }));
    await offlineIncidentQueue.markSynced('old-synced', 'backend-1');

    await offlineIncidentQueue.enqueue(makeEntry({ clientIncidentId: 'recent-pending' }));

    await offlineIncidentQueue.pruneSynced();

    const all = await offlineIncidentQueue.getAll();
    expect(all.map((i) => i.clientIncidentId)).toEqual(['recent-pending']);
  });
});
