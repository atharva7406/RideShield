import { RollingBuffer } from '../sensorBuffer';

describe('RollingBuffer', () => {
  it('retains samples within the window', () => {
    const buf = new RollingBuffer<{ timestamp: number }>(1000);
    buf.push({ timestamp: 0 });
    buf.push({ timestamp: 500 });
    buf.push({ timestamp: 900 });
    expect(buf.size).toBe(3);
  });

  it('evicts samples older than the window relative to the latest push', () => {
    const buf = new RollingBuffer<{ timestamp: number }>(1000);
    buf.push({ timestamp: 0 });
    buf.push({ timestamp: 1500 }); // cutoff becomes 500, evicts timestamp 0
    buf.push({ timestamp: 1600 }); // cutoff becomes 600, timestamp 1500 survives
    expect(buf.size).toBe(2);
    expect(buf.snapshot()[0].timestamp).toBe(1500);
  });

  it('clears all samples', () => {
    const buf = new RollingBuffer<{ timestamp: number }>(1000);
    buf.push({ timestamp: 0 });
    buf.clear();
    expect(buf.size).toBe(0);
  });

  it('returns the latest sample', () => {
    const buf = new RollingBuffer<{ timestamp: number }>(1000);
    buf.push({ timestamp: 0 });
    buf.push({ timestamp: 200 });
    expect(buf.latest()?.timestamp).toBe(200);
  });

  it('does not grow unbounded as samples keep arriving', () => {
    const buf = new RollingBuffer<{ timestamp: number }>(5000);
    for (let t = 0; t <= 60000; t += 20) {
      buf.push({ timestamp: t });
    }
    // ~5000ms window / 20ms interval ≈ 250 samples, plus one
    expect(buf.size).toBeLessThanOrEqual(252);
  });
});
