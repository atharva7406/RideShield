// ============================================================
// RideShield — useTelemetry Unified Hook
// ============================================================
// Combines location, accelerometer, and gyroscope into one object.
// Also handles telemetry emission to backend via Socket.IO.

import { useMemo, useRef, useEffect, useCallback } from 'react';
import { useLocation } from './useLocation';
import { useAccelerometer } from './useAccelerometer';
import { useGyroscope } from './useGyroscope';
import { socketService } from '../services/socket';
import type { TelemetryData, TelemetryConnectionStatus } from '../types/telemetry';
import { Config } from '../constants/config';

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
  const locationHook = useLocation();
  const accelHook = useAccelerometer();
  const gyroHook = useGyroscope();

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
    backend: socketService.getIsConnected() ? 'connected' : 'disconnected',
  }), [locationHook.location, locationHook.isLoading, accelHook.data]);

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
  useEffect(() => {
    if (!isActive || !emitToBackend || !shiftId) {
      if (emitIntervalRef.current) {
        clearInterval(emitIntervalRef.current);
        emitIntervalRef.current = null;
      }
      return;
    }

    emitIntervalRef.current = setInterval(() => {
      const loc = locationHook.location;
      const acc = accelHook.data;
      const gyro = gyroHook.data;
      if (!loc || !acc || !gyro) return;

      socketService.emitTelemetry({
        shiftId,
        timestamp: Date.now(),
        latitude: loc.latitude,
        longitude: loc.longitude,
        speed: loc.speedKmh ?? 0,
        heading: loc.heading,
        acceleration: { x: acc.x, y: acc.y, z: acc.z, magnitude: acc.magnitude },
        gyroscope: { x: gyro.x, y: gyro.y, z: gyro.z, magnitude: gyro.magnitude },
      });
    }, Config.TELEMETRY_EMIT_INTERVAL_MS);

    return () => {
      if (emitIntervalRef.current) {
        clearInterval(emitIntervalRef.current);
        emitIntervalRef.current = null;
      }
    };
  }, [isActive, emitToBackend, shiftId, locationHook.location, accelHook.data, gyroHook.data]);

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
  }, [locationHook.stopTracking, accelHook.stopTracking, gyroHook.stopTracking]);

  const isSimulated =
    locationHook.isSimulated || accelHook.isSimulated || gyroHook.isSimulated;

  return { telemetry, isSimulated, startTracking, stopTracking };
}
