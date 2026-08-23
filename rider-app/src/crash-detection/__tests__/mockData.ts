import type { AccelSample, GyroSample, GPSSample } from '../types';

const GRAVITY_G = 1; // resting baseline in "g" units

function noise(amplitude: number): number {
  return (Math.random() - 0.5) * 2 * amplitude;
}

function buildAccelSeries(
  durationMs: number,
  intervalMs: number,
  magnitudeFn: (tMs: number) => number
): AccelSample[] {
  const samples: AccelSample[] = [];
  for (let t = 0; t <= durationMs; t += intervalMs) {
    const magnitude = Math.max(0, magnitudeFn(t));
    // In test data, magnitude is already in G-units (matching expo-sensors native output).
    const gForce = magnitude;
    // x/y/z split is illustrative only — detection logic runs on magnitude
    samples.push({ x: magnitude * 0.4, y: magnitude * 0.4, z: magnitude * 0.82, magnitude, gForce, timestamp: t });
  }
  return samples;
}

function buildGyroSeries(
  durationMs: number,
  intervalMs: number,
  magnitudeFn: (tMs: number) => number
): GyroSample[] {
  const samples: GyroSample[] = [];
  for (let t = 0; t <= durationMs; t += intervalMs) {
    const magnitude = Math.max(0, magnitudeFn(t));
    samples.push({ x: magnitude * 0.5, y: magnitude * 0.5, z: magnitude * 0.5, magnitude, timestamp: t });
  }
  return samples;
}

function buildGPSSeries(
  durationMs: number,
  intervalMs: number,
  speedFn: (tMs: number) => number
): GPSSample[] {
  const samples: GPSSample[] = [];
  for (let t = 0; t <= durationMs; t += intervalMs) {
    samples.push({
      speed: Math.max(0, speedFn(t)),
      latitude: 19.076 + t * 0.000001,
      longitude: 72.8777 + t * 0.000001,
      timestamp: t,
    });
  }
  return samples;
}

export interface MockScenario {
  name: string;
  accel: AccelSample[];
  gyro: GyroSample[];
  gps: GPSSample[];
}

/** 1. Normal riding: steady baseline, small noise, constant speed. */
export function normalRiding(): MockScenario {
  return {
    name: 'normal riding',
    accel: buildAccelSeries(5000, 20, () => GRAVITY_G + noise(0.05)),
    gyro: buildGyroSeries(5000, 20, () => 0.1 + noise(0.05)),
    gps: buildGPSSeries(5000, 200, () => 8 + noise(0.3)),
  };
}

/** 2. Hard braking: firm but sub-crash accel spike, real gradual speed loss. */
export function hardBraking(): MockScenario {
  return {
    name: 'hard braking',
    accel: buildAccelSeries(5000, 20, (t) =>
      t >= 2000 && t <= 2600 ? 1.8 + noise(0.1) : GRAVITY_G + noise(0.05)
    ),
    gyro: buildGyroSeries(5000, 20, () => 0.2 + noise(0.1)),
    gps: buildGPSSeries(5000, 200, (t) => {
      if (t < 2000) return 14;
      if (t < 3500) return 14 - ((t - 2000) / 1500) * 10; // 14 -> 4 m/s, gradual
      return 4;
    }),
  };
}

/** 3. Speed bump: sharp but very brief spike, no meaningful speed change. */
export function speedBump(): MockScenario {
  return {
    name: 'speed bump',
    accel: buildAccelSeries(5000, 20, (t) =>
      t >= 2400 && t <= 2480 ? 2.0 + noise(0.1) : GRAVITY_G + noise(0.05)
    ),
    gyro: buildGyroSeries(5000, 20, () => 0.15 + noise(0.1)),
    gps: buildGPSSeries(5000, 200, () => 9 + noise(0.3)),
  };
}

/** 4. Phone shake: noisy accel + gyro, no sustained peak, no ride context. */
export function phoneShake(): MockScenario {
  return {
    name: 'phone shake',
    accel: buildAccelSeries(5000, 20, () => GRAVITY_G + noise(0.6)),
    gyro: buildGyroSeries(5000, 20, () => noise(1.5)),
    gps: [],
  };
}

/** 5. Phone drop: one large accel spike, minimal rotation, no GPS context. */
export function phoneDrop(): MockScenario {
  return {
    name: 'phone drop',
    accel: buildAccelSeries(3000, 20, (t) => {
      if (t >= 1200 && t <= 1240) return 3.2 + noise(0.2); // impact with ground
      if (t > 1240) return GRAVITY_G + noise(0.02); // lying still afterwards
      return GRAVITY_G + noise(0.05);
    }),
    gyro: buildGyroSeries(3000, 20, () => 0.1 + noise(0.1)), // mostly linear fall
    gps: [],
  };
}

/** 6. Simulated crash: big accel spike + gyro tumble + abrupt speed loss + stillness. */
export function simulatedCrash(): MockScenario {
  return {
    name: 'simulated crash',
    accel: buildAccelSeries(5000, 20, (t) => {
      if (t >= 2500 && t <= 2560) return 4.5 + noise(0.3); // impact
      if (t > 2560) return GRAVITY_G + noise(0.03); // still afterwards
      return GRAVITY_G + noise(0.05);
    }),
    gyro: buildGyroSeries(5000, 20, (t) =>
      t >= 2500 && t <= 2700 ? 6 + noise(1) : 0.15 + noise(0.1)
    ),
    gps: buildGPSSeries(5000, 200, (t) => {
      if (t < 2500) return 12;
      if (t < 2900) return 12 - ((t - 2500) / 400) * 12; // 12 -> 0, abrupt
      return 0;
    }),
  };
}

export const ALL_SCENARIOS = [
  normalRiding,
  hardBraking,
  speedBump,
  phoneShake,
  phoneDrop,
  simulatedCrash,
];
