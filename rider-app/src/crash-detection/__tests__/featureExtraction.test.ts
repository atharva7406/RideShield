import { computeFeatures } from '../featureExtraction';
import type { AccelSample, GyroSample, GPSSample } from '../types';

function accel(magnitude: number, timestamp: number): AccelSample {
  return { x: 0, y: 0, z: magnitude, magnitude, timestamp };
}
function gyro(magnitude: number, timestamp: number): GyroSample {
  return { x: 0, y: 0, z: magnitude, magnitude, timestamp };
}
function gps(speed: number, timestamp: number): GPSSample {
  return { speed, latitude: 0, longitude: 0, timestamp };
}

describe('computeFeatures', () => {
  it('reports zeros for an empty buffer', () => {
    const f = computeFeatures([], [], []);
    expect(f.accelPeak).toBe(0);
    expect(f.accelMagnitude).toBe(0);
    expect(f.speedDrop).toBeNull();
    expect(f.postImpactStillness).toBe(false);
  });

  it('finds the peak and a high peak-to-baseline ratio for a spike', () => {
    const samples = [
      accel(1.0, 0),
      accel(1.0, 20),
      accel(1.0, 40),
      accel(5.0, 60), // spike
      accel(1.0, 80),
    ];
    const f = computeFeatures(samples, [], []);
    expect(f.accelPeak).toBe(5.0);
    expect(f.peakToBaselineRatio).toBeGreaterThan(3);
  });

  it('computes jerk as the largest magnitude delta over time', () => {
    const samples = [accel(1.0, 0), accel(1.0, 20), accel(5.0, 40)];
    const f = computeFeatures(samples, [], []);
    // (5.0 - 1.0) / 0.02s = 200
    expect(f.jerk).toBeCloseTo(200, 0);
  });

  it('computes gyro variance as roughly zero for a constant signal', () => {
    const samples = [gyro(0.5, 0), gyro(0.5, 20), gyro(0.5, 40)];
    const f = computeFeatures([], samples, []);
    expect(f.gyroVariance).toBeCloseTo(0, 5);
  });

  it('returns null speedDrop with fewer than 2 GPS samples', () => {
    const f = computeFeatures([], [], [gps(10, 0)]);
    expect(f.speedDrop).toBeNull();
  });

  it('detects a real speed drop within the window', () => {
    const samples = [gps(15, 0), gps(15, 500), gps(5, 1000), gps(4, 1500)];
    const f = computeFeatures([], [], samples);
    expect(f.speedDrop).toBeCloseTo(11, 0);
  });

  it('does not flag stillness without enough post-peak data', () => {
    const samples = [accel(1.0, 0), accel(5.0, 20)]; // peak is the last sample
    const f = computeFeatures(samples, [], []);
    expect(f.postImpactStillness).toBe(false);
  });

  it('flags stillness when post-peak samples settle to low variance', () => {
    const samples = [
      accel(1.0, 0),
      accel(5.0, 100), // peak
      accel(1.0, 300),
      accel(1.01, 500),
      accel(0.99, 700),
      accel(1.0, 900),
    ];
    const f = computeFeatures(samples, [], []);
    expect(f.postImpactStillness).toBe(true);
  });
});
