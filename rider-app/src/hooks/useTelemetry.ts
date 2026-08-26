// ============================================================
// RideShield — useTelemetry Unified Hook
// ============================================================
// Combines location, accelerometer, and gyroscope into one object.
// Also handles telemetry emission to backend via Socket.IO.

import { useMemo, useRef, useEffect, useCallback, useState } from 'react';
import { useLocation } from './useLocation';
import { useAccelerometer } from './useAccelerometer';
import { useGyroscope } from './useGyroscope';
import { socketService } from '../services/socket';
import { apiClient } from '../services/api';
import type { TelemetryData, TelemetryConnectionStatus } from '../types/telemetry';
import { Config } from '../constants/config';
import { CrashDetector, captureIncidentWindow } from '../crash-detection';
import type { CrashResult } from '../crash-detection';
import { CRASH_DETECTION_CONFIG } from '../crash-detection/config';
import { reportIncident, initIncidentSync } from '../services/incidentSync';
import { generateUUID } from '../utils/uuid';

interface UseTelemetryOptions {
  shiftId: string | null;
  isActive: boolean;
  emitToBackend?: boolean;
}

interface UseTelemetryResult {
  telemetry: TelemetryData;
  isSimulated: boolean;
  startTracking: () => Promise<void>;
  stopTracking: () => void;
  /** SIH-demo trigger: seeds the real CrashDetector buffer with a
   * realistic spike and runs it through the exact same evaluate() ->
   * L1 -> PRE/IMPACT/POST capture -> queue/upload path as a genuine
   * Tier-0 event — not a separate fake pipeline. */
  simulateCrash: () => void;
}

export function useTelemetry({
  shiftId,
  isActive,
  emitToBackend = true,
}: UseTelemetryOptions): UseTelemetryResult {
  // -------------------------------------------------------------------------
  // Local Crash Detection state
  // -------------------------------------------------------------------------
  const crashDetectorRef = useRef(new CrashDetector());
  const crashEvalIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastCrashTriggerRef = useRef<number>(0);

  const onSampleLocation = useCallback((loc: any) => {
    // Add speed to the GPS buffer for speed drop calculation
    crashDetectorRef.current.pushGPS({
      latitude: loc.latitude,
      longitude: loc.longitude,
      speed: loc.speedKmh ?? 0,
      timestamp: Date.now(),
    });
  }, []);

  const locationHook = useLocation({
    onSample: onSampleLocation
  });

  const onSampleAccel = useCallback((acc: any) => {
    crashDetectorRef.current.pushAccel(acc);
  }, []);

  const accelHook = useAccelerometer({
    onSample: onSampleAccel
  });

  const onSampleGyro = useCallback((gyr: any) => {
    crashDetectorRef.current.pushGyro(gyr);
  }, []);

  const gyroHook = useGyroscope({
    onSample: onSampleGyro
  });

  const emitIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Start listening for connectivity restoration and flush anything left
  // over from a previous offline session (e.g. app was killed before it
  // could sync). Idempotent — safe if useTelemetry mounts more than once.
  useEffect(() => {
    initIncidentSync();
  }, []);

  // -------------------------------------------------------------------------
  // Compose connection status
  // -------------------------------------------------------------------------
  const connectionStatus: TelemetryConnectionStatus = useMemo(() => ({
    gps: locationHook.location
      ? 'connected'
      : locationHook.isLoading
      ? 'connecting'
      : 'disconnected',
    motion: accelHook.data ? 'connected' : 'connecting',
    backend: 'connected',
  }), [locationHook.location, locationHook.isLoading, accelHook.data]);

  // Maintain a local batch sequence
  const batchSequenceRef = useRef<number>(0);

  // -------------------------------------------------------------------------
  // Compose unified telemetry object
  // -------------------------------------------------------------------------
  const telemetry: TelemetryData = useMemo(() => ({
    location: locationHook.location,
    speed: locationHook.location?.speedKmh ?? 0,
    acceleration: accelHook.data,
    gForce: accelHook.data?.gForce ?? 1.0, // 1.0 G at rest
    gyroscope: gyroHook.data,
    timestamp: Date.now(),
    connectionStatus,
    isSimulated: locationHook.isSimulated || accelHook.isSimulated || gyroHook.isSimulated,
  }), [
    locationHook.location,
    locationHook.isSimulated,
    accelHook.data,
    accelHook.isSimulated,
    gyroHook.data,
    gyroHook.isSimulated,
    connectionStatus,
  ]);

  // -------------------------------------------------------------------------
  // Emit telemetry to backend at throttled interval
  // -------------------------------------------------------------------------
  
  // Use refs to hold the latest sensor data so setInterval doesn't thrash
  const latestDataRef = useRef({
    location: locationHook.location,
    accel: accelHook.data,
    gyro: gyroHook.data,
  });

  useEffect(() => {
    latestDataRef.current = {
      location: locationHook.location,
      accel: accelHook.data,
      gyro: gyroHook.data,
    };
  }, [locationHook.location, accelHook.data, gyroHook.data]);

  // ---------------------------------------------------------------------
  // Shared crash-trigger handler — used by BOTH the real 5Hz eval loop
  // below AND simulateCrash() (the SIH-demo button), so a demo trigger
  // exercises the exact same L1 -> PRE/IMPACT/POST capture -> queue/
  // upload path as a genuine Tier-0 detection, not a separate mock flow.
  // ---------------------------------------------------------------------
  const handleCrashTrigger = useCallback((result: CrashResult) => {
    const now = Date.now();
    if (now - lastCrashTriggerRef.current <= CRASH_DETECTION_CONFIG.CRASH_COOLDOWN_MS) {
      return; // still in cooldown from a previous trigger
    }
    lastCrashTriggerRef.current = now;

    console.log('[CrashDetector] Valid crash detected! Triggering incident.');

    // Minted the instant Tier 0 fires and carried unchanged through local
    // storage -> upload attempt -> offline queue -> retry -> backend, so
    // the same physical incident always maps to one Incident row no
    // matter how many times/how late it syncs.
    const clientIncidentId = generateUUID();
    // Anchor PRE/IMPACT/POST capture on the actual peak-G instant, not
    // "now" — the 5Hz eval loop can lag the real impact by up to 200ms.
    const triggerTimestamp = result.features.accelPeakTimestamp ?? now;

    const loc = latestDataRef.current.location;
    const crashPayload = {
      shift_id: shiftId,
      peak_g_force: result.features.accelPeakG,
      confidence_score: result.confidence,
      latitude: loc?.latitude ?? 0,
      longitude: loc?.longitude ?? 0,
    };

    // Trigger local UI immediately — must not wait on a network
    // round-trip, AsyncStorage, or the post-event capture wait below, so
    // this still uses the client-computed summary, not the backend's
    // re-scored result. This is the safety action; nothing below this
    // line is allowed to block or delay it.
    socketService.triggerMockCrash(crashPayload as any);

    // PRE/IMPACT/POST evidence capture — waits POST_EVENT_CAPTURE_MS
    // purely to collect post-impact evidence; L1 has already fired above
    // and is entirely unaffected by this wait. Once finalized, the window
    // (never a summary) is queued and uploaded exactly as before — see
    // services/incidentSync.ts.
    captureIncidentWindow({
      detector: crashDetectorRef.current,
      triggerTimestamp,
      clientIncidentId,
    }).then((finalized) => {
      reportIncident({
        clientIncidentId,
        shiftId: shiftId!,
        riderId: null,
        createdAt: triggerTimestamp,
        tier0: {
          confidence: result.confidence,
          peakGForce: result.features.accelPeakG,
        },
        evidence: {
          accelSamples: finalized.accelSamples.map(s => ({ timestamp: s.timestamp, x: s.x, y: s.y, z: s.z })),
          gyroSamples: finalized.gyroSamples.map(s => ({ timestamp: s.timestamp, x: s.x, y: s.y, z: s.z })),
          gpsSamples: finalized.gpsSamples.map(s => ({
            timestamp: s.timestamp, latitude: s.latitude, longitude: s.longitude, speed: s.speed,
          })),
        },
        windowMetadata: finalized.metadata,
      }).catch((err) => {
        console.error('Failed to enqueue crash window for sync:', err);
      });
    });
  }, [shiftId]);

  const simulateCrash = useCallback(() => {
    const now = Date.now();
    const G = 9.81;
    // Seed ~200ms of realistic baseline riding motion...
    for (let i = 10; i >= 1; i--) {
      const t = now - i * 20;
      crashDetectorRef.current.pushAccel({ x: 0.1, y: 0.2, z: 9.75, magnitude: G, gForce: 1.0, timestamp: t });
      crashDetectorRef.current.pushGyro({ x: 1, y: 1, z: 1, magnitude: 1.7, timestamp: t });
    }
    // ...then a spike well past both thresholds (accel AND gyro, so the
    // detector's corroboration rule is satisfied same as a real crash),
    // pushed into the SAME buffer real sensor data flows through.
    const spikeG = CRASH_DETECTION_CONFIG.ACCEL_PEAK_THRESHOLD_G * CRASH_DETECTION_CONFIG.ACCEL_PEAK_TO_BASELINE_RATIO_THRESHOLD;
    crashDetectorRef.current.pushAccel({
      x: spikeG * 0.6, y: spikeG * 0.3, z: spikeG * 0.2, magnitude: spikeG * G, gForce: spikeG, timestamp: now,
    });
    crashDetectorRef.current.pushGyro({
      x: CRASH_DETECTION_CONFIG.GYRO_MAGNITUDE_THRESHOLD + 50, y: 10, z: 10,
      magnitude: CRASH_DETECTION_CONFIG.GYRO_MAGNITUDE_THRESHOLD + 50, timestamp: now,
    });

    // Real evaluate() call — this is the actual detector, not a fake result.
    const result = crashDetectorRef.current.evaluate();
    if (result.isCrashCandidate) {
      handleCrashTrigger(result);
    } else {
      console.warn('[useTelemetry] simulateCrash seed did not pass detector thresholds — check CRASH_DETECTION_CONFIG');
    }
  }, [handleCrashTrigger]);

  useEffect(() => {
    if (!isActive || !emitToBackend || !shiftId) {
      if (emitIntervalRef.current) {
        clearInterval(emitIntervalRef.current);
        emitIntervalRef.current = null;
      }
      if (crashEvalIntervalRef.current) {
        clearInterval(crashEvalIntervalRef.current);
        crashEvalIntervalRef.current = null;
      }
      return;
    }

    // 1. Telemetry Loop (1 Hz)
    emitIntervalRef.current = setInterval(() => {
      const loc = latestDataRef.current.location;
      const acc = latestDataRef.current.accel;
      const gyro = latestDataRef.current.gyro;
      if (!loc || !acc || !gyro) return;

      const sample = {
        timestamp: Date.now() / 1000.0,
        latitude: loc.latitude,
        longitude: loc.longitude,
        speed: loc.speedKmh ?? 0,
        accel_x: acc.x,
        accel_y: acc.y,
        accel_z: acc.z,
        gyro_x: gyro.x,
        gyro_y: gyro.y,
        gyro_z: gyro.z,
      };

      batchSequenceRef.current += 1;

      apiClient.post('/telemetry/batch', {
        shift_id: shiftId,
        batch_sequence: batchSequenceRef.current,
        samples: [sample],
      }).catch((err) => {
        console.warn('Failed to send HTTP telemetry batch:', err);
      });
    }, Config.TELEMETRY_EMIT_INTERVAL_MS);

    // 2. Crash Detection Evaluation Loop (5 Hz)
    crashEvalIntervalRef.current = setInterval(() => {
      const result = crashDetectorRef.current.evaluate();
      if (result.isCrashCandidate) {
        handleCrashTrigger(result);
      }
    }, 200);

    return () => {
      if (emitIntervalRef.current) {
        clearInterval(emitIntervalRef.current);
        emitIntervalRef.current = null;
      }
      if (crashEvalIntervalRef.current) {
        clearInterval(crashEvalIntervalRef.current);
        crashEvalIntervalRef.current = null;
      }
    };
  }, [isActive, emitToBackend, shiftId, handleCrashTrigger]);

  // -------------------------------------------------------------------------
  // Start / Stop
  // -------------------------------------------------------------------------
  const startTracking = useCallback(async () => {
    await locationHook.startTracking();
    accelHook.startTracking();
    gyroHook.startTracking();
  }, [locationHook.startTracking, accelHook.startTracking, gyroHook.startTracking]);

  const stopTracking = useCallback(() => {
    locationHook.stopTracking();
    accelHook.stopTracking();
    gyroHook.stopTracking();
    if (emitIntervalRef.current) {
      clearInterval(emitIntervalRef.current);
      emitIntervalRef.current = null;
    }
    if (crashEvalIntervalRef.current) {
      clearInterval(crashEvalIntervalRef.current);
      crashEvalIntervalRef.current = null;
    }
    crashDetectorRef.current.clear();
  }, [locationHook.stopTracking, accelHook.stopTracking, gyroHook.stopTracking]);

  const isSimulated =
    locationHook.isSimulated || accelHook.isSimulated || gyroHook.isSimulated;

  return { telemetry, isSimulated, startTracking, stopTracking, simulateCrash };
}
