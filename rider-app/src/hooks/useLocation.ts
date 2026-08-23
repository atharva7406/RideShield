// ============================================================
// RideShield — useLocation Hook
// ============================================================

import { useState, useEffect, useRef, useCallback } from 'react';
import * as Location from 'expo-location';
import type { LocationData } from '../types/telemetry';
import { Config } from '../constants/config';

interface UseLocationResult {
  location: LocationData | null;
  hasPermission: boolean;
  isLoading: boolean;
  error: string | null;
  isSimulated: boolean;
  startTracking: () => Promise<void>;
  stopTracking: () => void;
}

// Simulated location: Delhi area, slow drift
const BASE_LAT = 28.6139;
const BASE_LNG = 77.209;

function generateSimulatedLocation(index: number): LocationData {
  const t = index * 0.01;
  return {
    latitude: BASE_LAT + Math.sin(t) * 0.002,
    longitude: BASE_LNG + Math.cos(t) * 0.002,
    speed: 8 + Math.sin(t * 3) * 4,          // ~8-12 m/s
    speedKmh: (8 + Math.sin(t * 3) * 4) * 3.6,
    heading: (t * 30) % 360,
    accuracy: 5,
    altitude: 220 + Math.sin(t) * 2,
    timestamp: Date.now(),
  };
}

export function useLocation(): UseLocationResult {
  const [location, setLocation] = useState<LocationData | null>(null);
  const [hasPermission, setHasPermission] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSimulated, setIsSimulated] = useState(false);

  const subscriptionRef = useRef<Location.LocationSubscription | null>(null);
  const simulatedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const simIndexRef = useRef(0);
  const isActiveRef = useRef(false);

  const startSimulated = useCallback(() => {
    setIsSimulated(true);
    simulatedIntervalRef.current = setInterval(() => {
      setLocation(generateSimulatedLocation(simIndexRef.current++));
    }, Config.TELEMETRY_SENSOR_INTERVAL_MS);
  }, []);

  const stopSimulated = useCallback(() => {
    if (simulatedIntervalRef.current) {
      clearInterval(simulatedIntervalRef.current);
      simulatedIntervalRef.current = null;
    }
  }, []);

  const startTracking = useCallback(async () => {
    if (isActiveRef.current) return;
    isActiveRef.current = true;
    setIsLoading(true);
    setError(null);

    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setHasPermission(false);
        setError('Location permission denied. Using simulated data.');
        startSimulated();
        setIsLoading(false);
        return;
      }
      setHasPermission(true);

      subscriptionRef.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.BestForNavigation,
          timeInterval: Config.TELEMETRY_SENSOR_INTERVAL_MS,
          distanceInterval: 1,
        },
        (pos) => {
          setLocation({
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            speed: pos.coords.speed,
            speedKmh: pos.coords.speed != null ? pos.coords.speed * 3.6 : null,
            heading: pos.coords.heading,
            accuracy: pos.coords.accuracy,
            altitude: pos.coords.altitude,
            timestamp: pos.timestamp,
          });
        }
      );
      setIsSimulated(false);
    } catch (err: any) {
      console.warn('[useLocation] Error, falling back to simulated:', err.message);
      setError('GPS unavailable. Using simulated data.');
      startSimulated();
    } finally {
      setIsLoading(false);
    }
  }, [startSimulated]);

  const stopTracking = useCallback(() => {
    isActiveRef.current = false;
    try {
      subscriptionRef.current?.remove();
    } catch (e) {
      console.warn('[useLocation] Failed to remove subscription (safe fallback):', e);
    }
    subscriptionRef.current = null;
    stopSimulated();
    setLocation(null);
  }, [stopSimulated]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      try {
        subscriptionRef.current?.remove();
      } catch (e) {
        console.warn('[useLocation] Failed to remove subscription during cleanup:', e);
      }
      stopSimulated();
    };
  }, [stopSimulated]);

  return {
    location,
    hasPermission,
    isLoading,
    error,
    isSimulated,
    startTracking,
    stopTracking,
  };
}
