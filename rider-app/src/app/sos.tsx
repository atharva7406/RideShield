// ============================================================
// RideShield — SOS Screen (Modal)
// ============================================================

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Linking,
  Animated,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRide } from '../store/rideStore';
import { useTelemetry } from '../hooks/useTelemetry';
import { socketService } from '../services/socket';
import { apiClient } from '../services/api';
import { PrimaryButton } from '../components/PrimaryButton';
import { SecondaryButton } from '../components/SecondaryButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography } from '../constants/theme';

export default function SOSScreen() {
  const router = useRouter();
  const { state: rideState } = useRide();
  const { telemetry } = useTelemetry({
    shiftId: rideState.activeShift?.id ?? null,
    isActive: false, // Don't run sensors just for this screen
    emitToBackend: false,
  });

  const [step, setStep] = useState<'confirm' | 'sent'>('confirm');
  const [loading, setLoading] = useState(false);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    }).start();
  }, [fadeAnim]);

  const handleSendSOS = useCallback(async () => {
    setLoading(true);

    const lat = telemetry.location?.latitude ?? 0;
    const lng = telemetry.location?.longitude ?? 0;
    const shiftId = rideState.activeShift?.id ?? 'unknown';

    // 1. Emit socket SOS
    socketService.emitSOS(shiftId, lat, lng);

    let incidentId = 'unknown';
    try {
      // 2. Fetch incidents for this shift, or create one if none exists
      const incidents = await apiClient.get<any[]>('/incidents');
      const shiftIncidents = incidents.filter(inc => inc.shift_id === shiftId);
      if (shiftIncidents.length > 0) {
        incidentId = shiftIncidents[0].id;
      } else {
        const newInc = await apiClient.post<any>('/incidents', {
          shift_id: shiftId,
          latitude: lat,
          longitude: lng,
          peak_g_force: 0.0,
          confidence_score: 1.0,
        });
        incidentId = newInc.id;
      }
      
      // 3. Fire backend telemetry payload FIRST (don't wait for it to resolve)
      const location = { lat, lng, timestamp: Date.now() };
      const currentRiderId = rideState.activeShift?.rider_id ?? 'unknown';
      
      apiClient.post(`/incidents/${incidentId}/sos`, {
        incident_id: incidentId,
        live_gps: location,
        rider_id: currentRiderId,
        triggered_at: new Date().toISOString(),
      }).catch(err => console.warn('SOS telemetry send failed', err));
    } catch (e) {
      console.warn('Failed to resolve/fire incident SOS on backend:', e);
    }

    // 4. Open native dialer to 112
    try {
      const canOpen = await Linking.canOpenURL('tel:112');
      if (canOpen) {
        await Linking.openURL('tel:112');
      }
    } catch (dialErr) {
      console.warn('Failed to open native dialer:', dialErr);
    }

    setLoading(false);
    setStep('sent');
  }, [telemetry.location, rideState.activeShift]);

  const handleCallEmergency = useCallback(() => {
    Linking.openURL('tel:112'); // Standard emergency number (India)
  }, []);

  const handleCancel = useCallback(() => {
    router.back();
  }, [router]);

  return (
    <View style={styles.overlay}>
      <SafeAreaView style={styles.safe}>
        <Animated.View style={[styles.card, { opacity: fadeAnim }]}>
          {step === 'confirm' ? (
            <>
              <View style={styles.iconWrap}>
                <Ionicons name="warning" size={48} color={Colors.danger} />
              </View>

              <Text style={styles.title}>Emergency Assistance?</Text>
              <Text style={styles.subtitle}>
                Are you sure you want to trigger SOS? This will alert our emergency response team and your emergency contacts.
              </Text>

              <View style={styles.buttons}>
                <PrimaryButton
                  label="YES, SEND SOS"
                  onPress={handleSendSOS}
                  loading={loading}
                  danger
                  style={styles.actionButton}
                />
                <SecondaryButton
                  label="CANCEL"
                  onPress={handleCancel}
                  style={styles.actionButton}
                />
              </View>
            </>
          ) : (
            <>
              <View style={[styles.iconWrap, { backgroundColor: Colors.successMuted, borderColor: Colors.success }]}>
                <Ionicons name="checkmark" size={48} color={Colors.success} />
              </View>

              <Text style={styles.title}>SOS Sent</Text>
              <Text style={styles.subtitle}>
                Emergency assistance has been requested. Our team is trying to reach you.
              </Text>

              <View style={styles.infoCard}>
                <View style={styles.infoRow}>
                  <Ionicons name="location" size={18} color={Colors.textSecondary} />
                  <Text style={styles.infoText}>
                    {telemetry.location?.latitude.toFixed(4) ?? '0.0000'}, {telemetry.location?.longitude.toFixed(4) ?? '0.0000'}
                  </Text>
                </View>
                <View style={styles.infoDivider} />
                <View style={styles.infoRow}>
                  <Ionicons name="time" size={18} color={Colors.textSecondary} />
                  <Text style={styles.infoText}>
                    {new Date().toLocaleTimeString()}
                  </Text>
                </View>
              </View>

              <View style={styles.buttons}>
                <PrimaryButton
                  label="CALL 112 (AMBULANCE/POLICE)"
                  onPress={handleCallEmergency}
                  danger
                  style={styles.actionButton}
                />
                <SecondaryButton
                  label="CLOSE"
                  onPress={handleCancel}
                  style={styles.actionButton}
                />
              </View>
            </>
          )}
        </Animated.View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(10, 14, 26, 0.90)',
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
  card: {
    width: '100%',
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xxl,
    padding: Spacing.xl,
    alignItems: 'center',
    gap: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  iconWrap: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: Colors.dangerMuted,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: 'rgba(255,59,48,0.4)',
  },
  title: {
    ...Typography.h1,
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  subtitle: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  buttons: {
    width: '100%',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  actionButton: {
    width: '100%',
  },
  infoCard: {
    width: '100%',
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: 4,
  },
  infoText: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  infoDivider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.xs,
  },
});
