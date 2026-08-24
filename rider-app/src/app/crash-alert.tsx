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
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRide } from '../store/rideStore';
import { claimService } from '../services/claimService';
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

  const pulseAnim = useRef(new Animated.Value(1)).current;
  const shakeAnim = useRef(new Animated.Value(0)).current;
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Vibrate / buzzer simulation on mount
  useEffect(() => {
    Vibration.vibrate([0, 500, 200, 500, 200], true);

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
          // Auto-trigger "I need help" on timeout
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
    };
  }, []);

  useEffect(() => {
    if (countdown === 0) {
      handleNeedHelp();
    }
  }, [countdown, handleNeedHelp]);

  const handleOkay = useCallback(async () => {
    setOkayLoading(true);
    if (countdownRef.current) clearInterval(countdownRef.current);

    const incidentId = crashEvent?.id;
    if (incidentId && !incidentId.startsWith('local-fallback')) {
      try {
        await apiClient.post(`/incidents/${incidentId}/okay`);
      } catch (err) {
        console.warn('Failed to resolve incident on backend:', err);
      }
    }

    socketService.emitRiderOkay(shiftId);
    setCrashEvent(null);

    // Return to live ride
    router.back();
  }, [shiftId, crashEvent, setCrashEvent, router]);

  const handleNeedHelp = useCallback(async () => {
    setHelpLoading(true);
    if (countdownRef.current) clearInterval(countdownRef.current);

    const incidentId = crashEvent?.id;
    try {
      if (incidentId && !incidentId.startsWith('local-fallback')) {
        await apiClient.post(`/incidents/${incidentId}/help`);
      }

      const response = await claimService.createClaim({
        shiftId,
        incidentTime: crashEvent?.detectedAt ?? new Date().toISOString(),
        incidentLatitude: crashEvent?.latitude ?? 0,
        incidentLongitude: crashEvent?.longitude ?? 0,
        riderConfirmed: true,
      });

      socketService.emitRiderNeedsHelp(shiftId, crashEvent!);
      setActiveClaim(response.claim);
      setCrashEvent(null);

      router.replace('/claim');
    } catch (err) {
      console.error('[CrashAlert] Claim creation failed:', err);
      setHelpLoading(false);
    }
  }, [shiftId, crashEvent, setActiveClaim, setCrashEvent, router]);

  const circumference = 2 * Math.PI * 26;
  const progress = countdown / COUNTDOWN_SECONDS;

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
