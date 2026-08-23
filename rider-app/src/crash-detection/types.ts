/**
 * RideShield — Crash Detection / Edge Intelligence Core
 * Framework-agnostic types. No React Native / Expo imports here —
 * this module knows nothing about hooks, phones, or Expo sensors.
 */

export interface AccelSample {
  x: number;
  y: number;
  z: number;
  /** sqrt(x^2 + y^2 + z^2) in m/s² (raw sensor units) */
  magnitude: number;
  /** magnitude / 9.81 — G-force units, used for crash threshold comparisons */
  gForce: number;
  timestamp: number; // ms since epoch
}

export interface GyroSample {
  x: number;
  y: number;
  z: number;
  /** sqrt(x^2 + y^2 + z^2), deg/s — converted from rad/s by useGyroscope */
  magnitude: number;
  timestamp: number; // ms since epoch
}

export interface GPSSample {
  speed: number; // km/h — useTelemetry pushes loc.speedKmh
  latitude: number;
  longitude: number;
  timestamp: number; // ms since epoch
}

export interface FeatureSet {
  timestamp: number;

  accelMagnitude: number; // m/s²
  accelPeak: number;      // m/s²
  /** Peak acceleration converted to G-force — used for threshold comparisons */
  accelPeakG: number;     // G
  jerk: number; // max |d(accel)/dt| over the window

  gyroMagnitude: number;  // deg/s
  gyroPeak: number;       // deg/s
  gyroVariance: number;   // (deg/s)²

  peakToBaselineRatio: number;

  /** km/h speed drop over the configured window; null if no GPS context available */
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
