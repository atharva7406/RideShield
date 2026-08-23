/**
 * V1 Prototype Calibration Values.
 *
 * These are deterministic threshold starting points.
 * Not yet scientifically validated with field crash data.
 *
 * Units:
 *  - accel magnitude is in "g" units (1.0 = resting gravity)
 *  - gyro magnitude is in deg/s
 *  - speed is in km/h
 */
export const CRASH_DETECTION_CONFIG = {
  BUFFER_WINDOW_MS: 5000,

  // Acceleration
  ACCEL_PEAK_THRESHOLD_G: 3.0,
  ACCEL_PEAK_TO_BASELINE_RATIO_THRESHOLD: 3,

  // Gyroscope (now in deg/s)
  GYRO_MAGNITUDE_THRESHOLD: 250,
  GYRO_VARIANCE_THRESHOLD: 100, // equivalent arbitrary high variance in deg/s

  // GPS / speed (now in km/h)
  SPEED_DROP_WINDOW_MS: 2000,
  SPEED_DROP_THRESHOLD_KPH: 30,

  // Post-impact stillness
  STILLNESS_WINDOW_MS: 1000,
  /** minimum span of post-peak data required before making a stillness call */
  MIN_STILLNESS_DATA_MS: 300,
  STILLNESS_ACCEL_VARIANCE_THRESHOLD: 0.05,

  // Confidence scoring is bypassed in V1, but left here for future use
  CONFIDENCE_WEIGHTS: {
    accelAnomaly: 0.4,
    gyroAnomaly: 0.2,
    speedDropDetected: 0.25,
    postImpactStillness: 0.15,
  },
  CRASH_CONFIDENCE_THRESHOLD: 0.55,
  
  // Cooldown
  CRASH_COOLDOWN_MS: 60000,
} as const;
