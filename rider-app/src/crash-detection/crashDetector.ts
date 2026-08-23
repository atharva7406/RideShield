import type {
  AccelSample,
  GyroSample,
  GPSSample,
  CrashResult,
  CrashSignals,
  FeatureSet,
} from './types';
import { RollingBuffer } from './sensorBuffer';
import { computeFeatures } from './featureExtraction';
import { CRASH_DETECTION_CONFIG as CFG } from './config';

export class CrashDetector {
  private accelBuffer = new RollingBuffer<AccelSample>(CFG.BUFFER_WINDOW_MS);
  private gyroBuffer = new RollingBuffer<GyroSample>(CFG.BUFFER_WINDOW_MS);
  private gpsBuffer = new RollingBuffer<GPSSample>(CFG.BUFFER_WINDOW_MS);

  pushAccel(sample: AccelSample): void {
    this.accelBuffer.push(sample);
  }

  pushGyro(sample: GyroSample): void {
    this.gyroBuffer.push(sample);
  }

  pushGPS(sample: GPSSample): void {
    this.gpsBuffer.push(sample);
  }

  clear(): void {
    this.accelBuffer.clear();
    this.gyroBuffer.clear();
    this.gpsBuffer.clear();
  }

  /** Evaluate current buffer state and return a crash assessment. */
  evaluate(): CrashResult {
    const features = computeFeatures(
      this.accelBuffer.snapshot(),
      this.gyroBuffer.snapshot(),
      this.gpsBuffer.snapshot()
    );

    const signals = this.deriveSignals(features);
    const confidence = this.computeConfidence(signals);

    // Design rule: a raw acceleration spike is necessary but never
    // sufficient on its own (that's what a phone drop looks like too).
    // We require at least one corroborating signal — gyro tumble or a
    // real speed loss — before calling it a crash candidate.
    const corroborated = signals.gyroAnomaly || signals.speedDropDetected;

    return {
      // V1 Deterministic Rule: High G AND (Abnormal Gyro OR Speed Drop)
      isCrashCandidate: signals.accelAnomaly && corroborated,
      confidence,
      signals,
      features,
      timestamp: features.timestamp,
    };
  }

  private deriveSignals(f: FeatureSet): CrashSignals {
    return {
      accelAnomaly:
        f.accelPeakG >= CFG.ACCEL_PEAK_THRESHOLD_G &&
        f.peakToBaselineRatio >= CFG.ACCEL_PEAK_TO_BASELINE_RATIO_THRESHOLD,
      gyroAnomaly:
        f.gyroPeak >= CFG.GYRO_MAGNITUDE_THRESHOLD || f.gyroVariance >= CFG.GYRO_VARIANCE_THRESHOLD,
      speedDropDetected: f.speedDrop !== null && f.speedDrop >= CFG.SPEED_DROP_THRESHOLD_KPH,
      postImpactStillness: f.postImpactStillness,
    };
  }

  private computeConfidence(signals: CrashSignals): number {
    const w = CFG.CONFIDENCE_WEIGHTS;
    let score = 0;
    if (signals.accelAnomaly) score += w.accelAnomaly;
    if (signals.gyroAnomaly) score += w.gyroAnomaly;
    if (signals.speedDropDetected) score += w.speedDropDetected;
    if (signals.postImpactStillness) score += w.postImpactStillness;
    return Math.min(1, score);
  }
}
