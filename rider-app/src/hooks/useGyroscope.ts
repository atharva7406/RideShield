// ============================================================
// RideShield — useGyroscope Hook
// ============================================================

import { useState, useEffect, useRef, useCallback } from 'react';
import { Platform } from 'react-native';
import { Gyroscope } from 'expo-sensors';
import type { GyroscopeData } from '../types/telemetry';
import { Config } from '../constants/config';

interface UseGyroscopeResult {
  data: GyroscopeData | null;
  isSimulated: boolean;
  startTracking: () => void;
  stopTracking: () => void;
}

// Gyroscope gives rad/s; multiply by (180/π) for deg/s
const RAD_TO_DEG = 180 / Math.PI;

function calcMagnitude(x: number, y: number, z: number): number {
  return Math.sqrt(x * x + y * y + z * z);
}

function generateSimulated(index: number): GyroscopeData {
  const t = index * 0.1;
  const x = Math.sin(t * 0.7) * 0.3;
  const y = Math.cos(t * 1.1) * 0.2;
  const z = Math.sin(t * 1.5) * 0.15;
  const magnitude = calcMagnitude(x, y, z) * RAD_TO_DEG;
  return {
    x: x * RAD_TO_DEG,
    y: y * RAD_TO_DEG,
    z: z * RAD_TO_DEG,
    magnitude,
    timestamp: Date.now(),
  };
}

export function useGyroscope(): UseGyroscopeResult {
  const [data, setData] = useState<GyroscopeData | null>(null);
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
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const handleDeviceMotion = (event: any) => {
        const rr = event.rotationRate;
        // rotationRate is in deg/s directly in HTML5 API
        const x = rr?.alpha ?? 0;
        const y = rr?.beta ?? 0;
        const z = rr?.gamma ?? 0;
        setData({
          x,
          y,
          z,
          magnitude: calcMagnitude(x, y, z),
          timestamp: Date.now(),
        });
      };

      window.addEventListener('devicemotion', handleDeviceMotion);
      subscriptionRef.current = {
        remove: () => window.removeEventListener('devicemotion', handleDeviceMotion)
      };
      setIsSimulated(false);
      return;
    }

    try {
      Gyroscope.setUpdateInterval(Config.TELEMETRY_SENSOR_INTERVAL_MS);
      subscriptionRef.current = Gyroscope.addListener((raw) => {
        const { x, y, z } = raw;
        const xDeg = x * RAD_TO_DEG;
        const yDeg = y * RAD_TO_DEG;
        const zDeg = z * RAD_TO_DEG;
        setData({
          x: xDeg,
          y: yDeg,
          z: zDeg,
          magnitude: calcMagnitude(xDeg, yDeg, zDeg),
          timestamp: Date.now(),
        });
      });
      setIsSimulated(false);
    } catch (err) {
      console.warn('[useGyroscope] Not available, using simulated data.', err);
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
