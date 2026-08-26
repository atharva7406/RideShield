// ============================================================
// RideShield — Crash Alert Screen (Modal)
// ============================================================
// Shown when backend emits CRASH_DETECTED.
// Frontend does NOT detect crashes itself.

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  Vibration,
  Linking,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Audio } from 'expo-av';
import { useRide } from '../store/rideStore';
import { claimService } from '../services/claimService';
import { shiftService } from '../services/shiftService';
import { socketService } from '../services/socket';
import { apiClient } from '../services/api';
import { PrimaryButton } from '../components/PrimaryButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography } from '../constants/theme';

const COUNTDOWN_SECONDS = 60;

export default function CrashAlertScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { state: rideState, setCrashEvent, setActiveClaim, clearShift } = useRide();
  const crashEvent = rideState.crashEvent;
  const shiftId = rideState.activeShift?.id ?? 'unknown';

  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const [helpLoading, setHelpLoading] = useState(false);
  const [okayLoading, setOkayLoading] = useState(false);
  const [showHelpOnWay, setShowHelpOnWay] = useState(false);
  const isSubmitting = useRef(false);
  const soundRef = useRef<Audio.Sound | null>(null);

  const pulseAnim = useRef(new Animated.Value(1)).current;
  const shakeAnim = useRef(new Animated.Value(0)).current;
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Vibrate / buzzer simulation on mount
  useEffect(() => {
    Vibration.vibrate([0, 500, 200, 500, 200], true);

    // Audio Alert Playback
    async function playAlarm() {
      try {
        await Audio.setAudioModeAsync({
          playsInSilentModeIOS: true,
          playThroughEarpieceAndroid: false,
        });
        const { sound } = await Audio.Sound.createAsync(
          require('../../assets/alarm.mp3'),
          { shouldPlay: true, isLooping: true, volume: 1.0 }
        );
        soundRef.current = sound;
      } catch (e) {
        console.warn('Failed to load/play alert sound:', e);
      }
    }
    playAlarm();

    // Pulse animation
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.05, duration: 600, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
      ])
    );
    pulse.start();

    // Shake animation
    const shake = Animated.sequence([
      Animated.timing(shakeAnim, { toValue: 8, duration: 80, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: -8, duration: 80, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: 6, duration: 80, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: -6, duration: 80, useNativeDriver: true }),
      Animated.timing(shakeAnim, { toValue: 0, duration: 80, useNativeDriver: true }),
    ]);
    shake.start();

    // Countdown
    countdownRef.current = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          clearInterval(countdownRef.current!);
          return 0;
        }
        return c - 1;
      });
    }, 1000);

    return () => {
      pulse.stop();
      if (countdownRef.current) clearInterval(countdownRef.current);
      Vibration.cancel();
      if (soundRef.current) {
        soundRef.current.stopAsync().catch(() => {});
        soundRef.current.unloadAsync().catch(() => {});
        soundRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (countdown === 0) {
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (soundRef.current) {
        soundRef.current.stopAsync().catch(() => {});
        soundRef.current.unloadAsync().catch(() => {});
        soundRef.current = null;
      }
      Vibration.cancel();
      setCrashEvent(null);
      router.back();
    }
  }, [countdown, setCrashEvent, router]);

  const handleOkay = useCallback(async () => {
    if (isSubmitting.current) return;
    isSubmitting.current = true;
    setOkayLoading(true);
    if (countdownRef.current) clearInterval(countdownRef.current);

    const incidentId = crashEvent?.id;
    try {
      if (incidentId && !incidentId.startsWith('local-fallback')) {
        await apiClient.post(`/incidents/${incidentId}/okay`);
      }
    } catch (err) {
      console.warn('Failed to resolve incident on backend:', err);
    }

    socketService.emitRiderOkay(shiftId);
    setCrashEvent(null);
    setOkayLoading(false);
    isSubmitting.current = false;

    // Return to live ride
    router.back();
  }, [shiftId, crashEvent, setCrashEvent, router]);

  const handleNeedHelp = useCallback(async () => {
    if (isSubmitting.current) return;
    isSubmitting.current = true;
    setHelpLoading(true);
    if (countdownRef.current) clearInterval(countdownRef.current);
    setShowHelpOnWay(true); // Show "Help is on the way" screen

    const incidentId = crashEvent?.id;
    const lat = crashEvent?.latitude ?? 0;
    const lng = crashEvent?.longitude ?? 0;

    // 1. Fire backend telemetry payload FIRST (don't wait for it to resolve)
    if (incidentId && !incidentId.startsWith('local-fallback')) {
      const location = { lat, lng, timestamp: Date.now() };
      const currentRiderId = rideState.activeShift?.rider_id ?? 'unknown';

      apiClient.post(`/incidents/${incidentId}/sos`, {
        incident_id: incidentId,
        live_gps: location,
        rider_id: currentRiderId,
        triggered_at: new Date().toISOString(),
      }).catch(err => console.warn('SOS telemetry send failed', err));

      // Trigger help status transition on backend
      apiClient.post(`/incidents/${incidentId}/help`).catch(err => console.warn(err));
    }

    // 2. Open native dialer to 112
    try {
      const canOpen = await Linking.canOpenURL('tel:112');
      if (canOpen) {
        await Linking.openURL('tel:112');
      }
    } catch (dialErr) {
      console.warn('Failed to open native dialer:', dialErr);
    }

    // 3. Auto-end shift on backend and frontend
    try {
      if (shiftId && shiftId !== 'unknown') {
        await shiftService.endShift(shiftId, 0.0);
      }
    } catch (endErr) {
      console.warn('Failed to end shift automatically on SOS:', endErr);
    }

    try {
      const response = await claimService.createClaim({
        shiftId,
        incidentId: incidentId && !incidentId.startsWith('local-fallback') ? incidentId : undefined,
        incidentTime: crashEvent?.detectedAt ?? new Date().toISOString(),
        incidentLatitude: lat,
        incidentLongitude: lng,
        riderConfirmed: true,
      });

      socketService.emitRiderNeedsHelp(shiftId, crashEvent!);
      setActiveClaim(response.claim);
      setCrashEvent(null);
      clearShift(); // Ends the shift locally (clears shiftState)

      // Delay a little bit so user sees "Help is on the way" warning card
      setTimeout(() => {
        router.replace('/claim-status');
      }, 3000);
    } catch (err) {
      console.error('[CrashAlert] Claim creation failed:', err);
      setHelpLoading(false);
      isSubmitting.current = false;
      // Redirect anyway to claim status to ensure they don't get stuck
      router.replace('/claim-status');
    }
  }, [shiftId, crashEvent, setActiveClaim, setCrashEvent, router, rideState, clearShift]);

  const circumference = 2 * Math.PI * 26;
  const progress = countdown / COUNTDOWN_SECONDS;

  if (showHelpOnWay) {
    return (
      <View style={styles.overlay}>
        <SafeAreaView style={styles.safe}>
          <Animated.View style={[styles.alertCard, { borderColor: Colors.success, borderWidth: 3 }]}>
            <View style={[styles.warningIconWrap, { backgroundColor: 'rgba(16, 185, 129, 0.1)' }]}>
              <Ionicons name="checkmark-circle" size={56} color={Colors.success} />
            </View>
            <Text style={[styles.alertTitle, { color: Colors.success }]}>HELP IS ON{'\n'}THE WAY</Text>
            <Text style={styles.alertSubtitle}>Emergency services have been dispatched.</Text>
            <Text style={styles.countdownHint}>Your active shift has been ended automatically. Initiating claim processing...</Text>
          </Animated.View>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <View style={styles.overlay}>
      <SafeAreaView style={styles.safe}>
        <Animated.View
          style={[
            styles.alertCard,
            {
              transform: [
                { scale: pulseAnim },
                { translateX: shakeAnim },
              ],
            },
          ]}
        >
          {/* Warning icon */}
          <View style={styles.warningIconWrap}>
            <Ionicons name="warning" size={48} color={Colors.danger} />
          </View>

          <Text style={styles.alertTitle}>POSSIBLE CRASH{'\n'}DETECTED</Text>
          <Text style={styles.alertSubtitle}>Are you okay?</Text>

          {/* Countdown ring */}
          <View style={styles.countdownWrap}>
            <View style={styles.countdownRing}>
              <Text style={styles.countdownNumber}>{countdown}</Text>
              <Text style={styles.countdownLabel}>sec</Text>
            </View>
          </View>

          <Text style={styles.countdownHint}>
            Auto-requesting help in {countdown}s
          </Text>

          {/* Captured info */}
          <View style={styles.capturedRow}>
            {['Location captured', 'Telemetry captured', 'Time recorded'].map(item => (
              <View key={item} style={styles.capturedItem}>
                <Ionicons name="checkmark-circle" size={14} color={Colors.success} />
                <Text style={styles.capturedText}>{item}</Text>
              </View>
            ))}
          </View>

          {/* Buttons */}
          <View style={styles.buttons}>
            <PrimaryButton
              testID="im-okay"
              label="I'M OKAY"
              onPress={handleOkay}
              loading={okayLoading}
              success
              style={styles.okayButton}
            />
            <PrimaryButton
              testID="need-help"
              label="I NEED HELP"
              onPress={handleNeedHelp}
              loading={helpLoading}
              danger
              style={styles.helpButton}
            />
          </View>
        </Animated.View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(10, 14, 26, 0.97)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  safe: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    width: '100%',
    paddingHorizontal: Spacing.lg,
  },
  alertCard: {
    width: '100%',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xxl,
    padding: Spacing.xl,
    alignItems: 'center',
    gap: Spacing.md,
    borderWidth: 2,
    borderColor: Colors.danger,
    shadowColor: Colors.danger,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.4,
    shadowRadius: 24,
    elevation: 16,
  },
  warningIconWrap: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: Colors.dangerMuted,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: 'rgba(255,59,48,0.4)',
  },
  alertTitle: {
    fontSize: 26,
    fontWeight: '900',
    color: Colors.textPrimary,
    textAlign: 'center',
    letterSpacing: 0.5,
    lineHeight: 32,
  },
  alertSubtitle: {
    ...Typography.h3,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  countdownWrap: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  countdownRing: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 4,
    borderColor: Colors.danger,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.dangerMuted,
  },
  countdownNumber: {
    fontSize: 28,
    fontWeight: '800',
    color: Colors.danger,
    lineHeight: 32,
  },
  countdownLabel: {
    ...Typography.caption,
    color: Colors.danger,
  },
  countdownHint: {
    ...Typography.bodyMD,
    color: Colors.textMuted,
    textAlign: 'center',
  },
  capturedRow: {
    width: '100%',
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    gap: Spacing.xs,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  capturedItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  capturedText: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  buttons: {
    width: '100%',
    gap: Spacing.sm,
  },
  okayButton: {},
  helpButton: {},
});
