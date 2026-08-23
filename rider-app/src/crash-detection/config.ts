/**
 * Prototype calibration values.
 *
 * These are NOT scientifically validated thresholds — they're reasonable
 * starting points for a hackathon demo, picked so the mock scenarios in
 * __tests__/mockData.ts behave sensibly. They should be re-tuned once we
 * have real collected sensor data (that's the whole reason confidence is
 * a weighted score instead of a single magic number).
 *
 * Units:
 *  - accel magnitude is in "g" units (1.0 = resting gravity), matching
 *    the gForce field already computed by useAccelerometer.
 *  - gyro magnitude is in rad/s.
 *  - speed is in m/s.
 */
export const CRASH_DETECTION_CONFIG = {
  BUFFER_WINDOW_MS: 5000,

  // Acceleration
  ACCEL_PEAK_THRESHOLD_G: 2.5,
  ACCEL_PEAK_TO_BASELINE_RATIO_THRESHOLD: 3,

  // Gyroscope
  GYRO_MAGNITUDE_THRESHOLD: 4,
  GYRO_VARIANCE_THRESHOLD: 1.5,

  // GPS / speed
  SPEED_DROP_WINDOW_MS: 2000,
  SPEED_DROP_THRESHOLD_MPS: 8,

  // Post-impact stillness
  STILLNESS_WINDOW_MS: 1000,
  /** minimum span of post-peak data required before making a stillness call */
  MIN_STILLNESS_DATA_MS: 300,
  STILLNESS_ACCEL_VARIANCE_THRESHOLD: 0.05,

  // Confidence scoring — weights sum to 1.0
  CONFIDENCE_WEIGHTS: {
    accelAnomaly: 0.4,
    gyroAnomaly: 0.2,
    speedDropDetected: 0.25,
    postImpactStillness: 0.15,
  },
  CRASH_CONFIDENCE_THRESHOLD: 0.55,
} as const;
