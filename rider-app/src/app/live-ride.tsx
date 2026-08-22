// ============================================================
// RideShield — Live Ride Screen (Vibrant Style)
// ============================================================

import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Alert,
  Dimensions,
  Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import MapView, { Marker, Polyline, PROVIDER_DEFAULT } from 'react-native-maps';
import { Ionicons } from '@expo/vector-icons';
import { useRide } from '../store/rideStore';
import { useTelemetry } from '../hooks/useTelemetry';
import { socketService } from '../services/socket';
import { shiftService } from '../services/shiftService';
import { SOSButton } from '../components/SOSButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../constants/theme';
import type { CrashEvent } from '../types/claim';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// Format seconds to "h m s"
function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function LiveRideScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { state: rideState, setCrashEvent, setShiftSummary, clearShift, setActiveShift } = useRide();

  const shiftId = rideState.activeShift?.id ?? null;

  const [isEnding, setIsEnding] = useState(false);
  const [shiftSeconds, setShiftSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mapRef = useRef<MapView>(null);

  // Route trail
  const [routeCoords, setRouteCoords] = useState<{ latitude: number; longitude: number }[]>([]);

  // Telemetry
  const { telemetry, startTracking, stopTracking } = useTelemetry({
    shiftId,
    isActive: true,
    emitToBackend: true,
  });

  useEffect(() => {
    async function initShift() {
      if (!shiftId) {
        const active = await shiftService.getActiveShift();
        if (active) {
          setActiveShift(active);
          socketService.joinShift(active.id);
        }
      } else {
        socketService.joinShift(shiftId);
      }
    }

    startTracking();
    socketService.connect();
    initShift();

    timerRef.current = setInterval(() => {
      setShiftSeconds(s => s + 1);
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      stopTracking();
      socketService.disconnect();
    };
  }, [shiftId, startTracking, stopTracking, setActiveShift]);

  useEffect(() => {
    const unsub = socketService.onCrashDetected((event: CrashEvent) => {
      setCrashEvent(event);
      router.push('/crash-alert');
    });
    return unsub;
  }, [setCrashEvent, router]);

  useEffect(() => {
    if (telemetry.location) {
      const { latitude, longitude } = telemetry.location;
      setRouteCoords(prev => {
        const next = [...prev, { latitude, longitude }];
        return next.length > 200 ? next.slice(next.length - 200) : next;
      });
      mapRef.current?.animateCamera({ center: { latitude, longitude }, zoom: 16 }, { duration: 500 });
    }
  }, [telemetry.location]);

  const performEndShift = useCallback(async () => {
    setIsEnding(true);
    if (timerRef.current) clearInterval(timerRef.current);
    stopTracking();
    if (shiftId) socketService.leaveShift(shiftId);
    socketService.disconnect();
    try {
      const response = await shiftService.endShift(shiftId ?? 'unknown');
      setShiftSummary(response.summary);
    } catch (err) {
      console.warn('[live-ride] Failed to end shift:', err);
    }
    clearShift();
    router.replace('/shift-summary');
  }, [shiftId, stopTracking, setShiftSummary, clearShift, router]);

  const handleEndShift = useCallback(() => {
    if (Platform.OS === 'web') {
      const confirmed = window.confirm('Are you sure you want to end your shift? This will stop all tracking.');
      if (confirmed) {
        performEndShift();
      }
    } else {
      Alert.alert(
        'End Shift',
        'Are you sure you want to end your shift? This will stop all tracking.',
        [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'End Shift',
            style: 'destructive',
            onPress: performEndShift,
          },
        ]
      );
    }
  }, [performEndShift]);

  const location = telemetry.location;
  const speed = Math.round(telemetry.speed);
  const gForce = telemetry.gForce;
  const gyro = telemetry.gyroscope;

  const initialRegion = useMemo(() => ({
    latitude: location?.latitude ?? 28.6139,
    longitude: location?.longitude ?? 77.209,
    latitudeDelta: 0.01,
    longitudeDelta: 0.01,
  }), []);

  return (
    <View style={styles.container}>
      {/* Top Header */}
      <View style={[styles.topHeader, { paddingTop: insets.top + Spacing.sm }]}>
        <Pressable 
          onPress={() => {
            if (router.canGoBack()) {
              router.back();
            } else {
              router.replace('/(tabs)/home');
            }
          }} 
          style={styles.backButton}
        >
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>Active Protection</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Map Section */}
      <View style={styles.mapSection}>
        <MapView
          ref={mapRef}
          style={styles.map}
          provider={PROVIDER_DEFAULT}
          initialRegion={initialRegion}
          currentLocation={location}
          showsUserLocation={false}
          showsMyLocationButton={false}
          showsCompass={false}
          mapType="standard"
        >
          {routeCoords.length > 1 && (
            <Polyline coordinates={routeCoords} strokeColor={Colors.primary} strokeWidth={4} />
          )}
          {location && (
            <Marker coordinate={{ latitude: location.latitude, longitude: location.longitude }} anchor={{ x: 0.5, y: 0.5 }}>
              <View style={styles.riderMarker}>
                <View style={styles.riderMarkerInner} />
              </View>
            </Marker>
          )}
        </MapView>

        {/* Map Overlays */}
        <View style={styles.overlayTopLeft}>
          <View style={styles.liveBadge}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>LIVE SHIFT</Text>
          </View>
          <Text style={styles.timerText}>{formatDuration(shiftSeconds)}</Text>
          <View style={styles.trackingPill}>
            <Ionicons name="location" size={14} color={Colors.primary} />
            <Text style={styles.trackingText}>Tracking Active</Text>
          </View>
        </View>

        <View style={styles.overlayTopRight}>
          <SOSButton onPress={() => router.push('/sos')} size={56} />
        </View>
      </View>

      {/* Bottom Sheet Dashboard */}
      <View style={styles.bottomSheet}>
        <View style={styles.dragHandle} />
        
        <View style={styles.statsContainer}>
          {/* Left side: Speed */}
          <View style={styles.speedColumn}>
            <View style={styles.speedHeader}>
              <Text style={styles.statsLabel}>CURRENT SPEED</Text>
              <Ionicons name="speedometer-outline" size={20} color={Colors.textSecondary} />
            </View>
            <View style={styles.speedValueRow}>
              <Text style={styles.speedNumber}>{speed}</Text>
              <Text style={styles.speedUnit}>km/h</Text>
            </View>
          </View>

          {/* Right side: Telemetry Grid */}
          <View style={styles.telemetryGrid}>
            <View style={styles.telemetryCard}>
              <Text style={styles.statsLabel}>G-Force</Text>
              <View style={styles.telemetryValueRow}>
                <Ionicons name="analytics" size={16} color={Colors.success} />
                <Text style={styles.telemetryValue}>{gForce.toFixed(1)}</Text>
              </View>
            </View>
            
            <View style={styles.telemetryCard}>
              <Text style={styles.statsLabel}>Gyro</Text>
              <View style={styles.telemetryValueRow}>
                <Ionicons name="compass" size={16} color={Colors.warning} />
                <Text style={styles.telemetryValue}>{gyro ? gyro.magnitude.toFixed(0) : '--'}°</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Acceleration mock chart visual (blue bars) */}
        <View style={styles.mockChart}>
          {[1,2,3,4,2,5,3,6,8,5,3,4,2,3,1,2].map((val, i) => (
            <View key={i} style={[styles.bar, { height: val * 4 }]} />
          ))}
        </View>

        <Pressable style={styles.endShiftButton} onPress={handleEndShift} disabled={isEnding}>
          <Ionicons name="stop-circle" size={20} color={Colors.danger} />
          <Text style={styles.endShiftText}>{isEnding ? 'ENDING...' : 'End Shift'}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  // Top Header
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.sm,
    backgroundColor: Colors.background,
    zIndex: 10,
  },
  backButton: { padding: Spacing.xs },
  headerTitle: { ...Typography.h3, color: Colors.textPrimary },
  // Map
  mapSection: {
    flex: 1,
    position: 'relative',
  },
  map: {
    width: '100%',
    height: '100%',
  },
  riderMarker: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: Colors.primary,
  },
  riderMarkerInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.primary,
  },
  // Overlays
  overlayTopLeft: {
    position: 'absolute',
    top: Spacing.md,
    left: Spacing.md,
    gap: 6,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.successMuted,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    gap: 4,
    alignSelf: 'flex-start',
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.success,
  },
  liveText: {
    ...Typography.labelSM,
    color: Colors.success,
  },
  timerText: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    fontWeight: '600',
    marginLeft: 2,
  },
  trackingPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.card,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    gap: 4,
    ...Shadows.soft,
    marginTop: 4,
  },
  trackingText: {
    ...Typography.labelSM,
    color: Colors.textPrimary,
  },
  overlayTopRight: {
    position: 'absolute',
    top: Spacing.md,
    right: Spacing.md,
  },
  // Bottom Sheet
  bottomSheet: {
    backgroundColor: Colors.card,
    borderTopLeftRadius: BorderRadius.xl,
    borderTopRightRadius: BorderRadius.xl,
    padding: Spacing.lg,
    ...Shadows.medium,
    marginTop: -20, // Overlap map
  },
  dragHandle: {
    width: 40,
    height: 4,
    backgroundColor: Colors.border,
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: Spacing.lg,
  },
  statsContainer: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginBottom: Spacing.lg,
  },
  statsLabel: {
    ...Typography.labelSM,
    color: Colors.textMuted,
    letterSpacing: 0.5,
  },
  // Speed
  speedColumn: {
    flex: 1,
  },
  speedHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.xs,
  },
  speedValueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 4,
  },
  speedNumber: {
    fontSize: 56,
    fontWeight: '800',
    color: Colors.textPrimary,
    letterSpacing: -1.5,
    lineHeight: 60,
  },
  speedUnit: {
    ...Typography.bodyLG,
    color: Colors.textMuted,
    fontWeight: '600',
  },
  // Telemetry Cards
  telemetryGrid: {
    flex: 1,
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  telemetryCard: {
    flex: 1,
    backgroundColor: Colors.background,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  telemetryValueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
  },
  telemetryValue: {
    ...Typography.h4,
    color: Colors.textPrimary,
  },
  // Mock Chart
  mockChart: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: 40,
    marginBottom: Spacing.xl,
    paddingHorizontal: Spacing.xs,
  },
  bar: {
    width: 12,
    backgroundColor: Colors.primaryMuted,
    borderRadius: 2,
  },
  // End Shift
  endShiftButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.md,
  },
  endShiftText: {
    ...Typography.labelMD,
    color: Colors.danger,
    letterSpacing: 0.5,
  },
});
