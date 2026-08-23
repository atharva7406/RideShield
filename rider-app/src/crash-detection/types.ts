/**
 * RideShield — Crash Detection / Edge Intelligence Core
 * Framework-agnostic types. No React Native / Expo imports here —
 * this module knows nothing about hooks, phones, or Expo sensors.
 */

export interface AccelSample {
  x: number;
  y: number;
  z: number;
  /** sqrt(x^2 + y^2 + z^2) — same convention as the existing useAccelerometer hook */
  magnitude: number;
  timestamp: number; // ms since epoch
}

export interface GyroSample {
  x: number;
  y: number;
  z: number;
  /** sqrt(x^2 + y^2 + z^2), rad/s */
  magnitude: number;
  timestamp: number; // ms since epoch
}

export interface GPSSample {
  speed: number; // m/s
  latitude: number;
  longitude: number;
  timestamp: number; // ms since epoch
}

export interface FeatureSet {
  timestamp: number;

  accelMagnitude: number;
  accelPeak: number;
  jerk: number; // max |d(accel)/dt| over the window

  gyroMagnitude: number;
  gyroPeak: number;
  gyroVariance: number;

  peakToBaselineRatio: number;

  /** m/s speed drop over the configured window; null if no GPS context available */
  speedDrop: number | null;

  postImpactStillness: boolean;
}

export interface CrashSignals {
  accelAnomaly: boolean;
  gyroAnomaly: boolean;
  speedDropDetected: boolean;
  postImpactStillness: boolean;
}

export interface CrashResult {
  isCrashCandidate: boolean;
  confidence: number; // 0-1
  signals: CrashSignals;
  features: FeatureSet;
  timestamp: number;
}
