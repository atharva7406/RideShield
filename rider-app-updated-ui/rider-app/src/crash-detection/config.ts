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
  // Raised from an initial 3.0G — real-device testing showed a firm
  // hand-shake alone clears 3.0G + a 3x baseline ratio, since a held
  // phone amplifies deliberate wrist motion the same way a real impact
  // would. Real crash impacts are typically well above 10G; 4.5G/4x still
  // leaves comfortable headroom below that while filtering out normal
  // handling. Still a documented, tunable placeholder, not validated
  // against real crash data.
  ACCEL_PEAK_THRESHOLD_G: 4.5,
  ACCEL_PEAK_TO_BASELINE_RATIO_THRESHOLD: 4,

  // Gyroscope (now in deg/s) — raised alongside the accel threshold for
  // the same reason: a deliberate hand-shake rotates the phone enough to
  // also clear the old 250 deg/s corroboration threshold.
  GYRO_MAGNITUDE_THRESHOLD: 350,
  GYRO_VARIANCE_THRESHOLD: 150, // equivalent arbitrary high variance in deg/s

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

  // ---------------------------------------------------------------------
  // Phase 3: PRE/IMPACT/POST incident-window capture.
  //
  // Derived from BUFFER_WINDOW_MS above, not hardcoded independently: the
  // rolling buffer already retains BUFFER_WINDOW_MS of history ending at
  // "now". If we wait POST_EVENT_CAPTURE_MS after the trigger before
  // taking the final snapshot, the buffer's own trailing window naturally
  // still holds (BUFFER_WINDOW_MS - POST_EVENT_CAPTURE_MS) of genuine
  // pre-event data — no separate "freeze" copy or buffer enlargement
  // needed. PRE_EVENT_CAPTURE_MS + POST_EVENT_CAPTURE_MS must not exceed
  // BUFFER_WINDOW_MS or the pre-event end would already be evicted by the
  // time of the final snapshot.
  PRE_EVENT_CAPTURE_MS: 3000,
  POST_EVENT_CAPTURE_MS: 2000,

  // Below these, a window is flagged incomplete (not discarded — see
  // incidentWindowCapture.ts). Set well under the ~150/~100 samples a
  // full 3s/2s span would hold at nominal 50Hz, so only genuine
  // degradation (backgrounding, sensor stalls, OS throttling) trips them.
  MIN_PRE_EVENT_SAMPLES: 10,
  MIN_POST_EVENT_SAMPLES: 10,

  // Below this observed rate, a window is flagged as low-sampling-rate
  // even if it technically has "enough" samples by count.
  LOW_SAMPLING_RATE_THRESHOLD_HZ: 20,
} as const;
