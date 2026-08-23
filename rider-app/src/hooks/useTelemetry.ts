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
import { CrashDetector } from '../crash-detection';
import { CRASH_DETECTION_CONFIG } from '../crash-detection/config';

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

  const locationHook = useLocation({
    onSample: (loc) => {
      // Add speed to the GPS buffer for speed drop calculation
      crashDetectorRef.current.pushGPS({
        latitude: loc.latitude,
        longitude: loc.longitude,
        speed: loc.speedKmh ?? 0,
        timestamp: Date.now(),
      });
    }
  });

  const accelHook = useAccelerometer({
    onSample: (acc) => crashDetectorRef.current.pushAccel(acc)
  });

  const gyroHook = useGyroscope({
    onSample: (gyr) => crashDetectorRef.current.pushGyro(gyr)
  });

  const emitIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
        const now = Date.now();
        if (now - lastCrashTriggerRef.current > CRASH_DETECTION_CONFIG.CRASH_COOLDOWN_MS) {
          lastCrashTriggerRef.current = now;
          
          console.log('[CrashDetector] Valid crash detected! Triggering incident.');
          
          const loc = latestDataRef.current.location;
          
          const crashPayload = {
            shift_id: shiftId,
            peak_g_force: result.features.accelPeakG,
            confidence_score: result.confidence,
            latitude: loc?.latitude ?? 0,
            longitude: loc?.longitude ?? 0
          };

          // Trigger local UI immediately
          socketService.triggerMockCrash(crashPayload as any);

          // Report to backend
          apiClient.post('/incidents', crashPayload).catch((err) => {
            console.error('Failed to report incident to backend:', err);
          });
        }
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
  }, [isActive, emitToBackend, shiftId]);

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

  return { telemetry, isSimulated, startTracking, stopTracking };
}
