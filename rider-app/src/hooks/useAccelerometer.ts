// ============================================================
// RideShield — useAccelerometer Hook
// ============================================================

import { useState, useEffect, useRef, useCallback } from 'react';
import { Accelerometer } from 'expo-sensors';
import type { AccelerometerData } from '../types/telemetry';
import { Config } from '../constants/config';

interface UseAccelerometerResult {
  data: AccelerometerData | null;
  isSimulated: boolean;
  startTracking: () => void;
  stopTracking: () => void;
}

const G = 9.81; // m/s²

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

export function useAccelerometer(): UseAccelerometerResult {
  const [data, setData] = useState<AccelerometerData | null>(null);
  const [isSimulated, setIsSimulated] = useState(false);

  const subscriptionRef = useRef<{ remove: () => void } | null>(null);
  const simulatedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const simIndexRef = useRef(0);

  const startSimulated = useCallback(() => {
    setIsSimulated(true);
    simulatedIntervalRef.current = setInterval(() => {
      setData(generateSimulated(simIndexRef.current++));
    }, Config.TELEMETRY_SENSOR_INTERVAL_MS);
  }, []);

  const stopSimulated = useCallback(() => {
    if (simulatedIntervalRef.current) {
      clearInterval(simulatedIntervalRef.current);
      simulatedIntervalRef.current = null;
    }
  }, []);

  const startTracking = useCallback(() => {
    try {
      Accelerometer.setUpdateInterval(Config.TELEMETRY_SENSOR_INTERVAL_MS);
      subscriptionRef.current = Accelerometer.addListener((raw) => {
        const { x, y, z } = raw;
        const magnitude = calcMagnitude(x, y, z);
        setData({ x, y, z, magnitude, gForce: magnitude / G, timestamp: Date.now() });
      });
      setIsSimulated(false);
    } catch (err) {
      console.warn('[useAccelerometer] Not available, using simulated data.');
      startSimulated();
    }
  }, [startSimulated]);

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
