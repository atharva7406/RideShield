interface Timestamped {
  timestamp: number;
}

/**
 * Generic time-windowed rolling buffer.
 *
 * Retains only samples within `windowMs` of the most recently pushed
 * sample. Eviction is time-based (not a fixed-size ring) because sensor
 * sampling rate isn't guaranteed constant — the OS can throttle it in
 * background, low-power mode, etc. Assumes samples are pushed in
 * non-decreasing timestamp order, which holds for a single live sensor
 * stream.
 */
export class RollingBuffer<T extends Timestamped> {
  private samples: T[] = [];

  constructor(private readonly windowMs: number) {}

  push(sample: T): void {
    this.samples.push(sample);
    this.evict(sample.timestamp);
  }

  private evict(latestTimestamp: number): void {
    const cutoff = latestTimestamp - this.windowMs;
    let i = 0;
    while (i < this.samples.length && this.samples[i].timestamp < cutoff) {
      i++;
    }
    if (i > 0) {
      this.samples.splice(0, i);
    }
  }

  /** Read-only view of current samples, oldest first. */
  snapshot(): readonly T[] {
    return this.samples;
  }

  latest(): T | undefined {
    return this.samples[this.samples.length - 1];
  }

  clear(): void {
    this.samples = [];
  }

  get size(): number {
    return this.samples.length;
  }
}
