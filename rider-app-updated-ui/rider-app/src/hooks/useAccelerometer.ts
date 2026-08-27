// ============================================================
// RideShield — useAccelerometer Hook
// ============================================================

import { useState, useEffect, useRef, useCallback } from 'react';
import { Platform } from 'react-native';
import { Accelerometer } from 'expo-sensors';
import type { AccelerometerData } from '../types/telemetry';
import { Config } from '../constants/config';

interface UseAccelerometerOptions {
  onSample?: (data: AccelerometerData) => void;
}

interface UseAccelerometerResult {
  data: AccelerometerData | null;
  isSimulated: boolean;
  startTracking: () => void;
  stopTracking: () => void;
}

const G = 9.81; // m/s²
// High frequency polling for crash detection
const SENSOR_POLL_MS = 20;

function calcMagnitude(x: number, y: number, z: number): number {
  return Math.sqrt(x * x + y * y + z * z);
}

function generateSimulated(index: number): AccelerometerData {
  const t = index * 0.1;
  const x = 0.1 + Math.sin(t) * 0.3;
  const y = 9.5 + Math.cos(t * 0.5) * 0.5;  // gravity on Y-axis typically
  const z = 0.05 + Math.sin(t * 2) * 0.15;
  const magnitude = calcMagnitude(x, y, z);
  return { x, y, z, magnitude, gForce: magnitude / G, timestamp: Date.now() };
}

export function useAccelerometer(options?: UseAccelerometerOptions): UseAccelerometerResult {
  const [data, setData] = useState<AccelerometerData | null>(null);
  const [isSimulated, setIsSimulated] = useState(false);

  const subscriptionRef = useRef<{ remove: () => void } | null>(null);
  const simulatedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const simIndexRef = useRef(0);
  const lastStateUpdateRef = useRef<number>(0);

  const handleSample = useCallback((data: AccelerometerData) => {
    // 1. Immediately pass to high-frequency crash detector callback if provided
    options?.onSample?.(data);

    // 2. Throttle React state updates to avoid UI lag
    const now = Date.now();
    if (now - lastStateUpdateRef.current >= Config.TELEMETRY_SENSOR_INTERVAL_MS) {
      lastStateUpdateRef.current = now;
      setData(data);
    }
  }, [options?.onSample]);

  const startSimulated = useCallback(() => {
    setIsSimulated(true);
    simulatedIntervalRef.current = setInterval(() => {
      handleSample(generateSimulated(simIndexRef.current++));
    }, SENSOR_POLL_MS);
  }, [handleSample]);

  const stopSimulated = useCallback(() => {
    if (simulatedIntervalRef.current) {
      clearInterval(simulatedIntervalRef.current);
      simulatedIntervalRef.current = null;
    }
  }, []);

  const startTracking = useCallback(() => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const handleDeviceMotion = (event: any) => {
        const x = event.accelerationIncludingGravity?.x ?? 0;
        const y = event.accelerationIncludingGravity?.y ?? G;
        const z = event.accelerationIncludingGravity?.z ?? 0;
        const magnitude = calcMagnitude(x, y, z);
        handleSample({ x, y, z, magnitude, gForce: magnitude / G, timestamp: Date.now() });
      };

      window.addEventListener('devicemotion', handleDeviceMotion);
      subscriptionRef.current = {
        remove: () => window.removeEventListener('devicemotion', handleDeviceMotion)
      };
      setIsSimulated(false);
      return;
    }

    try {
      Accelerometer.setUpdateInterval(SENSOR_POLL_MS);
      subscriptionRef.current = Accelerometer.addListener((raw) => {
        // expo-sensors Accelerometer gives values in G units (not m/s²) on native.
        // Multiply by G to get m/s², then divide back for gForce for clarity.
        const { x, y, z } = raw;
        const gForce = calcMagnitude(x, y, z);    // expo gives G directly on native
        const magnitude = gForce * G;              // convert to m/s² for storage
        handleSample({ x, y, z, magnitude, gForce, timestamp: Date.now() });
      });
      setIsSimulated(false);
    } catch (err) {
      console.warn('[useAccelerometer] Not available, using simulated data.', err);
      startSimulated();
    }
  }, [startSimulated, handleSample]);

  const stopTracking = useCallback(() => {
    subscriptionRef.current?.remove();
    subscriptionRef.current = null;
    stopSimulated();
    setData(null);
  }, [stopSimulated]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      subscriptionRef.current?.remove();
      stopSimulated();
    };
  }, [stopSimulated]);

  return { data, isSimulated, startTracking, stopTracking };
}
