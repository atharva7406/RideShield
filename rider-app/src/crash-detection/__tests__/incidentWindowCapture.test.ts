import { CrashDetector } from '../crashDetector';
import { captureIncidentWindow } from '../incidentWindowCapture';
import type { AccelSample, GyroSample, GPSSample } from '../types';

// Real timers with a tiny override — captureIncidentWindow's
// postEventCaptureMs is deliberately overridable only for tests (see its
// doc comment), so this exercises the real wait/finalize logic without
// needing fake-timer/promise-flush gymnastics.
const TEST_POST_EVENT_MS = 30;

function accel(timestamp: number, gForce = 1.0): AccelSample {
  return { x: 0.1, y: 0.1, z: 9.8, magnitude: gForce * 9.81, gForce, timestamp };
}

function gyro(timestamp: number, magnitude = 1.7): GyroSample {
  return { x: 1, y: 1, z: 1, magnitude, timestamp };
}

function gps(timestamp: number, speed = 20): GPSSample {
  return { latitude: 19.07, longitude: 72.87, speed, timestamp };
}

describe('captureIncidentWindow', () => {
  it('preserves pre-event samples that predate the trigger', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 20; i >= 1; i--) {
      detector.pushAccel(accel(triggerTs - i * 20));
    }
    detector.pushAccel(accel(triggerTs, 6.0));

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'pre-event-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    const preSamples = result.accelSamples.filter((s) => s.timestamp < triggerTs);
    expect(preSamples.length).toBeGreaterThanOrEqual(19);
    expect(result.metadata.completeness.hasPreEventData).toBe(true);
  });

  it('captures post-event samples pushed after the trigger, before finalizing', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 15; i >= 1; i--) {
      detector.pushAccel(accel(triggerTs - i * 20));
    }
    detector.pushAccel(accel(triggerTs, 6.0));

    const capturePromise = captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'post-event-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    // Simulates sensor streaming continuing in real time while the window
    // is still "capturing post-event" — this is the actual post-impact
    // tail, pushed via the same live buffer real sensors write to.
    for (let i = 1; i <= 10; i++) {
      detector.pushAccel(accel(triggerTs + i * 2));
    }

    const result = await capturePromise;

    const postSamples = result.accelSamples.filter((s) => s.timestamp > triggerTs);
    expect(postSamples.length).toBeGreaterThan(0);
    expect(result.metadata.completeness.hasPostEventData).toBe(true);
  });

  it('finalized window contains PRE + IMPACT + POST regions', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 20; i >= 1; i--) detector.pushAccel(accel(triggerTs - i * 20));
    detector.pushAccel(accel(triggerTs, 6.0)); // impact sample

    const capturePromise = captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'full-window-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });
    for (let i = 1; i <= 10; i++) detector.pushAccel(accel(triggerTs + i * 2));

    const result = await capturePromise;

    expect(result.accelSamples.some((s) => s.timestamp < triggerTs)).toBe(true);
    expect(result.accelSamples.some((s) => s.timestamp === triggerTs)).toBe(true);
    expect(result.accelSamples.some((s) => s.timestamp > triggerTs)).toBe(true);
    expect(result.metadata.completeness.isComplete).toBe(true);
  });

  it('samples in the finalized window are chronologically ordered', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    // Pushed out of order on purpose.
    detector.pushAccel(accel(triggerTs - 40));
    detector.pushAccel(accel(triggerTs - 100));
    detector.pushAccel(accel(triggerTs - 20));
    detector.pushAccel(accel(triggerTs, 6.0));

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'ordering-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    const timestamps = result.accelSamples.map((s) => s.timestamp);
    const sorted = [...timestamps].sort((a, b) => a - b);
    expect(timestamps).toEqual(sorted);
  });

  it('duplicate samples are collapsed rather than duplicated in the window', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    const dupe = accel(triggerTs - 20);
    detector.pushAccel(dupe);
    detector.pushAccel({ ...dupe }); // exact duplicate reading at the exact same timestamp
    detector.pushAccel(accel(triggerTs, 6.0));

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'dupe-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    const atDupeTs = result.accelSamples.filter((s) => s.timestamp === dupe.timestamp);
    expect(atDupeTs).toHaveLength(1);
  });

  it('gyro and GPS data are retained in the finalized window alongside accel', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 15; i >= 1; i--) {
      detector.pushAccel(accel(triggerTs - i * 20));
      detector.pushGyro(gyro(triggerTs - i * 20));
      detector.pushGPS(gps(triggerTs - i * 200));
    }
    detector.pushAccel(accel(triggerTs, 6.0));
    detector.pushGyro(gyro(triggerTs, 260));

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'multi-modal-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    expect(result.gyroSamples.length).toBeGreaterThan(0);
    expect(result.gpsSamples.length).toBeGreaterThan(0);
    expect(result.metadata.completeness.hasGyro).toBe(true);
    expect(result.metadata.completeness.hasGps).toBe(true);
  });

  it('flags a window with too few pre-event samples as incomplete, without throwing', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    detector.pushAccel(accel(triggerTs - 20)); // only 1 pre-event sample, well under MIN_PRE_EVENT_SAMPLES
    detector.pushAccel(accel(triggerTs, 6.0));

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'sparse-pre-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    expect(result.metadata.completeness.isComplete).toBe(false);
    expect(result.metadata.completeness.hasPreEventData).toBe(false);
    expect(result.metadata.completeness.reasons).toContain('insufficient_pre_event_samples');
  });

  it('flags a window with no post-event samples as incomplete (app backgrounded / interrupted), without throwing', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 15; i >= 1; i--) detector.pushAccel(accel(triggerTs - i * 20));
    detector.pushAccel(accel(triggerTs, 6.0));
    // No samples pushed during the wait — simulates the app being
    // backgrounded / sensors stalling right after the trigger.

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'no-post-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    expect(result.metadata.completeness.isComplete).toBe(false);
    expect(result.metadata.completeness.hasPostEventData).toBe(false);
    expect(result.accelSamples.length).toBeGreaterThan(0); // evidence still returned, not discarded
  });

  it('flags missing gyro/GPS modalities as incomplete without throwing', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 15; i >= 1; i--) detector.pushAccel(accel(triggerTs - i * 20));
    detector.pushAccel(accel(triggerTs, 6.0));
    // Never push gyro or GPS at all.

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'missing-modality-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    expect(result.metadata.completeness.hasGyro).toBe(false);
    expect(result.metadata.completeness.hasGps).toBe(false);
    expect(result.metadata.completeness.reasons).toEqual(
      expect.arrayContaining(['missing_gyro', 'missing_gps'])
    );
  });

  it('malformed (NaN/non-finite) timestamps are dropped rather than crashing the pipeline', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 15; i >= 1; i--) detector.pushAccel(accel(triggerTs - i * 20));
    detector.pushAccel({ ...accel(NaN), gForce: 6.0 }); // malformed sample
    detector.pushAccel(accel(triggerTs, 6.0));

    await expect(
      captureIncidentWindow({
        detector,
        triggerTimestamp: triggerTs,
        clientIncidentId: 'malformed-ts-test',
        postEventCaptureMs: TEST_POST_EVENT_MS,
      })
    ).resolves.toBeDefined();
  });

  it('flags a low observed sampling rate without throwing', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    // Sparse, far-apart samples — well under LOW_SAMPLING_RATE_THRESHOLD_HZ.
    for (let i = 10; i >= 1; i--) detector.pushAccel(accel(triggerTs - i * 500));
    detector.pushAccel(accel(triggerTs, 6.0));

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'low-rate-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    expect(result.metadata.completeness.isLowSamplingRate).toBe(true);
    expect(result.metadata.completeness.isComplete).toBe(false);
  });

  it('metadata carries the clientIncidentId and sample counts unchanged', async () => {
    const detector = new CrashDetector();
    const triggerTs = Date.now();
    for (let i = 15; i >= 1; i--) detector.pushAccel(accel(triggerTs - i * 20));
    detector.pushAccel(accel(triggerTs, 6.0));

    const result = await captureIncidentWindow({
      detector,
      triggerTimestamp: triggerTs,
      clientIncidentId: 'metadata-test',
      postEventCaptureMs: TEST_POST_EVENT_MS,
    });

    expect(result.metadata.clientIncidentId).toBe('metadata-test');
    expect(result.metadata.triggerTimestamp).toBe(triggerTs);
    expect(result.metadata.sampleCounts.accel).toBe(result.accelSamples.length);
  });
});
