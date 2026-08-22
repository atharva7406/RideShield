import { CrashDetector } from '../crashDetector';
import {
  normalRiding,
  hardBraking,
  speedBump,
  phoneShake,
  phoneDrop,
  simulatedCrash,
  MockScenario,
} from './mockData';

function evaluateScenario(scenario: MockScenario) {
  const detector = new CrashDetector();
  scenario.accel.forEach((s) => detector.pushAccel(s));
  scenario.gyro.forEach((s) => detector.pushGyro(s));
  scenario.gps.forEach((s) => detector.pushGPS(s));
  return detector.evaluate();
}

describe('CrashDetector — prototype scenarios', () => {
  it('does not flag normal riding', () => {
    expect(evaluateScenario(normalRiding()).isCrashCandidate).toBe(false);
  });

  it('does not flag hard braking as a crash', () => {
    expect(evaluateScenario(hardBraking()).isCrashCandidate).toBe(false);
  });

  it('does not flag a speed bump as a crash', () => {
    expect(evaluateScenario(speedBump()).isCrashCandidate).toBe(false);
  });

  it('does not flag phone shaking as a crash', () => {
    expect(evaluateScenario(phoneShake()).isCrashCandidate).toBe(false);
  });

  it('does not flag a dropped phone as a crash', () => {
    expect(evaluateScenario(phoneDrop()).isCrashCandidate).toBe(false);
  });

  it('flags a simulated crash with high confidence', () => {
    const result = evaluateScenario(simulatedCrash());
    expect(result.isCrashCandidate).toBe(true);
    expect(result.confidence).toBeGreaterThanOrEqual(0.55);
    expect(result.signals.accelAnomaly).toBe(true);
  });

  it('clear() resets buffers so a stale evaluate() looks empty', () => {
    const detector = new CrashDetector();
    simulatedCrash().accel.forEach((s) => detector.pushAccel(s));
    detector.clear();
    const result = detector.evaluate();
    expect(result.isCrashCandidate).toBe(false);
    expect(result.features.accelPeak).toBe(0);
  });
});
