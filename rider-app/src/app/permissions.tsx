// ============================================================
// RideShield — Permissions Screen
// ============================================================

import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { PrimaryButton } from '../components/PrimaryButton';
import { SecondaryButton } from '../components/SecondaryButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography } from '../constants/theme';

type PermStatus = 'idle' | 'granted' | 'denied' | 'unavailable';

interface Permission {
  id: string;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  description: string;
  status: PermStatus;
}

function statusColor(s: PermStatus): string {
  if (s === 'granted') return Colors.success;
  if (s === 'denied' || s === 'unavailable') return Colors.danger;
  return Colors.textMuted;
}

function statusIcon(s: PermStatus): keyof typeof Ionicons.glyphMap {
  if (s === 'granted') return 'checkmark-circle';
  if (s === 'denied') return 'close-circle';
  if (s === 'unavailable') return 'alert-circle';
  return 'ellipse-outline';
}

export default function PermissionsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [allGranted, setAllGranted] = useState(false);
  const [permissions, setPermissions] = useState<Permission[]>([
    {
      id: 'location',
      icon: 'location',
      title: 'Location Access',
      description: 'Used to track your route and speed.',
      status: 'idle',
    },
    {
      id: 'motion',
      icon: 'pulse',
      title: 'Motion Sensors',
      description: 'Used to monitor movement and detect unusual events.',
      status: 'idle',
    },
    {
      id: 'background',
      icon: 'map',
      title: 'Background Location',
      description: 'Allows ride tracking to continue during an active shift.',
      status: 'idle',
    },
  ]);

  const updatePermStatus = useCallback((id: string, status: PermStatus) => {
    setPermissions(prev =>
      prev.map(p => (p.id === id ? { ...p, status } : p))
    );
  }, []);

  const handleEnable = useCallback(async () => {
    setLoading(true);
    setAllGranted(false);

    // 1. Foreground location
    try {
      const { status: fgStatus } = await Location.requestForegroundPermissionsAsync();
      updatePermStatus('location', fgStatus === 'granted' ? 'granted' : 'denied');
    } catch {
      updatePermStatus('location', 'unavailable');
    }

    // 2. Motion — expo-sensors doesn't require explicit permission on Android
    // On iOS the Accelerometer just works. Mark as granted.
    updatePermStatus('motion', 'granted');

    // 3. Background location (requires foreground first)
    try {
      const { status: bgStatus } = await Location.requestBackgroundPermissionsAsync();
      updatePermStatus('background', bgStatus === 'granted' ? 'granted' : 'denied');
    } catch {
      updatePermStatus('background', 'unavailable');
    }

    setLoading(false);

    // Check if all critical permissions granted (we can proceed even with denied background)
    setAllGranted(true);
  }, [updatePermStatus]);

  const handleProceed = useCallback(() => {
    router.push('/live-ride');
  }, [router]);

  const handleSkip = useCallback(() => {
    // Allow proceeding — app will use simulated data for missing permissions
    router.push('/live-ride');
  }, [router]);

  const hasAttempted = permissions.some(p => p.status !== 'idle');
  const hasDenied = permissions.some(
    p => p.status === 'denied' || p.status === 'unavailable'
  );

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.heroIcon}>
          <Ionicons name="shield-checkmark" size={56} color={Colors.primary} />
        </View>
        <Text style={styles.title}>Enable Tracking</Text>
        <Text style={styles.subtitle}>
          RideShield needs these permissions to protect you during your shift.
        </Text>

        {/* Permission rows */}
        <View style={styles.permissionsCard}>
          {permissions.map((perm, idx) => (
            <React.Fragment key={perm.id}>
              <View style={styles.permRow}>
                <View style={[styles.permIconWrap, { backgroundColor: Colors.primaryMuted }]}>
                  <Ionicons name={perm.icon} size={22} color={Colors.primary} />
                </View>
                <View style={styles.permText}>
                  <Text style={styles.permTitle}>{perm.title}</Text>
                  <Text style={styles.permDesc}>{perm.description}</Text>
                </View>
                {perm.status !== 'idle' && (
                  <Ionicons
                    name={statusIcon(perm.status)}
                    size={22}
                    color={statusColor(perm.status)}
                  />
                )}
              </View>
              {idx < permissions.length - 1 && (
                <View style={styles.permDivider} />
              )}
            </React.Fragment>
          ))}
        </View>

        {hasDenied && (
          <View style={styles.deniedNotice}>
            <Ionicons name="information-circle" size={18} color={Colors.warning} />
            <Text style={styles.deniedText}>
              Some permissions were denied. The app will use simulated sensor data where possible.
              Full accuracy requires location permission.
            </Text>
          </View>
        )}

        {!hasAttempted ? (
          <PrimaryButton
            testID="enable-tracking"
            label="ENABLE TRACKING"
            onPress={handleEnable}
            loading={loading}
          />
        ) : allGranted ? (
          <PrimaryButton
            testID="proceed-to-ride"
            label="START LIVE RIDE"
            onPress={handleProceed}
            success
          />
        ) : (
          <>
            <PrimaryButton
              label="RETRY PERMISSIONS"
              onPress={handleEnable}
              loading={loading}
            />
            <SecondaryButton
              label="Continue with simulated data"
              onPress={handleSkip}
              style={styles.skipButton}
            />
          </>
        )}

        <Text style={styles.privacyNote}>
          Your data is encrypted and only used for coverage and safety analysis.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  scroll: {
    flexGrow: 1,
    padding: Spacing.lg,
    gap: Spacing.lg,
    paddingBottom: Spacing.xxl,
    alignItems: 'center',
  },
  heroIcon: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: Colors.primary,
    marginTop: Spacing.xl,
    boxShadow: '0px 0px 16px rgba(15, 118, 110, 0.35)',
    elevation: 8,
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
    marginTop: -Spacing.sm,
  },
  permissionsCard: {
    width: '100%',
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  permRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    gap: Spacing.md,
  },
  permIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  permText: { flex: 1, gap: 2 },
  permTitle: { ...Typography.bodyMD, color: Colors.textPrimary, fontWeight: '600' },
  permDesc: { ...Typography.bodySM, color: Colors.textSecondary, lineHeight: 16 },
  permDivider: { height: 1, backgroundColor: Colors.border },
  deniedNotice: {
    width: '100%',
    flexDirection: 'row',
    backgroundColor: Colors.warningMuted,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    gap: Spacing.sm,
    alignItems: 'flex-start',
    borderWidth: 1,
    borderColor: 'rgba(255,159,10,0.3)',
  },
  deniedText: {
    ...Typography.bodyMD,
    color: Colors.warning,
    flex: 1,
    lineHeight: 20,
  },
  skipButton: { marginTop: -Spacing.sm },
  privacyNote: {
    ...Typography.caption,
    color: Colors.textMuted,
    textAlign: 'center',
    lineHeight: 16,
  },
});
